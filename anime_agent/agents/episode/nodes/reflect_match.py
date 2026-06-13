"""reflect_match node for Episode Graph.

This node acts as a lightweight reasoning agent. When the primary torrent
selector is uncertain, it re-examines the candidates using metadata and
release-group heuristics, then either:

- auto_approve a candidate and route to send_download,
- request a broader search (Anime Garden fallback),
- keep the episode scheduled for a later RSS retry, or
- escalate to human_review as a last resort.

The goal is to reduce unnecessary human intervention while staying safe.
"""

from typing import Any

from anime_agent.tools.base import BaseTool
from anime_agent.tools.llm_tool import LLMTool, LLMToolInput
from anime_agent.utils.logger import logger


class ReflectMatchNode:
    """Reflect on low-confidence matches and decide the next step."""

    AUTO_APPROVE_CONFIDENCE = 0.75

    def __init__(self, llm_tool: BaseTool | None = None):
        self.llm_tool = llm_tool or LLMTool()

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Reason about candidates and recommend the next action."""
        logger.info(
            "Reflecting on low-confidence match for episode {} of subscription {}",
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

        # If no candidates at all, broaden search rather than bothering a human.
        if not candidates:
            logger.info("No candidates to reflect on; triggering broader search")
            return {"status": "search_resources"}

        prompt = self._build_prompt(
            candidates=candidates,
            failed_hashes=failed_hashes,
            title_variants=title_variants,
            episode_number=state.get("episode_number", 1),
            low_confidence_count=state.get("low_confidence_count", 0),
        )

        schema = {
            "title": "ReflectMatchResult",
            "description": "Decision after reflecting on uncertain torrent candidates",
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["auto_approve", "search_resources", "wait", "human_review"],
                },
                "info_hash": {"type": "string"},
                "confidence": {"type": "number"},
                "reason": {"type": "string"},
            },
            "required": ["action", "confidence", "reason"],
        }

        result = await self.llm_tool.invoke(
            LLMToolInput(
                prompt=prompt,
                json_schema=schema,
                system_msg=self._system_msg(),
                temperature=0.3,
            )
        )

        if not result.success:
            logger.warning("Reflection LLM failed: {}; escalating to human review", result.error)
            return {"status": "human_review", "requires_human": True}

        decision = result.data.get("json", {})
        action = decision.get("action", "human_review")
        confidence = decision.get("confidence", 0.0)

        if action == "auto_approve" and confidence >= self.AUTO_APPROVE_CONFIDENCE:
            info_hash = decision.get("info_hash", "")
            matched = next((c for c in candidates if c.get("info_hash") == info_hash), None)
            if matched and info_hash not in failed_hashes:
                logger.info(
                    "Auto-approved torrent for episode {}: hash={}, confidence={:.2f}",
                    state.get("episode_number"),
                    info_hash,
                    confidence,
                )
                return {
                    "status": "matched",
                    "matched_torrent": {
                        "info_hash": info_hash,
                        "title": matched.get("title"),
                        "link": matched.get("link"),
                        "confidence": confidence,
                    },
                    "low_confidence_count": 0,
                }

        if action == "search_resources" and not state.get("resource_searched"):
            logger.info("Reflection requested broader search for episode {}", state.get("episode_number"))
            return {"status": "search_resources"}

        if action == "wait":
            logger.info("Reflection decided to wait for better candidates for episode {}", state.get("episode_number"))
            return {"status": "schedule_resume"}

        logger.info(
            "Reflection escalating episode {} to human review (action={}, confidence={:.2f})",
            state.get("episode_number"),
            action,
            confidence,
        )
        return {"status": "human_review", "requires_human": True}

    def _system_msg(self) -> str:
        return (
            "You are a cautious anime torrent matching agent. A previous matcher was uncertain, "
            "so you must re-evaluate the candidates and decide the best next step.\n\n"
            "Rules:\n"
            "1. Only auto_approve if the candidate clearly matches the episode and title.\n"
            "2. Prefer well-known release groups and recent releases.\n"
            "3. If candidates look sparse or off-topic, request search_resources.\n"
            "4. If the episode is very new and RSS may not have caught up, choose wait.\n"
            "5. Choose human_review only when genuinely ambiguous after considering all data.\n\n"
            "Return JSON with action, info_hash (when auto_approve), confidence (0.0-1.0), and reason."
        )

    def _build_prompt(
        self,
        candidates: list[dict[str, Any]],
        failed_hashes: list[str],
        title_variants: list[str],
        episode_number: int,
        low_confidence_count: int,
    ) -> str:
        lines = [
            f"Target anime titles: {' / '.join(title_variants)}",
            f"Target episode: {episode_number}",
            f"Previous low-confidence attempts: {low_confidence_count}",
            f"Already failed hashes: {failed_hashes}",
            "",
            "Candidates:",
        ]
        for idx, candidate in enumerate(candidates, 1):
            size_mb = (candidate.get("size", 0) or 0) / (1024 * 1024)
            lines.append(
                f"{idx}. [{size_mb:.0f}MB] {candidate.get('title')} "
                f"|| source={candidate.get('source', 'unknown')} "
                f"|| hash={candidate.get('info_hash')}"
            )
        lines.extend(
            [
                "",
                "Decide the next action: auto_approve, search_resources, wait, or human_review.",
                "Return JSON: {action, info_hash, confidence, reason}.",
            ]
        )
        return "\n".join(lines)
