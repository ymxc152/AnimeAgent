"""Extended tests for ConversationalAgent — all query types."""

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
def agent(mock_query_service, db_session):
    a = ConversationalAgent(db_session)
    a.query_service = mock_query_service
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

    async def test_unknown_input(self, agent):
        result = await agent.chat("今天天气怎么样")
        assert "intent" in result
        assert "reply" in result

    async def test_returns_intent_and_data(self, agent):
        result = await agent.chat("我在追哪些番")
        assert "intent" in result
        assert "reply" in result
        assert "data" in result
        assert isinstance(result["data"], list)
