"""Episode Graph runner that loads DB state, executes the graph, and persists results."""

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from langgraph.graph.state import CompiledStateGraph
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from anime_agent.agents.episode.graph import build_episode_graph
from anime_agent.agents.episode.state import EpisodeAgentState
from anime_agent.memory.models import Episode, Subscription, TaskSchedule
from anime_agent.memory.store import Store


class EpisodeGraphRunner:
    """Execute the Episode Graph for a single subscription/episode pair.

    This class is designed to be passed as the ``executor`` callback to
    :class:`anime_agent.services.scheduler.Scheduler`.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        graph: CompiledStateGraph | None = None,
    ):
        self.session_factory = session_factory
        self.graph = graph or build_episode_graph(session_factory=session_factory)

    async def __call__(self, subscription_id: int, episode_number: int) -> dict[str, Any]:
        """Scheduler-compatible executor entry point."""
        async with self.session_factory() as session:
            return await self.run(subscription_id, episode_number, session)

    async def run(
        self,
        subscription_id: int,
        episode_number: int,
        session: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """Load state, run the Episode Graph, and persist the outcome."""
        if session is None:
            async with self.session_factory() as session:
                return await self.run(subscription_id, episode_number, session)

        store = Store(session)
        subscription = await store.subscriptions.get_by_id(subscription_id)
        if subscription is None:
            raise ValueError(f"Subscription {subscription_id} not found")

        episode = await store.episodes.get_by_subscription_and_number(
            subscription_id, episode_number
        )
        if episode is None:
            raise ValueError(
                f"Episode {episode_number} not found for subscription {subscription_id}"
            )

        state = self._build_state(subscription, episode)
        final = await self.graph.ainvoke(state)

        await self._persist_results(store, subscription, episode, final)
        return final

    def _build_state(self, subscription: Subscription, episode: Episode) -> EpisodeAgentState:
        """Hydrate an EpisodeAgentState from DB rows."""
        candidates = self._load_json(cast(str | None, episode.torrent_candidates), default=[])
        failed_hashes = self._load_json(cast(str | None, episode.torrent_failed_hashes), default=[])

        info_hash = cast(str | None, episode.torrent_hash)
        if not info_hash:
            # Backward compatibility: some rows may still store the hash in
            # torrent_info_hash while torrent_hash is empty.
            info_hash = cast(str | None, episode.torrent_info_hash)
        link = cast(str | None, episode.torrent_link)
        matched_torrent = None
        if info_hash or link:
            matched_torrent = {
                "info_hash": info_hash,
                "title": cast(str | None, episode.torrent_title)
                or cast(str | None, episode.torrent_name),
                "link": link,
            }

        download_path = cast(str | None, episode.download_path)
        download_files: list[str] = [download_path] if download_path else []

        # Determine RSS source: prefer subscription's explicit source, fall back to default
        rss_source_id = cast(int | None, subscription.rss_source_id)
        if rss_source_id is None:
            from anime_agent.config import settings
            if getattr(settings, "rss_default_url", None):
                rss_source_id = 1

        return EpisodeAgentState(
            goal_id=f"sub_{subscription.id}_ep_{episode.episode_number}",
            subscription_id=cast(int, subscription.id),
            episode_number=cast(int, episode.episode_number),
            rss_source_id=rss_source_id,
            title_romaji=cast(str, subscription.title_romaji),
            title_native=cast(str, subscription.title_native or ""),
            title_chinese=cast(str | None, subscription.title_chinese),
            season=int(getattr(subscription, "season", 1) or 1),
            bangumi_data={},
            anilist_data={},
            tmdb_data=None,
            torrent_candidates=candidates,
            matched_torrent=matched_torrent,
            torrent_hash=cast(str | None, episode.torrent_hash),
            torrent_name=cast(str | None, episode.torrent_name),
            torrent_failed_hashes=failed_hashes,
            download_files=download_files,
            download_progress=0.0,
            classification=None,
            organized_path=cast(str | None, episode.organized_path),
            organized_files=[],
            emby_refreshed=False,
            status=cast(str, episode.status) or "pending",
            errors=[],
            requires_human=cast(str, episode.status) == "human_review",
            human_input=cast(str | None, episode.human_input),
            low_confidence_count=cast(int, episode.low_confidence_count or 0),
            resume_after=None,
            resource_searched=False,
        )

    async def _persist_results(
        self,
        store: Store,
        subscription: Subscription,
        episode: Episode,
        final: dict[str, Any],
    ) -> None:
        """Write terminal graph state back to the database."""
        self._set(episode, "status", final.get("status", episode.status))
        self._set(episode, "torrent_candidates", json.dumps(final.get("torrent_candidates", [])))
        self._set(episode, "torrent_hash", final.get("torrent_hash"))
        self._set(episode, "torrent_name", final.get("torrent_name"))
        matched = final.get("matched_torrent") or {}
        self._set(episode, "torrent_title", matched.get("title"))
        self._set(episode, "torrent_info_hash", matched.get("info_hash"))
        self._set(episode, "torrent_link", matched.get("link"))
        self._set(episode, "download_path", self._first_file(final.get("download_files", [])))
        self._set(episode, "organized_path", final.get("organized_path"))
        self._set(episode, "low_confidence_count", final.get("low_confidence_count", 0))
        self._set(episode, "human_input", final.get("human_input"))
        self._set(
            episode,
            "torrent_failed_hashes",
            json.dumps(final.get("torrent_failed_hashes", [])),
        )
        self._set(episode, "metadata_verified", bool(final.get("classification")))

        errors = final.get("errors", [])
        if errors:
            self._set(episode, "error_log", "\n".join(str(e) for e in errors))

        await store.episodes.update(episode)

        resume_after = final.get("resume_after")
        if resume_after:
            await self._reschedule(store, subscription, resume_after)

    async def _reschedule(
        self, store: Store, subscription: Subscription, resume_after: str
    ) -> None:
        """Update the subscription schedule to the requested resume time."""
        try:
            resume_dt = datetime.fromisoformat(resume_after)
        except ValueError:
            logger.warning("Invalid resume_after value: {}", resume_after)
            return

        sub_id = cast(int, subscription.id)
        schedule = await store.schedules.get_by_subscription(sub_id)
        if schedule is None:
            schedule = TaskSchedule(
                subscription_id=sub_id,
                next_run_at=resume_dt.replace(tzinfo=None),
                is_active=True,
            )
            await store.schedules.create(schedule)
        else:
            await store.schedules.update_next_run(
                cast(int, schedule.id), resume_dt.replace(tzinfo=None)
            )

    def _set(self, episode: Episode, field: str, value: Any) -> None:
        """Set an Episode attribute while avoiding mypy Column type complaints."""
        setattr(episode, field, value)

    def _load_json(self, value: str | None, default: Any) -> Any:
        """Safely parse a JSON column value."""
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    def _first_file(self, files: Sequence[str] | None) -> str | None:
        """Return the first download file path if any."""
        if files:
            return files[0]
        return None
