"""Tests for match_torrent node."""

from unittest.mock import AsyncMock

from anime_agent.agents.episode.nodes.match_torrent import MatchTorrentNode
from anime_agent.tools.base import ToolOutput


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


async def test_match_torrent_selects_high_confidence_candidate():
    """match_torrent should select a candidate and set matched_torrent."""
    selector = AsyncMock()
    selector.select.return_value = ToolOutput(
        success=True,
        data={
            "matched": True,
            "info_hash": "abc1",
            "title": "[Sub] Anime - 01 [1080p].mkv",
            "link": "magnet:?xt=urn:btih:abc1",
            "confidence": 0.95,
        },
    )

    node = MatchTorrentNode(selector=selector)
    result = await node(_state(candidates=[{"title": "test", "info_hash": "abc1"}]))

    assert result["matched_torrent"]["info_hash"] == "abc1"
    assert result["status"] == "matched"
    assert result["low_confidence_count"] == 0


async def test_match_torrent_increments_low_confidence():
    """match_torrent should increment low_confidence_count for medium confidence."""
    selector = AsyncMock()
    selector.select.return_value = ToolOutput(
        success=True,
        data={
            "matched": True,
            "info_hash": "abc1",
            "confidence": 0.65,
        },
    )

    node = MatchTorrentNode(selector=selector)
    result = await node(_state(low_confidence_count=1, candidates=[{"title": "test", "info_hash": "abc1"}]))

    assert result["low_confidence_count"] == 2
    assert result["status"] == "low_confidence"


async def test_match_torrent_triggers_human_review_after_three_low_confidence():
    """match_torrent should set requires_human after 3 low confidence attempts."""
    selector = AsyncMock()
    selector.select.return_value = ToolOutput(
        success=True,
        data={
            "matched": True,
            "info_hash": "abc1",
            "confidence": 0.65,
        },
    )

    node = MatchTorrentNode(selector=selector)
    result = await node(_state(low_confidence_count=2, candidates=[{"title": "test", "info_hash": "abc1"}]))

    assert result["requires_human"] is True
    assert result["status"] == "human_review"


async def test_match_torrent_returns_no_match():
    """match_torrent should handle no match gracefully."""
    selector = AsyncMock()
    selector.select.return_value = ToolOutput(
        success=True,
        data={"matched": False, "reason": "No candidates"},
    )

    node = MatchTorrentNode(selector=selector)
    result = await node(_state(candidates=[{"title": "test", "info_hash": "abc1"}]))

    assert result["matched_torrent"] is None
    assert result["status"] == "no_match"


async def test_match_torrent_triggers_search_resources_when_empty():
    """match_torrent should trigger search_resources when candidates are empty."""
    selector = AsyncMock()
    node = MatchTorrentNode(selector=selector)
    result = await node(_state(candidates=[], resource_searched=False))

    assert result["status"] == "search_resources"
    selector.select.assert_not_called()


async def test_match_torrent_returns_no_match_when_empty_and_searched():
    """match_torrent should return no_match when candidates empty but search already done."""
    selector = AsyncMock()
    selector.select.return_value = ToolOutput(
        success=True,
        data={"matched": False, "reason": "No candidates"},
    )

    node = MatchTorrentNode(selector=selector)
    result = await node(_state(candidates=[], resource_searched=True))

    assert result["status"] == "no_match"
