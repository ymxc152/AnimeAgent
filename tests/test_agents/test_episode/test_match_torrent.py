"""Tests for match_torrent node."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from anime_agent.agents.episode.nodes.match_torrent import MatchTorrentNode
from anime_agent.tools.base import ToolOutput


def _mock_llm(action: str, **params) -> AsyncMock:
    """Return a mock LLM tool that returns a single JSON action."""
    result = ToolOutput(
        success=True,
        data={"text": json.dumps({"action": action, "reasoning": "test", **params})},
    )

    async def _invoke(input_data):
        return result

    mock = AsyncMock()
    mock.invoke = AsyncMock(side_effect=_invoke)
    return mock


def _state(low_confidence_count: int = 0, candidates: list | None = None, resource_searched: bool = False) -> dict:
    return {
        "subscription_id": 42,
        "episode_number": 1,
        "title_romaji": "Sousou no Frieren",
        "title_native": "葬送のフリーレン",
        "title_chinese": "葬送的芙莉莲",
        "torrent_candidates": candidates or [],
        "low_confidence_count": low_confidence_count,
        "torrent_failed_hashes": [],
        "resource_searched": resource_searched,
    }


def _make_selector(prefilter_result=None):
    """Create a MagicMock selector with _prefilter returning the given result."""
    selector = MagicMock()
    selector._prefilter.return_value = prefilter_result or []
    return selector


async def test_match_torrent_selects_high_confidence_candidate():
    """match_torrent should select a candidate and set matched_torrent."""
    selector = _make_selector([{"title": "test", "info_hash": "abc1", "size": 1000}])

    llm = _mock_llm("select", info_hash="abc1")
    node = MatchTorrentNode(selector=selector, llm_tool=llm)
    result = await node(_state(candidates=[{"title": "test", "info_hash": "abc1"}]))

    assert result["matched_torrent"]["info_hash"] == "abc1"
    assert result["status"] == "matched"


async def test_match_torrent_returns_no_match_on_abort():
    """match_torrent should return no_match when LLM aborts."""
    selector = _make_selector([{"title": "test", "info_hash": "abc1", "size": 1000}])

    llm = _mock_llm("abort")
    node = MatchTorrentNode(selector=selector, llm_tool=llm)
    result = await node(_state(candidates=[{"title": "test", "info_hash": "abc1"}]))

    assert result["matched_torrent"] is None
    assert result["status"] == "no_match"


async def test_match_torrent_triggers_search_resources_when_empty():
    """match_torrent should trigger search_resources when candidates are empty."""
    selector = _make_selector([])

    llm = _mock_llm("search_more")
    node = MatchTorrentNode(selector=selector, llm_tool=llm)
    result = await node(_state(candidates=[], resource_searched=False))

    assert result["status"] == "search_resources"
    selector._prefilter.assert_called()


async def test_match_torrent_returns_no_match_when_empty_and_searched():
    """match_torrent should return no_match when candidates empty but search already done."""
    selector = _make_selector([])

    llm = _mock_llm("abort")
    node = MatchTorrentNode(selector=selector, llm_tool=llm)
    result = await node(_state(candidates=[], resource_searched=True))

    assert result["matched_torrent"] is None
    assert result["status"] == "no_match"


async def test_match_torrent_handles_llm_error():
    """match_torrent should handle LLM errors gracefully."""
    selector = _make_selector([{"title": "test", "info_hash": "abc1", "size": 1000}])

    llm = AsyncMock()
    async def _fail_invoke(input_data):
        return ToolOutput(success=False, error="LLM unavailable")
    llm.invoke = AsyncMock(side_effect=_fail_invoke)
    node = MatchTorrentNode(selector=selector, llm_tool=llm)
    result = await node(_state(candidates=[{"title": "test", "info_hash": "abc1"}]))

    assert result["status"] == "failed"
    assert "errors" in result
