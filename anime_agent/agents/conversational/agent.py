"""Conversational agent with multi-turn dialogue, LLM polish, and subscribe flow."""

from __future__ import annotations

import json
import uuid
from typing import Any, cast

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from anime_agent.agents.conversational.intent import ParsedIntent, parse_intent
from anime_agent.agents.conversational.reply import format_reply, llm_polish
from anime_agent.memory.store import Store
from anime_agent.services.metadata_resolver import MetadataResolver
from anime_agent.services.status_query import StatusQueryService
from anime_agent.tools.llm_tool import LLMTool, LLMToolInput

# Chat state constants (persisted in intent_json.chat_state)
STATE_IDLE = "idle"
STATE_CONFIRMING = "confirming"


class ConversationalAgent:
    """Multi-turn conversational agent for anime management.

    Supports:
    - Status queries (list, detail, pending, failed, info)
    - Natural language subscription (search → confirm)
    - Episode retry
    - Help
    - LLM-powered intent classification for unknown inputs
    - LLM-powered reply polish
    """

    def __init__(
        self,
        session: AsyncSession,
        llm_tool: LLMTool | None = None,
    ):
        self.session = session
        self.store = Store(session)
        self.query_service = StatusQueryService(session)
        self.llm_tool = llm_tool
        self.resolver = MetadataResolver()

    async def chat(
        self,
        user_input: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Process user input and return a reply with session management."""
        if not session_id:
            session_id = uuid.uuid4().hex[:16]

        # 1. Save user message
        await self.store.chat_messages.create(
            session_id=session_id, role="user", content=user_input
        )

        # 2. Load recent history for context
        history_msgs = await self.store.chat_messages.list_by_session(session_id, limit=20)
        history = [{"role": str(m.role), "content": str(m.content)} for m in history_msgs]

        # 3. Determine current chat state from last assistant message
        chat_state = STATE_IDLE
        last_assistant = _last_assistant_message(history_msgs)
        if last_assistant and last_assistant.intent_json:
            try:
                prev_intent = json.loads(last_assistant.intent_json)
                chat_state = prev_intent.get("chat_state", STATE_IDLE)
            except (json.JSONDecodeError, TypeError):
                pass

        # 4. Parse intent
        intent = parse_intent(user_input)

        # If we're in CONFIRMING state and user picked a number → treat as select
        if (
            chat_state == STATE_CONFIRMING
            and intent.action != "select_candidate"
            and self.llm_tool
            and intent.action == "unknown"
        ):
            # Try LLM classification for ambiguous confirm responses
            intent = await self._llm_classify_intent(user_input, history)

        # 5. LLM intent classification for unknown (when in IDLE)
        if intent.action == "unknown" and self.llm_tool:
            intent = await self._llm_classify_intent(user_input, history)

        # 6. Dispatch
        data: Any = None
        next_state = STATE_IDLE

        if intent.action == "query_status" and intent.query_type:
            data = await self._query(intent.query_type, intent.title)

        elif intent.action == "subscribe":
            data, next_state = await self._handle_subscribe(intent.title)

        elif intent.action == "select_candidate":
            data = await self._handle_select(intent.selection_index, history_msgs)
            if data and data.get("success"):
                next_state = STATE_IDLE
            elif data is None:
                next_state = STATE_CONFIRMING  # keep waiting

        elif intent.action == "retry_episode":
            data = await self._handle_retry(intent.title, intent.episode_number)

        elif intent.action == "help":
            pass  # format_reply handles help directly

        # 7. Format reply
        reply = format_reply(
            action=intent.action,
            data=data,
            title=intent.title,
            query_type=intent.query_type,
        )

        # 8. LLM polish (if available)
        if self.llm_tool and intent.action not in ("unknown",):
            polished = await llm_polish(
                self.llm_tool,
                user_input,
                reply,
                data,
                history=history,
            )
            if polished:
                reply = polished

        # 9. Save assistant message with intent + state
        intent_dict = intent.to_dict()
        intent_dict["chat_state"] = next_state
        await self.store.chat_messages.create(
            session_id=session_id,
            role="assistant",
            content=reply,
            intent_json=json.dumps(intent_dict, ensure_ascii=False),
            data_json=json.dumps(data, ensure_ascii=False, default=str)
            if data is not None
            else None,
        )

        return {
            "session_id": session_id,
            "reply": reply,
            "intent": intent_dict,
            "data": data,
        }

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------

    async def _query(self, query_type: str, title: str | None) -> Any:
        if query_type == "list_active":
            return await self.query_service.list_active()
        if query_type == "subscription_detail":
            return await self.query_service.subscription_detail(title or "")
        if query_type == "pending_torrents":
            return await self.query_service.pending_torrents()
        if query_type == "anime_info":
            return await self.query_service.anime_info(title or "")
        if query_type == "failed_tasks":
            return await self.query_service.failed_tasks()
        return None

    async def _handle_subscribe(self, title: str | None) -> tuple[Any, str]:
        """Search for anime candidates and enter CONFIRMING state."""
        if not title:
            return None, STATE_IDLE

        try:
            result = await self.resolver.search(title)
            if result.success:
                candidates = result.data.get("candidates", [])
                return candidates, STATE_CONFIRMING if candidates else STATE_IDLE
        except Exception as exc:  # noqa: BLE001
            logger.warning("Anime search failed: {}", exc)

        return [], STATE_IDLE

    async def _handle_select(
        self,
        selection_index: int | None,
        history_msgs: list[Any],
    ) -> dict[str, Any] | None:
        """Handle candidate selection from CONFIRMING state."""
        if selection_index is None:
            return None

        # Find last assistant message with candidates
        candidates = _last_candidates(history_msgs)
        if not candidates:
            return None

        idx = selection_index - 1  # 1-indexed → 0-indexed
        if idx < 0 or idx >= len(candidates):
            return {"success": False, "error": "选择超出范围"}

        chosen = candidates[idx]

        # Create subscription using web.py helper
        try:
            from anime_agent.web_schemas import DiscoverySubscribeRequest

            payload = DiscoverySubscribeRequest(
                anilist_id=chosen.get("anilist_id"),
                bangumi_id=chosen.get("bangumi_id"),
                tmdb_id=chosen.get("tmdb_id"),
                title_romaji=chosen.get("title_romaji", "Unknown"),
                title_native=chosen.get("title_native"),
                title_chinese=chosen.get("title_chinese"),
                total_episodes=chosen.get("total_episodes"),
                season_year=chosen.get("season_year"),
                season=chosen.get("season"),
            )

            from anime_agent.web import _create_subscription_from_payload

            sub = await _create_subscription_from_payload(self.session, payload, source="chat")
            title = sub.title_chinese or sub.title_native or sub.title_romaji
            return {
                "success": True,
                "title": title,
                "subscription_id": sub.id,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Subscribe failed: {}", exc)
            return {"success": False, "error": str(exc)}

    async def _handle_retry(self, title: str | None, episode_number: int | None) -> dict[str, Any]:
        """Reset an episode to pending for retry."""
        if not title:
            return {"success": False, "error": "请指定要重试的番名"}

        sub = await self.query_service._find_subscription_by_title(title)
        if sub is None:
            return {"success": False, "error": "未找到订阅"}

        if episode_number is not None:
            ep = await self.store.episodes.get_by_subscription_and_number(
                cast(int, sub.id), episode_number
            )
            if ep:
                ep_any = cast(Any, ep)
                ep_any.status = "pending"
                ep_any.torrent_hash = None
                ep_any.torrent_name = None
                ep_any.torrent_link = None
                ep_any.error_log = None
                await self.store.episodes.update(ep)
                return {
                    "success": True,
                    "title": sub.title_chinese or sub.title_romaji,
                    "episode_number": episode_number,
                }

        # Retry all failed episodes
        episodes = await self.store.episodes.list_by_subscription(cast(int, sub.id))
        retried = 0
        for ep in episodes:
            if ep.status in ("failed", "human_review"):
                ep_any = cast(Any, ep)
                ep_any.status = "pending"
                ep_any.torrent_hash = None
                ep_any.torrent_name = None
                ep_any.torrent_link = None
                ep_any.error_log = None
                await self.store.episodes.update(ep)
                retried += 1

        return {
            "success": retried > 0,
            "title": sub.title_chinese or sub.title_romaji,
            "retried_count": retried,
        }

    # ------------------------------------------------------------------
    # LLM intent classification (unknown fallback)
    # ------------------------------------------------------------------

    _CLASSIFY_SYSTEM = (
        "你是一个意图分类器。根据用户输入，返回 JSON 格式的意图分类。\n"
        "可选的 action: query_status, subscribe, retry_episode, help, chitchat\n"
        "可选的 query_type (仅 action=query_status): "
        "list_active, subscription_detail, pending_torrents, anime_info, failed_tasks\n"
        '返回格式: {"action": "...", "query_type": "...", "title": "..."}\n'
        "如果没有标题，title 设为 null。只返回 JSON，不要其他内容。"
    )

    async def _llm_classify_intent(
        self, user_input: str, history: list[dict[str, str]]
    ) -> ParsedIntent:
        """Use LLM to classify intent when rules fail."""
        try:
            result = await self.llm_tool.invoke(  # type: ignore[union-attr]
                LLMToolInput(
                    prompt=f"用户输入：{user_input}",
                    system_msg=self._CLASSIFY_SYSTEM,
                    temperature=0.1,
                    json_schema={"type": "object"},
                )
            )
            if result.success and result.data:
                obj = result.data.get("json", {})
                action = obj.get("action", "unknown")
                if action == "chitchat":
                    return ParsedIntent("unknown")
                return ParsedIntent(
                    action=action,
                    query_type=obj.get("query_type"),
                    title=obj.get("title"),
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("LLM intent classification failed: {}", exc)

        return ParsedIntent("unknown")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _last_assistant_message(messages: list[Any]) -> Any:
    """Return the most recent assistant message, or None."""
    for msg in reversed(messages):
        if msg.role == "assistant":
            return msg
    return None


def _last_candidates(messages: list[Any]) -> list[dict[str, Any]]:
    """Extract candidates list from the last assistant message's data_json."""
    for msg in reversed(messages):
        if msg.role == "assistant" and msg.data_json:
            try:
                data = json.loads(msg.data_json)
                if isinstance(data, list) and data:
                    return data
            except (json.JSONDecodeError, TypeError):
                pass
    return []
