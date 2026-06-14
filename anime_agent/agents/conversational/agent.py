"""Minimal conversational agent for status queries."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from anime_agent.agents.conversational.intent import parse_intent
from anime_agent.agents.conversational.reply import format_reply
from anime_agent.services.status_query import StatusQueryService


class ConversationalAgent:
    """Answer natural-language questions about download status.

    The agent is intentionally thin: it parses intent with rules, queries the
    local database via StatusQueryService, and formats a template reply. An
    optional LLM polish layer can be added later without changing the API.
    """

    def __init__(self, session: AsyncSession):
        self.query_service = StatusQueryService(session)

    async def chat(self, user_input: str) -> dict[str, Any]:
        """Process user input and return a reply plus structured intent/data."""
        intent = parse_intent(user_input)

        data: Any = None
        if intent.action == "query_status" and intent.query_type:
            data = await self._query(intent.query_type, intent.title)

        reply = format_reply(intent.query_type or "unknown", data, intent.title)

        return {
            "intent": intent.to_dict(),
            "reply": reply,
            "data": data,
        }

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
