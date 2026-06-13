"""process_metadata node for Episode Graph — minimal content classification."""

from typing import Any

from anime_agent.utils.logger import logger


class ProcessMetadataNode:
    """Classify content and attach metadata before organizing files.

    This is a minimal implementation: it derives ``content_type`` from the
    subscription format when available and marks the episode as ready for
    organization.  A full implementation would cross-validate against TMDB.
    """

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process metadata and return updated state."""
        logger.info(
            "Processing metadata for episode {} of subscription {}",
            state.get("episode_number"),
            state.get("subscription_id"),
        )

        content_type = self._resolve_content_type(state)

        return {
            "content_type": content_type,
            "tmdb_id": state.get("tmdb_id"),
            "confidence": state.get("confidence", 1.0),
            "verified": state.get("verified", False),
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
