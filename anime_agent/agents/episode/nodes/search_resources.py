"""search_resources node for Episode Graph — AnimeGarden fallback search."""

from typing import Any

from anime_agent.config import Settings, get_settings
from anime_agent.tools.animes_garden_tool import AnimeGardenTool, AnimeGardenToolInput
from anime_agent.tools.base import BaseTool
from anime_agent.utils.logger import logger


class SearchResourcesNode:
    """Search AnimeGarden for torrent candidates as RSS fallback."""

    def __init__(
        self,
        anime_garden_tool: BaseTool | None = None,
        settings: Settings | None = None,
    ):
        self.anime_garden_tool = anime_garden_tool or AnimeGardenTool()
        self.settings = settings or get_settings()

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Search AnimeGarden and merge candidates."""
        logger.info(
            "Searching AnimeGarden resources for episode {} of subscription {}",
            state.get("episode_number"),
            state.get("subscription_id"),
        )

        title = state.get("title_chinese") or state.get("title_romaji") or state.get("title_native", "")
        if not title:
            logger.error("No title available for resource search")
            return {
                "torrent_candidates": state.get("torrent_candidates", []),
                "status": "failed",
                "errors": ["No title available for resource search"],
            }

        if not self.settings.resource_fallback_enabled:
            logger.info(
                "Resource fallback disabled; skipping AnimeGarden search for episode {}",
                state.get("episode_number"),
            )
            return {
                "torrent_candidates": state.get("torrent_candidates", []),
                "status": "schedule_resume",
                "resource_searched": False,
            }

        existing = {
            c.get("info_hash") for c in state.get("torrent_candidates", []) if c.get("info_hash")
        }
        merged = list(state.get("torrent_candidates", []))
        max_pages = max(1, self.settings.resource_search_max_pages)

        for page in range(1, max_pages + 1):
            result = await self.anime_garden_tool.invoke(
                AnimeGardenToolInput(search=title, page=page)
            )

            if not result.success:
                logger.error("AnimeGarden search failed: {}", result.error)
                return {
                    "torrent_candidates": merged,
                    "status": "failed",
                    "errors": [f"AnimeGarden search failed: {result.error}"],
                }

            new_candidates = result.data.get("candidates", [])
            for candidate in new_candidates:
                info_hash = candidate.get("info_hash")
                if info_hash and info_hash in existing:
                    continue
                merged.append(candidate)
                if info_hash:
                    existing.add(info_hash)

            if len(new_candidates) == 0:
                break

        logger.info(
            "Found {} AnimeGarden candidates for episode {}, total: {}",
            len(merged) - len(state.get("torrent_candidates", [])),
            state.get("episode_number"),
            len(merged),
        )
        return {"torrent_candidates": merged, "status": "searched", "resource_searched": True}
