"""Tests for fetch_rss node."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anime_agent.agents.episode.nodes.fetch_rss import FetchRSSNode
from anime_agent.tools.base import ToolOutput


def _mock_llm(action: str = "fetch", **params) -> AsyncMock:
    """Return a mock LLM tool that returns a single JSON action."""
    mock = AsyncMock()
    mock.invoke.return_value = ToolOutput(
        success=True,
        data={"text": json.dumps({"action": action, "reasoning": "test", **params})},
    )
    return mock


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


def _make_mock_source(url: str = "https://example.com/rss", name: str = "test", source_id: int = 1):
    source = MagicMock()
    source.id = source_id
    source.url = url
    source.name = name
    source.is_active = True
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
    sources = sources or []
    mock_store.rss_sources.list_active = AsyncMock(return_value=sources)

    async def _get_by_id(source_id: int):
        for source in sources:
            if getattr(source, "id", None) == source_id:
                return source
        return None

    mock_store.rss_sources.get_by_id = AsyncMock(side_effect=_get_by_id)

    mock_session = AsyncMock()

    @asynccontextmanager
    async def _factory():
        yield mock_session

    return FetchRSSNode(rss_tool=rss_tool, session_factory=_factory, llm_tool=_mock_llm())


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
    node = FetchRSSNode(llm_tool=_mock_llm())
    result = await node(_state())

    assert result["status"] == "failed"
    assert "errors" in result


async def test_fetch_rss_uses_specific_rss_source(mock_store):
    """fetch_rss should prefer the subscription's rss_source_id."""
    rss_tool = AsyncMock()
    rss_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"entries": [{"title": "[Sub] Anime - 01 [1080p].mkv", "info_hash": "abc1"}]},
    )

    preferred = _make_mock_source(url="https://preferred.com/rss", name="preferred", source_id=1)
    other = _make_mock_source(url="https://other.com/rss", name="other", source_id=2)
    node = _make_node(mock_store, rss_tool=rss_tool, sources=[preferred, other])
    result = await node(_state(rss_source_id=1))

    assert result["status"] == "fetching"
    assert len(result["torrent_candidates"]) == 1
    rss_tool.invoke.assert_called_once()
    call_url = rss_tool.invoke.call_args[0][0].url
    assert call_url == "https://preferred.com/rss"


async def test_fetch_rss_falls_back_when_source_inactive(mock_store):
    """fetch_rss should fall back to all active sources if the requested one is inactive."""
    rss_tool = AsyncMock()
    rss_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"entries": [{"title": "[Sub] Anime - 01 [1080p].mkv", "info_hash": "abc1"}]},
    )

    inactive = _make_mock_source(url="https://inactive.com/rss", name="inactive", source_id=1)
    inactive.is_active = False
    fallback = _make_mock_source(url="https://fallback.com/rss", name="fallback", source_id=2)
    node = _make_node(mock_store, rss_tool=rss_tool, sources=[inactive, fallback])
    result = await node(_state(rss_source_id=1))

    assert result["status"] == "fetching"
    call_url = rss_tool.invoke.call_args[0][0].url
    assert call_url == "https://fallback.com/rss"


def test_fetch_rss_builds_nyaa_title_url():
    """FetchRSSNode should append the anime title to Nyaa q parameter."""
    node = FetchRSSNode(llm_tool=_mock_llm())
    url = node._build_source_url("https://nyaa.si/?page=rss&q=1080p&c=1_3&f=2", "Frieren")
    assert "q=1080p+Frieren" in url or "q=Frieren+1080p" in url


def test_fetch_rss_builds_animegarden_title_url():
    """FetchRSSNode should append the anime title to AnimeGarden keyword parameters."""
    node = FetchRSSNode(llm_tool=_mock_llm())
    url = node._build_source_url("https://api.animes.garden/feed.xml?keyword=1080", "Frieren")
    assert "keyword=1080" in url
    assert "keyword=Frieren" in url


def test_fetch_rss_leaves_unknown_sources_unchanged():
    """FetchRSSNode should not modify URLs for unknown RSS sources."""
    node = FetchRSSNode(llm_tool=_mock_llm())
    original = "https://example.com/rss?search=1080p"
    assert node._build_source_url(original, "Frieren") == original


def test_fetch_rss_prefers_romaji_for_nyaa():
    """FetchRSSNode should use romaji title for Nyaa sources."""
    node = FetchRSSNode(llm_tool=_mock_llm())
    state = {
        "title_romaji": "Otonari no Tenshi-sama",
        "title_native": "お隣の天使様",
        "title_chinese": "关于邻家的天使大人",
    }
    assert node._search_title(state, "nyaa.si") == "Otonari no Tenshi-sama"


def test_fetch_rss_prefers_chinese_for_animegarden():
    """FetchRSSNode should use Chinese title for AnimeGarden sources."""
    node = FetchRSSNode(llm_tool=_mock_llm())
    state = {
        "title_romaji": "Otonari no Tenshi-sama",
        "title_native": "お隣の天使様",
        "title_chinese": "关于邻家的天使大人",
    }
    assert node._search_title(state, "api.animes.garden") == "关于邻家的天使大人"
