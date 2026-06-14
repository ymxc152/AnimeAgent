"""Status query service for conversational statistics."""

from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from anime_agent.memory.models import Episode, Subscription


class StatusQueryService:
    """Read-only queries used by the conversational agent.

    All methods return structured data so the reply layer can decide how to
    format the final natural-language answer.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self) -> list[dict[str, Any]]:
        """Return active subscriptions with episode counts."""
        result = await self.session.execute(
            select(Subscription).where(Subscription.status == "ongoing")
        )
        subs = list(result.scalars().all())
        output = []
        for sub in subs:
            counts = await self._episode_counts(cast(int, sub.id))
            output.append(
                {
                    "id": sub.id,
                    "title": sub.title_chinese or sub.title_native or sub.title_romaji,
                    "total_episodes": sub.total_episodes,
                    "completed": counts.get("completed", 0),
                    "downloaded": counts.get("downloaded", 0),
                    "failed": counts.get("failed", 0),
                    "pending": counts.get("pending", 0),
                }
            )
        return output

    async def subscription_detail(self, title: str) -> dict[str, Any] | None:
        """Return subscription + episode summary for a title."""
        sub = await self._find_subscription_by_title(title)
        if sub is None:
            return None

        episodes = await self.session.execute(
            select(Episode)
            .where(Episode.subscription_id == sub.id)
            .order_by(Episode.episode_number)
        )
        eps = list(episodes.scalars().all())
        return {
            "id": sub.id,
            "title": sub.title_chinese or sub.title_native or sub.title_romaji,
            "status": sub.status,
            "total_episodes": sub.total_episodes,
            "completed": sum(1 for e in eps if e.status == "completed"),
            "downloaded": sum(1 for e in eps if e.status == "downloaded"),
            "failed": sum(1 for e in eps if e.status == "failed"),
            "pending": sum(1 for e in eps if e.status == "pending"),
            "episodes": [
                {
                    "number": e.episode_number,
                    "status": e.status,
                    "aired_at": e.aired_at.isoformat() if e.aired_at else None,
                }
                for e in eps
            ],
        }

    async def pending_torrents(self) -> list[dict[str, Any]]:
        """Return episodes waiting for torrents or human review."""
        statuses = ["waiting_for_rss", "no_match", "human_review", "low_confidence"]
        result = await self.session.execute(
            select(Episode).where(Episode.status.in_(statuses)).order_by(Episode.updated_at)
        )
        eps = list(result.scalars().all())
        output = []
        for ep in eps:
            sub = await self.session.get(Subscription, cast(int, ep.subscription_id))
            output.append(
                {
                    "episode_id": ep.id,
                    "subscription_id": ep.subscription_id,
                    "title": sub.title_chinese or sub.title_native or sub.title_romaji if sub else None,
                    "episode_number": ep.episode_number,
                    "status": ep.status,
                }
            )
        return output

    async def anime_info(self, title: str) -> dict[str, Any] | None:
        """Return metadata for a subscription."""
        sub = await self._find_subscription_by_title(title)
        if sub is None:
            return None
        return {
            "id": sub.id,
            "title": sub.title_chinese or sub.title_native or sub.title_romaji,
            "title_romaji": sub.title_romaji,
            "title_native": sub.title_native,
            "title_chinese": sub.title_chinese,
            "season": sub.season,
            "season_year": sub.season_year,
            "total_episodes": sub.total_episodes,
            "status": sub.status,
        }

    async def failed_tasks(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return recent failed episodes."""
        result = await self.session.execute(
            select(Episode)
            .where(Episode.status == "failed")
            .order_by(Episode.updated_at.desc())
            .limit(limit)
        )
        eps = list(result.scalars().all())
        output = []
        for ep in eps:
            sub = await self.session.get(Subscription, cast(int, ep.subscription_id))
            output.append(
                {
                    "episode_id": ep.id,
                    "subscription_id": ep.subscription_id,
                    "title": sub.title_chinese or sub.title_native or sub.title_romaji if sub else None,
                    "episode_number": ep.episode_number,
                    "error_log": ep.error_log,
                    "updated_at": ep.updated_at.isoformat() if ep.updated_at else None,
                }
            )
        return output

    async def _find_subscription_by_title(self, title: str) -> Subscription | None:
        """Fuzzy title match across title variants."""
        lowered = title.lower().strip()
        result = await self.session.execute(select(Subscription))
        for sub in result.scalars().all():
            for variant in (sub.title_chinese, sub.title_native, sub.title_romaji):
                if variant and lowered in variant.lower():
                    return sub
        return None

    async def _episode_counts(self, subscription_id: int) -> dict[str, int]:
        """Aggregate episode statuses for a subscription."""
        result = await self.session.execute(
            select(Episode.status, func.count(Episode.id))
            .where(Episode.subscription_id == subscription_id)
            .group_by(Episode.status)
        )
        return {row[0]: row[1] for row in result.all()}
