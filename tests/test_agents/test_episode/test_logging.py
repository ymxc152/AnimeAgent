"""Tests for logging in Episode Graph nodes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anime_agent.agents.episode.nodes.fetch_rss import FetchRSSNode
from anime_agent.agents.episode.nodes.match_torrent import MatchTorrentNode
from anime_agent.agents.episode.nodes.poll_download import PollDownloadNode
from anime_agent.agents.episode.nodes.send_download import SendDownloadNode


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


class TestFetchRSSLogging:
    """Test FetchRSSNode logging."""

    @patch("anime_agent.agents.episode.nodes.fetch_rss.logger")
    async def test_logs_on_success(self, mock_logger, base_state):
        """FetchRSSNode should log on success."""
        from contextlib import asynccontextmanager
        from unittest.mock import patch as _patch

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

        with _patch("anime_agent.agents.episode.nodes.fetch_rss.Store", return_value=mock_store):
            node = FetchRSSNode(rss_tool=mock_tool, session_factory=_factory)
            await node(base_state)

        # Should log entry and exit
        assert mock_logger.info.call_count >= 2

    @patch("anime_agent.agents.episode.nodes.fetch_rss.logger")
    async def test_logs_on_failure(self, mock_logger, base_state):
        """FetchRSSNode should log on failure."""
        node = FetchRSSNode()
        await node(base_state)

        # Should log entry and error
        assert mock_logger.info.call_count >= 1
        assert mock_logger.error.call_count >= 1


class TestMatchTorrentLogging:
    """Test MatchTorrentNode logging."""

    @patch("anime_agent.agents.episode.nodes.match_torrent.logger")
    async def test_logs_on_match(self, mock_logger, base_state):
        """MatchTorrentNode should log on match."""
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
        await node(base_state)

        # Should log entry and exit
        assert mock_logger.info.call_count >= 2

    @patch("anime_agent.agents.episode.nodes.match_torrent.logger")
    async def test_logs_on_no_match(self, mock_logger, base_state):
        """MatchTorrentNode should log on no match."""
        base_state["torrent_candidates"] = []

        mock_selector = AsyncMock()
        mock_selector.select.return_value = MagicMock(
            success=True,
            data={"matched": False, "reason": "No candidates after pre-filtering"},
        )

        node = MatchTorrentNode(selector=mock_selector)
        await node(base_state)

        # Should log entry and exit
        assert mock_logger.info.call_count >= 2


class TestSendDownloadLogging:
    """Test SendDownloadNode logging."""

    @patch("anime_agent.agents.episode.nodes.send_download.logger")
    async def test_logs_on_success(self, mock_logger, base_state):
        """SendDownloadNode should log on success."""
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
        await node(base_state)

        # Should log entry and exit
        assert mock_logger.info.call_count >= 2

    @patch("anime_agent.agents.episode.nodes.send_download.logger")
    async def test_logs_on_failure(self, mock_logger, base_state):
        """SendDownloadNode should log on failure."""
        base_state["matched_torrent"] = None

        node = SendDownloadNode()
        await node(base_state)

        # Should log entry and error
        assert mock_logger.info.call_count >= 1
        assert mock_logger.error.call_count >= 1


class TestPollDownloadLogging:
    """Test PollDownloadNode logging."""

    @patch("anime_agent.agents.episode.nodes.poll_download.logger")
    async def test_logs_on_progress(self, mock_logger, base_state):
        """PollDownloadNode should log on progress."""
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
        await node(base_state)

        # Should log entry and exit
        assert mock_logger.info.call_count >= 2

    @patch("anime_agent.agents.episode.nodes.poll_download.logger")
    async def test_logs_on_complete(self, mock_logger, base_state):
        """PollDownloadNode should log on complete."""
        base_state["torrent_hash"] = "abc123"

        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = MagicMock(
            success=True,
            data={
                "status": {
                    "progress": 1.0,
                    "name": "test.mkv",
                    "content_path": "/downloads/test.mkv",
                },
            },
        )

        node = PollDownloadNode(qb_tool=mock_tool)
        await node(base_state)

        # Should log entry and exit
        assert mock_logger.info.call_count >= 2

    @patch("anime_agent.agents.episode.nodes.poll_download.logger")
    async def test_logs_on_failure(self, mock_logger, base_state):
        """PollDownloadNode should log on failure."""
        base_state["torrent_hash"] = None

        node = PollDownloadNode()
        await node(base_state)

        # Should log entry and error
        assert mock_logger.info.call_count >= 1
        assert mock_logger.error.call_count >= 1
