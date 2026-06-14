"""fetch_rss node — LLM-driven agent for RSS fetching."""

from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from anime_agent.agents.episode.agent_prompts import FETCH_RSS_ACTIONS, FETCH_RSS_SYSTEM
from anime_agent.agents.episode.base_agent import BaseAgentNode
from anime_agent.memory.store import Store
from anime_agent.tools.base import BaseTool
from anime_agent.tools.rss_tool import RSSTool, RSSToolInput


class FetchRSSNode(BaseAgentNode):
    """LLM-driven RSS fetching agent.

    Instead of hardcoded hostname matching, the LLM decides how to
    construct search queries for each RSS source.
    """

    NODE_NAME = "fetch_rss"
    SYSTEM_PROMPT = FETCH_RSS_SYSTEM
    ACTIONS = FETCH_RSS_ACTIONS
    MAX_LLM_CALLS = 2
    TERMINAL_ACTIONS = {"done", "abort", "fetch"}

    def __init__(
        self,
        rss_tool: BaseTool | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.rss_tool = rss_tool or RSSTool()
        self.session_factory = session_factory

    def _build_prompt(self, context: dict[str, Any], state: dict[str, Any]) -> str:
        sources = context.get("sources", [])
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
            f"可用 RSS 源：{len(sources)} 个\n"
            + "\n".join(f"  - {s.name}: {s.url[:60]}..." for s in sources[:5]) + "\n"
            f"已有候选数：{existing_count}\n"
            f"{history_text}\n\n"
            f"请决定抓取策略。"
        )

    async def _load_context(self, state: dict[str, Any]) -> dict[str, Any]:
        sources = await self._get_active_sources(state.get("rss_source_id"))
        return {"sources": sources}

    async def _act(self, action: Any, state: dict[str, Any]) -> dict[str, Any]:
        if action.type == "fetch":
            # Fetch from all sources using the old logic
            return await self._execute_fetch(state)
        return await super()._act(action, state)

    async def _execute_fetch(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute RSS fetching from all active sources."""
        sources = await self._get_active_sources(state.get("rss_source_id"))
        if not sources:
            return {"success": False, "output": "No active RSS sources"}

        merged = list(state.get("torrent_candidates", []))
        existing_hashes = {c.get("info_hash") for c in merged if c.get("info_hash")}

        for source in sources:
            hostname = urlparse(source.url).hostname or ""
            title = self._search_title(state, hostname)
            url = self._build_source_url(source.url, title)
            result = await self.rss_tool.invoke(RSSToolInput(url=url))
            if not result.success:
                continue
            new_entries = result.data.get("entries", [])
            for entry in new_entries:
                info_hash = entry.get("info_hash")
                if info_hash and info_hash in existing_hashes:
                    continue
                entry["rss_source_name"] = source.name
                merged.append(entry)
                if info_hash:
                    existing_hashes.add(info_hash)

        return {
            "success": True,
            "output": f"Fetched {len(merged) - len(state.get('torrent_candidates', []))} new entries",
            "candidates": merged,
        }

    def _build_result(self, action: Any, result: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        if action.type in ("done", "fetch") and result.get("success"):
            candidates = result.get("candidates", state.get("torrent_candidates", []))
            if not candidates:
                return {"status": "waiting_for_rss", "torrent_candidates": []}
            return {"status": "fetching", "torrent_candidates": candidates}
        if action.type == "abort":
            return {"status": "waiting_for_rss", "torrent_candidates": state.get("torrent_candidates", [])}
        return {"status": "failed", "errors": [result.get("output", "RSS fetch failed")]}

    async def _get_active_sources(self, rss_source_id: int | None = None) -> list[Any]:
        if self.session_factory is None:
            return []
        async with self.session_factory() as session:
            store = Store(session)
            if rss_source_id is not None:
                source = await store.rss_sources.get_by_id(rss_source_id)
                if source is not None and source.is_active:
                    return [source]
            return await store.rss_sources.list_active()

    def _search_title(self, state: dict[str, Any], hostname: str) -> str:
        if "nyaa.si" in hostname:
            for key in ("title_romaji", "title_native", "title_chinese"):
                value = state.get(key)
                if isinstance(value, str) and value:
                    return value
        elif "animes.garden" in hostname:
            for key in ("title_chinese", "title_romaji", "title_native"):
                value = state.get(key)
                if isinstance(value, str) and value:
                    return value
        else:
            for key in ("title_romaji", "title_chinese", "title_native"):
                value = state.get(key)
                if isinstance(value, str) and value:
                    return value
        return ""

    def _build_source_url(self, url: str, title: str) -> str:
        if not title:
            return url
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        hostname = parsed.hostname or ""
        if "nyaa.si" in hostname:
            existing = " ".join(query.get("q", []))
            query["q"] = [f"{existing} {title}".strip()]
        elif "animes.garden" in hostname:
            if "search" in query:
                existing = " ".join(query.get("search", []))
                query["search"] = [f"{existing} {title}".strip()]
            else:
                query.setdefault("keyword", [])
                query["keyword"].append(title)
        else:
            return url
        new_query = urlencode(query, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
