"""match_torrent node — LLM-driven agent for torrent selection."""

from typing import Any

from anime_agent.agents.episode.agent_prompts import (
    MATCH_TORRENT_ACTIONS,
    MATCH_TORRENT_SYSTEM,
)
from anime_agent.agents.episode.base_agent import BaseAgentNode
from anime_agent.services.torrent_selector import TorrentSelector
from anime_agent.tools.base import BaseTool
from anime_agent.utils.logger import logger


class MatchTorrentNode(BaseAgentNode):
    """LLM-driven torrent matching agent.

    Instead of hardcoded confidence thresholds, the LLM dynamically decides
    whether to select a candidate, search for more, or abort.
    """

    NODE_NAME = "match_torrent"
    SYSTEM_PROMPT = MATCH_TORRENT_SYSTEM
    ACTIONS = MATCH_TORRENT_ACTIONS
    MAX_LLM_CALLS = 3
    TERMINAL_ACTIONS = {"select", "search_more", "abort"}

    def __init__(
        self,
        selector: TorrentSelector | None = None,
        llm_tool: BaseTool | None = None,
        **kwargs: Any,
    ):
        super().__init__(llm_tool=llm_tool, **kwargs)
        self.selector = selector or TorrentSelector(llm_tool=self.llm_tool)

    def _build_prompt(self, context: dict[str, Any], state: dict[str, Any]) -> str:
        candidates = state.get("torrent_candidates", [])
        failed_hashes = state.get("torrent_failed_hashes", [])
        episode = state.get("episode_number", 1)
        title_variants = [
            t for t in (
                state.get("title_romaji"),
                state.get("title_chinese"),
                state.get("title_native"),
            ) if t
        ]

        # Pre-filter candidates using existing selector logic
        prefiltered = self.selector._prefilter(
            candidates, episode, title_variants, failed_hashes
        )

        if not prefiltered:
            if not state.get("resource_searched"):
                return (
                    f"第 {episode} 集没有找到任何候选种子。\n"
                    f"标题变体：{title_variants}\n"
                    f"请决定下一步。"
                )
            return (
                f"第 {episode} 集没有找到匹配的候选种子，且已经搜索过资源。\n"
                f"标题变体：{title_variants}\n"
                f"请决定下一步。"
            )

        # Format candidates for LLM
        candidate_lines = []
        for i, c in enumerate(prefiltered[:10], 1):
            candidate_lines.append(
                f"{i}. hash={c.get('info_hash', '?')[:12]}... "
                f"title={c.get('title', '?')[:60]} "
                f"size={c.get('size', '?')}"
            )

        history = context.get("history", [])
        history_text = ""
        if history:
            history_text = "\n之前的操作：\n" + "\n".join(
                f"- {h['action']}: {h['result'][:100]}" for h in history
            )

        return (
            f"目标：第 {episode} 集\n"
            f"标题变体：{title_variants}\n"
            f"已过滤候选（{len(prefiltered)} 个）：\n"
            + "\n".join(candidate_lines)
            + f"\n已失败的 hash：{failed_hashes}"
            f"{history_text}\n\n"
            f"请选择最佳种子或决定下一步。"
        )

    async def _act(self, action: Any, state: dict[str, Any]) -> dict[str, Any]:
        if action.type == "select":
            info_hash = action.params.get("info_hash", "")
            candidates = state.get("torrent_candidates", [])
            # Find the full candidate by hash prefix
            matched = None
            for c in candidates:
                if c.get("info_hash", "").startswith(info_hash):
                    matched = c
                    break
            if matched:
                return {"success": True, "matched": matched}
            return {"success": False, "output": f"Candidate with hash {info_hash} not found"}

        if action.type == "search_more":
            return {"success": True, "output": "Triggering resource search"}

        return await super()._act(action, state)

    def _build_result(self, action: Any, result: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        if action.type == "select" and result.get("matched"):
            matched = result["matched"]
            confidence = matched.get("confidence", 0.9)
            logger.info(
                "MatchTorrent agent selected: hash={}, confidence={:.2f}",
                matched.get("info_hash"),
                confidence,
            )
            return {
                "status": "matched",
                "matched_torrent": {
                    "info_hash": matched.get("info_hash"),
                    "title": matched.get("title"),
                    "link": matched.get("link"),
                    "confidence": confidence,
                },
                "low_confidence_count": 0,
            }

        if action.type == "search_more":
            return {
                "status": "search_resources",
                "matched_torrent": None,
            }

        # abort
        return {
            "status": "no_match",
            "matched_torrent": None,
        }

