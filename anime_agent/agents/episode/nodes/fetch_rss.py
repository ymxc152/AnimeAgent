"""fetch_rss node for Episode Graph."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from anime_agent.memory.store import Store
from anime_agent.tools.base import BaseTool
from anime_agent.tools.rss_tool import RSSTool, RSSToolInput
from anime_agent.utils.logger import logger


class FetchRSSNode:
    """Fetch RSS candidates from ALL active RSS sources and merge them."""

    def __init__(
        self,
        rss_tool: BaseTool | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ):
        self.rss_tool = rss_tool or RSSTool()
        self.session_factory = session_factory

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Fetch RSS from all active sources and merge candidates."""
        logger.info(
            "Fetching RSS for episode {} of subscription {}",
            state.get("episode_number"),
            state.get("subscription_id"),
        )

        sources = await self._get_active_sources(state.get("rss_source_id"))
        if not sources:
            logger.error("No active RSS sources found")
            return {
                "torrent_candidates": state.get("torrent_candidates", []),
                "status": "failed",
                "errors": ["No active RSS sources configured"],
            }

        merged = list(state.get("torrent_candidates", []))
        existing_hashes = {
            c.get("info_hash") for c in merged if c.get("info_hash")
        }

        for source in sources:
            url = source.url
            logger.info("Fetching RSS source: {} ({})", source.name, url)
            result = await self.rss_tool.invoke(RSSToolInput(url=url))
            if not result.success:
                logger.warning(
                    "RSS fetch failed for source {}: {}",
                    source.name,
                    result.error,
                )
                continue

            new_entries = result.data.get("entries", [])
            for entry in new_entries:
                info_hash = entry.get("info_hash")
                if info_hash and info_hash in existing_hashes:
                    continue
                # Tag each entry with its source for traceability
                entry["rss_source_name"] = source.name
                merged.append(entry)
                if info_hash:
                    existing_hashes.add(info_hash)

            logger.info(
                "Fetched {} entries from {}, total candidates: {}",
                len(new_entries),
                source.name,
                len(merged),
            )

        if not merged:
            logger.warning(
                "No RSS candidates found for episode {} from any source",
                state.get("episode_number"),
            )
            return {
                "torrent_candidates": [],
                "status": "waiting_for_rss",
            }

        return {"torrent_candidates": merged, "status": "fetching"}

    async def _get_active_sources(self, rss_source_id: int | None = None) -> list[Any]:
        """Load active RSS sources from the database.

        If ``rss_source_id`` is provided, prefer that specific source while still
        falling back to all active sources when it is missing or inactive.
        """
        if self.session_factory is None:
            logger.error("No session_factory configured for FetchRSSNode")
            return []
        async with self.session_factory() as session:
            store = Store(session)
            if rss_source_id is not None:
                source = await store.rss_sources.get_by_id(rss_source_id)
                if source is not None and source.is_active:
                    return [source]
                logger.warning(
                    "Requested RSS source {} not found or inactive; falling back to all active sources",
                    rss_source_id,
                )
            return await store.rss_sources.list_active()
