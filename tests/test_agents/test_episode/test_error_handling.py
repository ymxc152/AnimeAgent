"""Tests for unified error handling across all Episode Graph nodes."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from anime_agent.agents.episode.nodes.fetch_rss import FetchRSSNode
from anime_agent.agents.episode.nodes.match_torrent import MatchTorrentNode
from anime_agent.agents.episode.nodes.poll_download import PollDownloadNode
from anime_agent.agents.episode.nodes.send_download import SendDownloadNode
from anime_agent.tools.base import ToolOutput


def _mock_llm(action: str = "abort", **params) -> AsyncMock:
    """Return a mock LLM tool that returns a single JSON action."""
    mock = AsyncMock()
    mock.invoke.return_value = ToolOutput(
        success=True,
        data={"text": json.dumps({"action": action, "reasoning": "test", **params})},
    )
    return mock


@pytest.fixture
def base_state():
    """Create a base state for testing."""
    return {
        "goal_id": "sub_1_ep_1",
        "subscription_id": 1,
        "episode_number": 1,
        "rss_source_id": 1,
        "title_romaji": "Sousou no Frieren",
        "title_native": "葬送のフリーレン",
        "title_chinese": "葬送的芙莉莲",
        "bangumi_data": {},
        "anilist_data": {},
        "tmdb_data": None,
        "torrent_candidates": [],
        "matched_torrent": None,
        "torrent_hash": None,
        "torrent_name": None,
        "torrent_failed_hashes": [],
        "download_files": [],
        "download_progress": 0.0,
        "classification": None,
        "organized_path": None,
        "organized_files": [],
        "emby_refreshed": False,
        "status": "pending",
        "errors": [],
        "requires_human": False,
        "human_input": None,
        "low_confidence_count": 0,
        "resume_after": None,
        "resource_searched": False,
    }


class TestFetchRSSErrorHandling:
    """Test FetchRSSNode error handling."""

    async def test_returns_errors_on_no_source(self, base_state):
        """FetchRSSNode should return errors list when no RSS source."""
        base_state["rss_source_id"] = None

        node = FetchRSSNode(llm_tool=_mock_llm("fetch"))
        result = await node(base_state)

        assert result["status"] == "failed"
        assert "errors" in result
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) > 0

    async def test_returns_errors_on_no_session_factory(self, base_state):
        """FetchRSSNode should return errors list when no session_factory configured."""
        node = FetchRSSNode(llm_tool=_mock_llm("fetch"))
        result = await node(base_state)

        assert result["status"] == "failed"
        assert "errors" in result
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) > 0

    async def test_returns_waiting_on_tool_failure(self, base_state):
        """FetchRSSNode should return failed when all sources fail."""
        from contextlib import asynccontextmanager
        from unittest.mock import patch

        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = MagicMock(
            success=False,
            error="Connection failed",
        )

        mock_source = MagicMock()
        mock_source.url = "http://example.com/rss"
        mock_source.name = "test"

        mock_session = AsyncMock()
        mock_store = MagicMock()
        mock_store.rss_sources.list_active = AsyncMock(return_value=[mock_source])
        mock_store.rss_sources.get_by_id = AsyncMock(return_value=None)

        @asynccontextmanager
        async def _factory():
            yield mock_session

        with patch("anime_agent.agents.episode.nodes.fetch_rss.Store", return_value=mock_store):
            node = FetchRSSNode(rss_tool=mock_tool, session_factory=_factory, llm_tool=_mock_llm("fetch"))
            result = await node(base_state)

        # When all sources fail, status is waiting_for_rss
        assert result["status"] == "waiting_for_rss"
        assert "torrent_candidates" in result


class TestMatchTorrentErrorHandling:
    """Test MatchTorrentNode error handling."""

    async def test_returns_errors_on_llm_failure(self, base_state):
        """MatchTorrentNode should return errors list when LLM fails."""
        base_state["torrent_candidates"] = [
            {"info_hash": "abc123", "title": "test", "link": "magnet:?xt=urn:btih:abc123"},
        ]

        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = ToolOutput(success=False, error="LLM service unavailable")

        node = MatchTorrentNode(llm_tool=mock_llm)
        result = await node(base_state)

        assert result["status"] == "failed"
        assert "errors" in result
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) > 0


class TestSendDownloadErrorHandling:
    """Test SendDownloadNode error handling."""

    async def test_returns_errors_on_no_torrent(self, base_state):
        """SendDownloadNode should return errors list when no matched torrent."""
        base_state["matched_torrent"] = None

        node = SendDownloadNode(llm_tool=_mock_llm())
        result = await node(base_state)

        assert result["status"] == "failed"
        assert "errors" in result
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) > 0

    async def test_returns_errors_on_already_failed(self, base_state):
        """SendDownloadNode should return errors list when hash already failed."""
        base_state["matched_torrent"] = {
            "info_hash": "abc123",
            "title": "test",
            "link": "magnet:?xt=urn:btih:abc123",
        }
        base_state["torrent_failed_hashes"] = ["abc123"]

        node = SendDownloadNode(llm_tool=_mock_llm())
        result = await node(base_state)

        assert result["status"] == "failed"
        assert "errors" in result
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) > 0

    async def test_returns_errors_on_no_link(self, base_state):
        """SendDownloadNode should return errors list when no download link."""
        base_state["matched_torrent"] = {
            "info_hash": "abc123",
            "title": "test",
            "link": None,
        }

        node = SendDownloadNode(llm_tool=_mock_llm())
        result = await node(base_state)

        assert result["status"] == "failed"
        assert "errors" in result
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) > 0

    async def test_returns_errors_on_tool_failure(self, base_state):
        """SendDownloadNode should return errors list when tool fails."""
        base_state["matched_torrent"] = {
            "info_hash": "abc123",
            "title": "test",
            "link": "magnet:?xt=urn:btih:abc123",
        }

        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = MagicMock(
            success=False,
            error="qBittorrent connection failed",
        )

        node = SendDownloadNode(qb_tool=mock_tool, llm_tool=_mock_llm("abort"))
        result = await node(base_state)

        assert result["status"] == "failed"
        assert "errors" in result
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) > 0


class TestPollDownloadErrorHandling:
    """Test PollDownloadNode error handling."""

    async def test_returns_errors_on_no_hash(self, base_state):
        """PollDownloadNode should return errors list when no torrent hash."""
        base_state["torrent_hash"] = None

        node = PollDownloadNode(llm_tool=_mock_llm())
        result = await node(base_state)

        assert result["status"] == "failed"
        assert "errors" in result
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) > 0

    async def test_returns_errors_on_tool_failure(self, base_state):
        """PollDownloadNode should handle tool failure gracefully and return a valid result."""
        base_state["torrent_hash"] = "abc123"

        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = MagicMock(
            success=False,
            error="qBittorrent connection failed",
        )

        node = PollDownloadNode(qb_tool=mock_tool, llm_tool=_mock_llm("switch"))
        result = await node(base_state)

        assert result["status"] == "retry_match"
        assert "abc123" in result["torrent_failed_hashes"]
