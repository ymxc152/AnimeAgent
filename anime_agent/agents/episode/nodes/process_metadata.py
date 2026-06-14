"""process_metadata node for Episode Graph — content classification + TMDB validation."""

from typing import Any

from anime_agent.config import settings
from anime_agent.tools.base import BaseTool
from anime_agent.tools.tmdb_tool import TMDBTool, TMDBToolInput
from anime_agent.utils.logger import logger


class ProcessMetadataNode:
    """Classify content and cross-validate episode metadata against TMDB."""

    def __init__(self, tmdb_tool: BaseTool | None = None) -> None:
        self.tmdb_tool = tmdb_tool or TMDBTool()

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process metadata and return updated state."""
        logger.info(
            "Processing metadata for episode {} of subscription {}",
            state.get("episode_number"),
            state.get("subscription_id"),
        )

        content_type = self._resolve_content_type(state)
        verified, confidence = await self._verify_with_tmdb(state)

        return {
            "content_type": content_type,
            "tmdb_id": state.get("tmdb_id"),
            "confidence": confidence if verified else state.get("confidence", 0.0),
            "verified": verified,
            "status": "metadata_processed",
        }

    def _resolve_content_type(self, state: dict[str, Any]) -> str:
        """Resolve content type from state or subscription format."""
        existing = state.get("content_type")
        if existing:
            return str(existing)

        fmt = (state.get("format") or "").upper()
        if fmt in {"MOVIE", "FILM"}:
            return "Movie"
        if fmt in {"OVA"}:
            return "OVA"
        if fmt in {"ONA"}:
            return "ONA"
        if fmt in {"SPECIAL", "SP"}:
            return "SP"

        return "TV"

    async def _verify_with_tmdb(
        self, state: dict[str, Any]
    ) -> tuple[bool, float]:
        """Cross-validate season/episode mapping against TMDB when configured.

        Returns (verified, confidence). If TMDB is unavailable or the episode is
        not found, returns (False, 0.0) so the pipeline can continue without
        blocking organization.
        """
        tmdb_id = state.get("tmdb_id")
        season = state.get("season")
        episode_number = state.get("episode_number")

        if not settings.tmdb_api_key:
            return False, 0.0
        if tmdb_id is None or season is None or episode_number is None:
            return False, 0.0

        try:
            result = await self.tmdb_tool.invoke(
                TMDBToolInput(action="season", tmdb_id=tmdb_id, season_number=season)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("TMDB season validation failed: {}", exc)
            return False, 0.0

        if not result.success or not result.data:
            logger.warning("TMDB season validation failed: {}", result.error)
            return False, 0.0

        season_data = result.data.get("season", {})
        episodes = season_data.get("episodes", [])

        for ep in episodes:
            if ep.get("episode_number") == episode_number:
                logger.info(
                    "TMDB verified episode {} for tmdb_id {} season {}",
                    episode_number,
                    tmdb_id,
                    season,
                )
                return True, 1.0

        logger.warning(
            "TMDB episode {} not found for tmdb_id {} season {}",
            episode_number,
            tmdb_id,
            season,
        )
        return False, 0.0
