"""Weekly new-season discovery service."""

from datetime import UTC, datetime
from typing import Any, cast

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from anime_agent.config import Settings, get_settings
from anime_agent.memory.models import Episode, Subscription, TaskSchedule
from anime_agent.memory.store import Store
from anime_agent.services.content_filter import ContentFilter, FilterRules
from anime_agent.services.episode_planner import EpisodePlanner
from anime_agent.services.metadata_resolver import MetadataResolver


class DiscoveryService:
    """Discover seasonal anime, filter them, and create subscriptions."""

    def __init__(
        self,
        session: AsyncSession,
        resolver: MetadataResolver | None = None,
        filter_service: ContentFilter | None = None,
        planner: EpisodePlanner | None = None,
        settings: Settings | None = None,
    ):
        self.store = Store(session)
        self.resolver = resolver or MetadataResolver()
        self.planner = planner or EpisodePlanner()
        self.settings = settings or get_settings()
        self.filter_service = filter_service or ContentFilter(
            FilterRules(
                exclude_ova=self.settings.filter_exclude_ova,
                exclude_movies=self.settings.filter_exclude_movies,
                min_duration_minutes=self.settings.filter_min_duration_minutes,
                exclude_genres=self.settings.filter_exclude_genres,
                exclude_formats=self.settings.filter_exclude_formats,
                require_anime_type=self.settings.filter_require_anime_type,
            )
        )

    async def run(self) -> dict[str, Any]:
        """Run discovery for the current season and return summary."""
        year, season = self._current_season()
        logger.info("Running discovery for {} {}", season, year)

        result = await self.resolver.get_seasonal(year, season)
        if not result.success:
            logger.error("Discovery failed: {}", result.error)
            return {"created": 0, "filtered": 0, "error": result.error}

        candidates = result.data.get("candidates", [])
        created_count = 0
        filtered_count = 0

        for anime in candidates:
            filter_result = self.filter_service.apply(anime)
            if not filter_result.allowed:
                filtered_count += 1
                continue

            if await self._is_duplicate(anime):
                continue

            if self.settings.filter_auto_subscribe_new_season:
                await self._create_subscription(anime)
                created_count += 1

        return {
            "created": created_count,
            "filtered": filtered_count,
            "total": len(candidates),
        }

    async def _is_duplicate(self, anime: dict[str, Any]) -> bool:
        bangumi_id = anime.get("bangumi_id")
        anilist_id = anime.get("anilist_id")

        if bangumi_id is not None:
            existing = await self.store.subscriptions.get_by_bangumi_id(bangumi_id)
            if existing is not None:
                return True

        if anilist_id is not None:
            existing = await self.store.subscriptions.get_by_anilist_id(anilist_id)
            if existing is not None:
                return True

        return False

    async def _create_subscription(self, anime: dict[str, Any]) -> Subscription:
        total = anime.get("total_episodes") or 12
        subscription = Subscription(
            bangumi_id=anime.get("bangumi_id"),
            anilist_id=anime.get("anilist_id"),
            title_romaji=anime.get("title_romaji") or anime.get("title_native") or "Unknown",
            title_native=anime.get("title_native"),
            title_chinese=anime.get("title_chinese"),
            season_year=anime.get("season_year"),
            season=anime.get("season"),
            total_episodes=total,
            local_folder_name=anime.get("title_chinese") or anime.get("title_romaji") or "Unknown",
            source="auto_discover",
            auto_download_enabled=True,
            expected_airing_weekday=self._infer_weekday(anime.get("air_date")),
        )
        subscription = await self.store.subscriptions.create(subscription)

        for number in range(1, cast(int, subscription.total_episodes) + 1):
            await self.store.episodes.create(
                Episode(
                    subscription_id=cast(int, subscription.id),
                    episode_number=number,
                    status="pending",
                )
            )

        schedule = TaskSchedule(
            subscription_id=cast(int, subscription.id),
            task_type="check_updates",
            next_run_at=self.planner.plan_next_run(subscription),
            is_active=True,
        )
        await self.store.schedules.create(schedule)

        logger.info("Auto-subscribed to {} ({} episodes)", subscription.title_romaji, total)
        return subscription

    def _current_season(self) -> tuple[int, str]:
        now = datetime.now(UTC)
        month = now.month
        if month <= 3:
            return now.year, "WINTER"
        if month <= 6:
            return now.year, "SPRING"
        if month <= 9:
            return now.year, "SUMMER"
        return now.year, "FALL"

    def _infer_weekday(self, air_date: str | None) -> int | None:
        """Infer weekday (0=Monday) from an ISO air_date string."""
        if not air_date:
            return None
        try:
            return datetime.fromisoformat(air_date).weekday()
        except ValueError:
            return None
