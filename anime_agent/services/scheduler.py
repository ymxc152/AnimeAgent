"""APScheduler wrapper with pre-flight health check and task orchestration."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from anime_agent.config import Settings, get_settings
from anime_agent.memory.models import Episode, Subscription, TaskSchedule
from anime_agent.memory.store import Store
from anime_agent.services.discovery import DiscoveryService
from anime_agent.services.episode_planner import EpisodePlanner
from anime_agent.services.healthcheck import HealthCheck
from anime_agent.services.qb_sync_service import QBSyncService


class PreFlightHealthCheckError(RuntimeError):
    """Raised when the scheduler cannot start because pre-flight checks failed."""


class Scheduler:
    """Schedule subscription checks and weekly discovery jobs.

    The scheduler performs a pre-flight health check on startup, bootstraps
    :class:`TaskSchedule` rows for active subscriptions, and periodically
    invokes the configured executor for due work.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        health_check: HealthCheck,
        planner: EpisodePlanner | None = None,
        settings: Settings | None = None,
        executor: Callable[[int, int], Awaitable[dict[str, Any]]] | None = None,
    ):
        self.session_factory = session_factory
        self.health_check = health_check
        self.planner = planner or EpisodePlanner()
        self.settings = settings or get_settings()
        self.executor = executor or self._default_executor
        self._scheduler: AsyncIOScheduler | None = None

    async def start(self) -> None:
        """Run pre-flight checks, bootstrap schedules, and start APScheduler."""
        report = await self.health_check.run()
        if not report.healthy:
            raise PreFlightHealthCheckError(f"Pre-flight health check failed: {report.errors}")

        await self.bootstrap_schedules()

        if self._scheduler is None:
            self._scheduler = AsyncIOScheduler()

        self._scheduler.add_job(
            self.tick,
            "interval",
            seconds=self.settings.check_interval_seconds,
            id="tick",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self.run_discovery,
            CronTrigger.from_crontab(self.settings.discovery_cron),
            id="discovery",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """Shutdown the underlying APScheduler instance."""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        logger.info("Scheduler stopped")

    async def bootstrap_schedules(self, session: AsyncSession | None = None) -> None:
        """Create TaskSchedule rows for active subscriptions that lack one."""
        if session is None:
            async with self.session_factory() as session:
                return await self.bootstrap_schedules(session)

        store = Store(session)
        subscriptions = await store.subscriptions.list_active()

        for subscription in subscriptions:
            sub_id = cast(int, subscription.id)
            existing = await store.schedules.get_by_subscription(sub_id)
            if existing is not None:
                continue

            next_run = self.planner.plan_next_run(subscription)
            schedule = TaskSchedule(
                subscription_id=sub_id,
                task_type="check_updates",
                next_run_at=next_run,
                is_active=True,
            )
            await store.schedules.create(schedule)
            logger.debug("Bootstrapped schedule for subscription {}", subscription.id)

    async def tick(self, session: AsyncSession | None = None) -> None:
        """Process due schedules and invoke the executor for pending episodes."""
        if session is None:
            async with self.session_factory() as session:
                return await self.tick(session)

        # Sync active qBittorrent progress first so the rest of the tick sees fresh state.
        try:
            sync_summary = await QBSyncService(session).sync()
            if sync_summary.get("updated"):
                logger.debug("Synced {} episodes from qBittorrent", sync_summary["updated"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("qBittorrent sync failed during tick: {}", exc)

        store = Store(session)
        now = datetime.now(UTC)
        due_schedules = await store.schedules.list_due(now)

        for schedule in due_schedules:
            subscription = await store.subscriptions.get_by_id(cast(int, schedule.subscription_id))
            if subscription is None:
                logger.warning(
                    "Schedule {} references missing subscription {}",
                    schedule.id,
                    schedule.subscription_id,
                )
                continue

            await self._process_subscription(store, subscription)

    async def run_discovery(self) -> None:
        """Run the weekly new-season discovery job."""
        async with self.session_factory() as session:
            service = DiscoveryService(session, settings=self.settings)
            summary = await service.run()
            logger.info("Discovery completed: {}", summary)

    async def _process_subscription(self, store: Store, subscription: Subscription) -> None:
        """Execute active episodes for a subscription and reschedule it."""
        sub_id = cast(int, subscription.id)
        episodes = await store.episodes.list_by_subscription(sub_id)
        terminal_statuses = {"completed", "skipped"}
        retry_cooldown = timedelta(seconds=300)
        now_naive = datetime.now(UTC).replace(tzinfo=None)
        active: list[Episode] = []

        for ep in episodes:
            if ep.status in terminal_statuses:
                continue
            if ep.status in ("failed", "human_review"):
                updated_at = ep.updated_at
                if updated_at is None or now_naive - updated_at >= retry_cooldown:
                    logger.info(
                        "Auto-retrying episode {} of subscription {} from status={}",
                        ep.episode_number,
                        sub_id,
                        ep.status,
                    )
                    ep.status = "pending"
                    ep.error_log = None
                    ep.human_input = None
                    active.append(ep)
                continue
            active.append(ep)

        resume_times: list[datetime] = []
        for i, episode in enumerate(active):
            ep_number = cast(int, episode.episode_number)

            if not self._episode_has_aired(subscription, episode):
                logger.info(
                    "Episode {} of subscription {} has not aired yet; skipping this tick",
                    ep_number,
                    subscription.id,
                )
                continue

            # Small stagger between episodes; RSS responses are cached for 5 minutes,
            # so this is mainly to avoid overwhelming the local event loop.
            if i > 0:
                await asyncio.sleep(1)

            try:
                final = await self.executor(sub_id, ep_number)
                resume_after = self._parse_resume_after(final)
                if resume_after is not None:
                    resume_times.append(resume_after)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Executor failed for subscription {} episode {}: {}",
                    subscription.id,
                    episode.episode_number,
                    exc,
                )

        if resume_times:
            next_run = min(resume_times)
        elif any(
            ep.status == "pending" and self._episode_has_aired(subscription, ep) for ep in episodes
        ):
            # There are aired episodes still pending: check again soon rather than
            # waiting for the weekly airing slot.
            next_run = now_naive + timedelta(minutes=15)
        else:
            next_run = self.planner.plan_next_run(subscription)

        schedule = await store.schedules.get_by_subscription(sub_id)
        if schedule is not None:
            await store.schedules.update_next_run(cast(int, schedule.id), next_run)

    def _parse_resume_after(self, result: Any) -> datetime | None:
        """Parse resume_after ISO timestamp returned by an executor."""
        if not isinstance(result, dict):
            return None
        resume_after = result.get("resume_after")
        if not resume_after:
            return None
        try:
            dt = datetime.fromisoformat(resume_after)
            if dt.tzinfo is not None:
                dt = dt.astimezone(UTC).replace(tzinfo=None)
            return dt
        except ValueError:
            logger.warning("Invalid resume_after value: {}", resume_after)
            return None

    def _episode_has_aired(self, subscription: Subscription, episode: Episode) -> bool:
        """Return True if the episode is expected to have aired.

        Priority:
        1. If ``episode.aired_at`` is set, use it directly.
        2. If the subscription has ``expected_airing_weekday``/``time``,
           estimate the first air date from ``subscription.created_at`` and
           assume each subsequent episode airs one week later.
        3. Otherwise allow processing (no gating information).
        """
        if episode.aired_at is not None:
            aired_at = cast(datetime, episode.aired_at)
            if aired_at.tzinfo is None:
                aired_at = aired_at.replace(tzinfo=UTC)
            return bool(datetime.now(UTC) >= aired_at.astimezone(UTC))

        weekday = subscription.expected_airing_weekday
        if weekday is None:
            return True

        airing_time = subscription.expected_airing_time or "00:00"
        try:
            hour, minute = map(int, str(airing_time).split(":")[:2])
        except ValueError:
            hour, minute = 0, 0

        tz_name = subscription.airing_timezone or "Asia/Tokyo"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:  # noqa: BLE001
            tz = ZoneInfo("Asia/Tokyo")

        now = datetime.now(tz)
        anchor = subscription.created_at or datetime.now(UTC)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=UTC)
        anchor = anchor.astimezone(tz)

        # First occurrence of weekday/time on or after the anchor.
        days_ahead = (weekday - anchor.weekday()) % 7
        first_air = anchor.replace(hour=hour, minute=minute, second=0, microsecond=0)
        first_air += timedelta(days=days_ahead)
        if first_air < anchor:
            first_air += timedelta(weeks=1)

        ep_number = cast(int, episode.episode_number)
        episode_air_date = first_air + timedelta(weeks=ep_number - 1)
        return now >= episode_air_date

    async def _default_executor(self, subscription_id: int, episode_number: int) -> dict[str, Any]:
        """Default no-op executor when none is provided."""
        logger.warning(
            "No episode executor configured; skipping sub={} ep={}",
            subscription_id,
            episode_number,
        )
        return {}
