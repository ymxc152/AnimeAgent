"""Tests for fetch_rss node."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anime_agent.agents.episode.nodes.fetch_rss import FetchRSSNode
from anime_agent.tools.base import ToolOutput


def _state(rss_source_id: int | None = 1) -> dict:
    return {
        "subscription_id": 42,
        "episode_number": 1,
        "title_romaji": "Sousou no Frieren",
        "title_native": "葬送のフリーレン",
        "title_chinese": "葬送的芙莉莲",
        "torrent_candidates": [],
        "rss_source_id": rss_source_id,
    }


def _make_mock_source(url: str = "https://example.com/rss", name: str = "test"):
    source = MagicMock()
    source.url = url
    source.name = name
    return source


@pytest.fixture
def mock_store():
    """Patch Store globally and return the mock instance."""
    mock = MagicMock()
    rss_sources = AsyncMock()
    rss_sources.list_active = AsyncMock(return_value=[])
    mock.rss_sources = rss_sources
    with patch("anime_agent.agents.episode.nodes.fetch_rss.Store", return_value=mock):
        yield mock


def _make_node(mock_store, rss_tool=None, sources=None):
    """Create a FetchRSSNode with mocked session_factory."""
    mock_store.rss_sources.list_active = AsyncMock(return_value=sources or [])

    mock_session = AsyncMock()

    @asynccontextmanager
    async def _factory():
        yield mock_session

    return FetchRSSNode(rss_tool=rss_tool, session_factory=_factory)


async def test_fetch_rss_returns_candidates(mock_store):
    """fetch_rss should fetch and merge RSS candidates."""
    rss_tool = AsyncMock()
    rss_tool.invoke.return_value = ToolOutput(
        success=True,
        data={
            "entries": [
                {"title": "[Sub] Anime - 01 [1080p].mkv", "info_hash": "abc1"},
                {"title": "[Sub] Anime - 01 [720p].mkv", "info_hash": "abc2"},
            ]
        },
    )

    node = _make_node(mock_store, rss_tool=rss_tool, sources=[_make_mock_source()])
    result = await node(_state())

    assert len(result["torrent_candidates"]) == 2
    assert result["status"] == "fetching"


async def test_fetch_rss_merges_with_existing_candidates(mock_store):
    """fetch_rss should merge new candidates with existing ones, deduplicating by info_hash."""
    state = _state()
    state["torrent_candidates"] = [
        {"title": "old", "info_hash": "abc1"},
    ]

    rss_tool = AsyncMock()
    rss_tool.invoke.return_value = ToolOutput(
        success=True,
        data={
            "entries": [
                {"title": "[Sub] Anime - 01 [1080p].mkv", "info_hash": "abc1"},
                {"title": "[Sub] Anime - 01 [720p].mkv", "info_hash": "abc2"},
            ]
        },
    )

    node = _make_node(mock_store, rss_tool=rss_tool, sources=[_make_mock_source()])
    result = await node(state)

    assert len(result["torrent_candidates"]) == 2
    hashes = {c["info_hash"] for c in result["torrent_candidates"]}
    assert hashes == {"abc1", "abc2"}


async def test_fetch_rss_returns_error_without_active_sources(mock_store):
    """fetch_rss should fail if no active RSS sources exist."""
    node = _make_node(mock_store, sources=[])
    result = await node(_state())

    assert result["status"] == "failed"
    assert result["errors"]


async def test_fetch_rss_returns_waiting_on_tool_failure(mock_store):
    """fetch_rss should return waiting_for_rss when all sources fail."""
    rss_tool = AsyncMock()
    rss_tool.invoke.return_value = ToolOutput(success=False, error="RSS down")

    node = _make_node(mock_store, rss_tool=rss_tool, sources=[_make_mock_source()])
    result = await node(_state())

    assert result["status"] == "waiting_for_rss"


async def test_fetch_rss_returns_failed_when_no_session_factory():
    """fetch_rss should fail when no session_factory configured."""
    node = FetchRSSNode()
    result = await node(_state())

    assert result["status"] == "failed"
    assert "errors" in result
