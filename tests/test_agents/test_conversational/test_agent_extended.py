"""Extended tests for ConversationalAgent — session management and all actions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from anime_agent.agents.conversational.agent import ConversationalAgent


@pytest.fixture
def mock_query_service():
    service = MagicMock()
    service.list_active = AsyncMock(return_value=[{"title": "Frieren", "total_episodes": 28, "completed": 10, "failed": 0}])
    service.subscription_detail = AsyncMock(return_value={"title": "Frieren", "total_episodes": 28, "completed": 10, "failed": 0, "pending": 18})
    service.pending_torrents = AsyncMock(return_value=[{"title": "Frieren", "episode_number": 5, "status": "waiting_for_rss"}])
    service.anime_info = AsyncMock(return_value={"title": "Frieren", "total_episodes": 28, "season": "FALL", "season_year": 2023})
    service.failed_tasks = AsyncMock(return_value=[{"title": "Frieren", "episode_number": 5, "error_log": "timeout"}])
    return service


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.chat_messages.create = AsyncMock()
    store.chat_messages.list_by_session = AsyncMock(return_value=[])
    return store


@pytest.fixture
def agent(db_session, mock_query_service, mock_store):
    a = ConversationalAgent.__new__(ConversationalAgent)
    a.session = db_session
    a.store = mock_store
    a.query_service = mock_query_service
    a.llm_tool = None
    a.resolver = MagicMock()
    return a


class TestConversationalAgentChat:
    async def test_list_active(self, agent, mock_query_service):
        result = await agent.chat("我在追哪些番")
        assert "Frieren" in result["reply"]
        mock_query_service.list_active.assert_called_once()

    async def test_subscription_detail(self, agent, mock_query_service):
        result = await agent.chat("葬送的芙莉莲进度怎么样")
        assert "Frieren" in result["reply"]
        mock_query_service.subscription_detail.assert_called_once()

    async def test_pending_torrents(self, agent, mock_query_service):
        result = await agent.chat("有什么在等种子")
        assert "Frieren" in result["reply"]
        mock_query_service.pending_torrents.assert_called_once()

    async def test_anime_info(self, agent, mock_query_service):
        result = await agent.chat("葬送的芙莉莲有多少集")
        assert "Frieren" in result["reply"]
        mock_query_service.anime_info.assert_called_once()

    async def test_failed_tasks(self, agent, mock_query_service):
        result = await agent.chat("最近有什么失败的任务")
        assert "Frieren" in result["reply"]
        mock_query_service.failed_tasks.assert_called_once()

    async def test_help(self, agent):
        result = await agent.chat("帮助")
        assert "追番" in result["reply"] or "订阅" in result["reply"]

    async def test_unknown_input(self, agent):
        result = await agent.chat("今天天气怎么样")
        assert "intent" in result
        assert "reply" in result
        assert result["intent"]["action"] == "unknown"

    async def test_returns_session_id(self, agent):
        result = await agent.chat("帮助", session_id="test123")
        assert result["session_id"] == "test123"

    async def test_generates_session_id(self, agent):
        result = await agent.chat("帮助")
        assert "session_id" in result
        assert len(result["session_id"]) > 0

    async def test_saves_messages(self, agent, mock_store):
        await agent.chat("帮助")
        assert mock_store.chat_messages.create.call_count == 2  # user + assistant


class TestConversationalAgentLLMFallback:
    async def test_uses_llm_for_unknown(self, db_session, mock_store):
        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = MagicMock(
            success=True,
            data={"json": {"action": "query_status", "query_type": "list_active", "title": None}},
        )

        mock_qs = MagicMock()
        mock_qs.list_active = AsyncMock(return_value=[{"title": "Test", "total_episodes": 12, "completed": 5, "failed": 0}])

        a = ConversationalAgent.__new__(ConversationalAgent)
        a.session = db_session
        a.store = mock_store
        a.query_service = mock_qs
        a.llm_tool = mock_llm
        a.resolver = MagicMock()

        await a.chat("随便问点什么")
        assert mock_llm.invoke.called
