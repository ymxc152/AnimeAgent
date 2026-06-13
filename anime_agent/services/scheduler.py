"""APScheduler wrapper with pre-flight health check and task orchestration."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, cast

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from anime_agent.config import Settings, get_settings
from anime_agent.memory.models import Subscription, TaskSchedule
from anime_agent.memory.store import Store
from anime_agent.services.discovery import DiscoveryService
from anime_agent.services.episode_planner import EpisodePlanner
from anime_agent.services.healthcheck import HealthCheck


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
        terminal_statuses = {"completed", "failed", "skipped"}
        active = [ep for ep in episodes if ep.status not in terminal_statuses]

        resume_times: list[datetime] = []
        for i, episode in enumerate(active):
            # Add delay between episodes to avoid RSS rate limiting
            if i > 0:
                await asyncio.sleep(5)

            ep_number = cast(int, episode.episode_number)
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

        next_run = min(resume_times) if resume_times else self.planner.plan_next_run(subscription)
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

    async def _default_executor(self, subscription_id: int, episode_number: int) -> dict[str, Any]:
        """Default no-op executor when none is provided."""
        logger.warning(
            "No episode executor configured; skipping sub={} ep={}",
            subscription_id,
            episode_number,
        )
        return {}
