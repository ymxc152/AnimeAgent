"""match_torrent node for Episode Graph."""

from typing import Any

from anime_agent.services.torrent_selector import TorrentSelector
from anime_agent.tools.base import BaseTool
from anime_agent.utils.logger import logger


class MatchTorrentNode:
    """Select the best torrent candidate for the target episode.

    Uses rule-based pre-filtering + LLM selection.  High confidence matches
    proceed directly to download; medium confidence matches accumulate up to
    ``MAX_LOW_CONFIDENCE_ATTEMPTS`` and then pause for human review.
    """

    CONFIDENCE_THRESHOLD = 0.5
    HIGH_CONFIDENCE_THRESHOLD = 0.8
    MAX_LOW_CONFIDENCE_ATTEMPTS = 3

    def __init__(self, selector: TorrentSelector | None = None, llm_tool: BaseTool | None = None):
        if selector is not None:
            self.selector = selector
        else:
            from anime_agent.tools.llm_tool import LLMTool
            self.selector = TorrentSelector(llm_tool=llm_tool or LLMTool())

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run torrent selection and update state."""
        logger.info(
            "Matching torrent for episode {} of subscription {}",
            state.get("episode_number"),
            state.get("subscription_id"),
        )

        candidates = state.get("torrent_candidates", [])
        failed_hashes = state.get("torrent_failed_hashes", [])
        title_variants = [
            t
            for t in (
                state.get("title_romaji"),
                state.get("title_chinese"),
                state.get("title_native"),
            )
            if t
        ]

        # If no candidates and resource search hasn't been tried yet, trigger it
        if not candidates and not state.get("resource_searched"):
            logger.info("No candidates for episode {}, triggering resource search", state.get("episode_number"))
            return {
                "matched_torrent": None,
                "status": "search_resources",
            }

        result = await self.selector.select(
            candidates=candidates,
            episode_number=state.get("episode_number", 1),
            title_variants=title_variants,
            failed_hashes=failed_hashes,
        )

        if not result.success:
            logger.error("Torrent selection failed for episode {}: {}", state.get("episode_number"), result.error)
            return {
                "matched_torrent": None,
                "status": "failed",
                "errors": [f"Torrent selection failed: {result.error}"],
            }

        data = result.data
        if not data.get("matched"):
            logger.info("No torrent match found for episode {}", state.get("episode_number"))
            return {
                "matched_torrent": None,
                "status": "no_match",
            }

        confidence = data.get("confidence", 0.0)

        # Below the minimum threshold -> treat as no match and wait for more candidates.
        if confidence < self.CONFIDENCE_THRESHOLD:
            logger.info(
                "Confidence below threshold ({:.2f}) for episode {}, will retry later",
                confidence,
                state.get("episode_number"),
            )
            return {
                "matched_torrent": None,
                "status": "no_match",
            }

        # High confidence -> proceed to download immediately.
        if confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            logger.info(
                "Matched episode {}: hash={}, confidence={:.2f}",
                state.get("episode_number"),
                data.get("info_hash"),
                confidence,
            )
            return {
                "matched_torrent": {
                    "info_hash": data.get("info_hash"),
                    "title": data.get("title"),
                    "link": data.get("link"),
                    "confidence": confidence,
                },
                "status": "matched",
                "low_confidence_count": 0,
            }

        # Medium confidence -> accumulate attempts and eventually ask a human.
        low_confidence_count = state.get("low_confidence_count", 0) + 1
        logger.info(
            "Low confidence ({:.2f}) for episode {} (attempt {}/{})",
            confidence,
            state.get("episode_number"),
            low_confidence_count,
            self.MAX_LOW_CONFIDENCE_ATTEMPTS,
        )

        if low_confidence_count >= self.MAX_LOW_CONFIDENCE_ATTEMPTS:
            return {
                "matched_torrent": {
                    "info_hash": data.get("info_hash"),
                    "title": data.get("title"),
                    "link": data.get("link"),
                    "confidence": confidence,
                },
                "status": "human_review",
                "requires_human": True,
                "low_confidence_count": low_confidence_count,
            }

        return {
            "matched_torrent": None,
            "status": "low_confidence",
            "low_confidence_count": low_confidence_count,
        }
