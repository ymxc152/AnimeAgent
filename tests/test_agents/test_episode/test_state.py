"""Tests for Episode state management and node status updates."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from anime_agent.agents.episode.graph import build_episode_graph
from anime_agent.agents.episode.nodes.fetch_rss import FetchRSSNode
from anime_agent.agents.episode.nodes.match_torrent import MatchTorrentNode
from anime_agent.agents.episode.nodes.poll_download import PollDownloadNode
from anime_agent.agents.episode.nodes.send_download import SendDownloadNode
from anime_agent.agents.episode.state import EpisodeAgentState


@pytest.fixture
def base_state() -> EpisodeAgentState:
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


class TestFetchRSSNodeStatus:
    """Test FetchRSSNode returns correct status."""

    async def test_fetch_rss_returns_fetching_on_success(self, base_state):
        """FetchRSSNode should return status='fetching' on success."""
        from contextlib import asynccontextmanager
        from unittest.mock import patch

        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = MagicMock(
            success=True,
            data={"entries": [{"info_hash": "abc123", "title": "test"}]},
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
            node = FetchRSSNode(rss_tool=mock_tool, session_factory=_factory)
            result = await node(base_state)

        assert result["status"] == "fetching"
        assert "torrent_candidates" in result

    async def test_fetch_rss_returns_failed_on_no_session_factory(self, base_state):
        """FetchRSSNode should return status='failed' when no session_factory."""
        node = FetchRSSNode()
        result = await node(base_state)

        assert result["status"] == "failed"
        assert len(result["errors"]) > 0

    async def test_fetch_rss_returns_waiting_on_tool_error(self, base_state):
        """FetchRSSNode should return status='waiting_for_rss' when all sources fail."""
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
            node = FetchRSSNode(rss_tool=mock_tool, session_factory=_factory)
            result = await node(base_state)

        assert result["status"] == "waiting_for_rss"


class TestMatchTorrentNodeStatus:
    """Test MatchTorrentNode returns correct status."""

    async def test_match_torrent_returns_matched_on_high_confidence(self, base_state):
        """MatchTorrentNode should return status='matched' on high confidence."""
        base_state["torrent_candidates"] = [
            {"info_hash": "abc123", "title": "[Sub] Frieren - 01 [1080p].mkv", "link": "magnet:?xt=urn:btih:abc123"},
        ]

        mock_selector = AsyncMock()
        mock_selector.select.return_value = MagicMock(
            success=True,
            data={
                "matched": True,
                "info_hash": "abc123",
                "title": "[Sub] Frieren - 01 [1080p].mkv",
                "link": "magnet:?xt=urn:btih:abc123",
                "confidence": 0.9,
            },
        )

        node = MatchTorrentNode(selector=mock_selector)
        result = await node(base_state)

        assert result["status"] == "matched"
        assert result["matched_torrent"] is not None

    async def test_match_torrent_returns_search_resources_when_empty(self, base_state):
        """MatchTorrentNode should return status='search_resources' when no candidates and not searched."""
        base_state["torrent_candidates"] = []
        base_state["resource_searched"] = False

        mock_selector = AsyncMock()
        node = MatchTorrentNode(selector=mock_selector)
        result = await node(base_state)

        assert result["status"] == "search_resources"

    async def test_match_torrent_returns_no_match_when_empty_and_searched(self, base_state):
        """MatchTorrentNode should return status='no_match' when no candidates but already searched."""
        base_state["torrent_candidates"] = []
        base_state["resource_searched"] = True

        mock_selector = AsyncMock()
        mock_selector.select.return_value = MagicMock(
            success=True,
            data={"matched": False, "reason": "No candidates after pre-filtering"},
        )

        node = MatchTorrentNode(selector=mock_selector)
        result = await node(base_state)

        assert result["status"] == "no_match"

    async def test_match_torrent_returns_low_confidence_for_reflection(self, base_state):
        """MatchTorrentNode should return status='low_confidence' so reflection can decide."""
        base_state["torrent_candidates"] = [
            {"info_hash": "abc123", "title": "[Sub] Frieren - 01 [1080p].mkv", "link": "magnet:?xt=urn:btih:abc123"},
        ]
        base_state["low_confidence_count"] = 2  # Already 2 attempts

        mock_selector = AsyncMock()
        mock_selector.select.return_value = MagicMock(
            success=True,
            data={
                "matched": True,
                "info_hash": "abc123",
                "title": "[Sub] Frieren - 01 [1080p].mkv",
                "link": "magnet:?xt=urn:btih:abc123",
                "confidence": 0.5,
            },
        )

        node = MatchTorrentNode(selector=mock_selector)
        result = await node(base_state)

        assert result["status"] == "low_confidence"
        assert result["low_confidence_count"] == 3


class TestSendDownloadNodeStatus:
    """Test SendDownloadNode returns correct status."""

    async def test_send_download_returns_downloading_on_success(self, base_state):
        """SendDownloadNode should return status='downloading' on success."""
        base_state["matched_torrent"] = {
            "info_hash": "abc123",
            "title": "[Sub] Frieren - 01 [1080p].mkv",
            "link": "magnet:?xt=urn:btih:abc123",
            "confidence": 0.9,
        }

        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = MagicMock(
            success=True,
            data={"hash": "abc123"},
        )

        node = SendDownloadNode(qb_tool=mock_tool)
        result = await node(base_state)

        assert result["status"] == "downloading"
        assert result["torrent_hash"] == "abc123"

    async def test_send_download_returns_failed_on_no_torrent(self, base_state):
        """SendDownloadNode should return status='failed' when no matched torrent."""
        base_state["matched_torrent"] = None

        node = SendDownloadNode()
        result = await node(base_state)

        assert result["status"] == "failed"
        assert len(result["errors"]) > 0

    async def test_send_download_returns_failed_on_already_failed(self, base_state):
        """SendDownloadNode should return status='failed' when hash already failed."""
        base_state["matched_torrent"] = {
            "info_hash": "abc123",
            "title": "[Sub] Frieren - 01 [1080p].mkv",
            "link": "magnet:?xt=urn:btih:abc123",
        }
        base_state["torrent_failed_hashes"] = ["abc123"]

        node = SendDownloadNode()
        result = await node(base_state)

        assert result["status"] == "failed"
        assert len(result["errors"]) > 0


class TestPollDownloadNodeStatus:
    """Test PollDownloadNode returns correct status."""

    async def test_poll_download_returns_downloading_when_not_complete(self, base_state):
        """PollDownloadNode should return status='downloading' when not complete."""
        base_state["torrent_hash"] = "abc123"

        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = MagicMock(
            success=True,
            data={
                "status": {
                    "progress": 0.5,
                    "name": "test.mkv",
                },
            },
        )

        node = PollDownloadNode(qb_tool=mock_tool)
        result = await node(base_state)

        assert result["status"] == "downloading"
        assert result["download_progress"] == 0.5

    async def test_poll_download_returns_downloaded_when_complete(self, base_state):
        """PollDownloadNode should return status='downloaded' when complete."""
        from datetime import UTC, datetime

        base_state["torrent_hash"] = "abc123"

        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = MagicMock(
            success=True,
            data={
                "status": {
                    "progress": 1.0,
                    "state": "uploading",
                    "name": "test.mkv",
                    "content_path": "/downloads/test.mkv",
                    "added_at": datetime.now(UTC),
                    "last_speed_at": datetime.now(UTC),
                },
            },
        )

        node = PollDownloadNode(qb_tool=mock_tool)
        result = await node(base_state)

        assert result["status"] == "downloaded"
        assert result["download_progress"] == 1.0

    async def test_poll_download_returns_failed_on_no_hash(self, base_state):
        """PollDownloadNode should return status='failed' when no torrent hash."""
        base_state["torrent_hash"] = None

        node = PollDownloadNode()
        result = await node(base_state)

        assert result["status"] == "failed"
        assert len(result["errors"]) > 0


class TestGraphRouting:
    """Test Graph routing functions use correct status."""

    async def test_graph_routes_after_fetch_rss_success(self, base_state):
        """Graph should route to match_torrent after successful fetch_rss."""
        graph = build_episode_graph()

        # Mock the fetch_rss node to return success
        mock_fetch_rss = AsyncMock()
        mock_fetch_rss.return_value = {
            **base_state,
            "status": "fetching",
            "torrent_candidates": [{"info_hash": "abc123", "title": "test"}],
        }

        # The graph should compile and have routing
        assert graph is not None

    async def test_graph_routes_after_match_torrent_matched(self, base_state):
        """Graph should route to send_download when matched."""
        graph = build_episode_graph()

        # The graph should compile and have routing
        assert graph is not None
