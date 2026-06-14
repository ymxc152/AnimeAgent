"""search_resources node — LLM-driven agent for AnimeGarden search."""

from typing import Any

from anime_agent.agents.episode.agent_prompts import (
    SEARCH_RESOURCES_ACTIONS,
    SEARCH_RESOURCES_SYSTEM,
)
from anime_agent.agents.episode.base_agent import BaseAgentNode
from anime_agent.config import Settings, get_settings
from anime_agent.tools.animes_garden_tool import AnimeGardenTool, AnimeGardenToolInput
from anime_agent.tools.base import BaseTool


class SearchResourcesNode(BaseAgentNode):
    """LLM-driven AnimeGarden search agent.

    Instead of fixed title priority and config-driven pagination,
    the LLM decides search strategy adaptively.
    """

    NODE_NAME = "search_resources"
    SYSTEM_PROMPT = SEARCH_RESOURCES_SYSTEM
    ACTIONS = SEARCH_RESOURCES_ACTIONS
    MAX_LLM_CALLS = 2
    TERMINAL_ACTIONS = {"done", "abort", "search", "broaden", "narrow"}

    def __init__(
        self,
        anime_garden_tool: BaseTool | None = None,
        settings: Settings | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.anime_garden_tool = anime_garden_tool or AnimeGardenTool()
        self.settings = settings or get_settings()

    def _build_prompt(self, context: dict[str, Any], state: dict[str, Any]) -> str:
        title_variants = [
            t for t in (
                state.get("title_chinese"),
                state.get("title_romaji"),
                state.get("title_native"),
            ) if t
        ]
        existing_count = len(state.get("torrent_candidates", []))

        history = context.get("history", [])
        history_text = ""
        if history:
            history_text = "\n之前的操作：\n" + "\n".join(
                f"- {h['action']}: {h['result'][:100]}" for h in history
            )

        return (
            f"目标：第 {state.get('episode_number', '?')} 集\n"
            f"标题变体：{title_variants}\n"
            f"已有候选数：{existing_count}\n"
            f"回退搜索是否启用：{self.settings.resource_fallback_enabled}\n"
            f"{history_text}\n\n"
            f"请决定搜索策略。"
        )

    async def _act(self, action: Any, state: dict[str, Any]) -> dict[str, Any]:
        if action.type in ("search", "broaden", "narrow"):
            return await self._execute_search(state, action.type)
        return await super()._act(action, state)

    async def _execute_search(self, state: dict[str, Any], strategy: str) -> dict[str, Any]:
        """Execute AnimeGarden search."""
        if not self.settings.resource_fallback_enabled:
            return {"success": True, "output": "Resource fallback disabled", "candidates": state.get("torrent_candidates", [])}

        title = state.get("title_chinese") or state.get("title_romaji") or state.get("title_native", "")
        if not title:
            return {"success": False, "output": "No title available"}

        existing = {c.get("info_hash") for c in state.get("torrent_candidates", []) if c.get("info_hash")}
        merged = list(state.get("torrent_candidates", []))
        max_pages = 1 if strategy == "narrow" else max(1, self.settings.resource_search_max_pages)

        for page in range(1, max_pages + 1):
            result = await self.anime_garden_tool.invoke(AnimeGardenToolInput(search=title, page=page))
            if not result.success:
                return {"success": False, "output": f"Search failed: {result.error}"}
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

        new_count = len(merged) - len(state.get("torrent_candidates", []))
        return {"success": True, "output": f"Found {new_count} new candidates", "candidates": merged}

    def _build_result(self, action: Any, result: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        if action.type in ("done", "search", "broaden", "narrow") and result.get("success"):
            candidates = result.get("candidates", state.get("torrent_candidates", []))
            return {"status": "searched", "torrent_candidates": candidates, "resource_searched": True}
        if action.type == "abort":
            return {"status": "schedule_resume", "torrent_candidates": state.get("torrent_candidates", [])}
        return {"status": "failed", "errors": [result.get("output", "Search failed")]}

