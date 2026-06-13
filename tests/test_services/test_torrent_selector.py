"""Tests for TorrentSelector."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from anime_agent.services.torrent_selector import TorrentSelector
from anime_agent.tools.base import ToolOutput


def _candidate(title: str, info_hash: str, published: datetime | None = None) -> dict:
    return {
        "title": title,
        "info_hash": info_hash,
        "link": f"magnet:?xt=urn:btih:{info_hash}",
        "published": (published or datetime.now(UTC)).isoformat(),
        "size": 536870912,
    }


async def test_selector_prefilters_by_episode_number():
    """Selector should drop candidates whose titles do not contain the target episode."""
    candidates = [
        _candidate("[Sub] Anime - 01 [1080p].mkv", "abc1"),
        _candidate("[Sub] Anime - 02 [1080p].mkv", "abc2"),
        _candidate("[Sub] Anime - 10 [1080p].mkv", "abc3"),
    ]

    llm_tool = AsyncMock()
    llm_tool.invoke.return_value = ToolOutput(
        success=True, data={"json": {"info_hash": "abc1", "confidence": 0.95}}
    )

    selector = TorrentSelector(llm_tool=llm_tool)
    result = await selector.select(
        candidates=candidates,
        episode_number=1,
        title_variants=["Anime"],
        failed_hashes=[],
    )

    assert result.success is True
    # Pre-filter should keep episode 1 only; episode 2 and 10 must be rejected.
    passed = result.data.get("prefiltered", [])
    titles = {c["title"] for c in passed}
    assert "[Sub] Anime - 01 [1080p].mkv" in titles
    assert "[Sub] Anime - 02 [1080p].mkv" not in titles
    assert "[Sub] Anime - 10 [1080p].mkv" not in titles


async def test_selector_prefilters_keeps_versioned_releases():
    """Selector should keep versioned releases like 01v2 / EP01v2."""
    candidates = [
        _candidate("[Sub] Anime - 01v2 [1080p].mkv", "abc1v2"),
        _candidate("[Sub] Anime - 01 [1080p].mkv", "abc1"),
        _candidate("[Sub] Anime EP02v2 [1080p].mkv", "abc2"),
    ]

    llm_tool = AsyncMock()
    llm_tool.invoke.return_value = ToolOutput(
        success=True, data={"json": {"info_hash": "abc1v2", "confidence": 0.95}}
    )

    selector = TorrentSelector(llm_tool=llm_tool)
    result = await selector.select(
        candidates=candidates,
        episode_number=1,
        title_variants=["Anime"],
        failed_hashes=[],
    )

    assert result.success is True
    passed = result.data.get("prefiltered", [])
    titles = {c["title"] for c in passed}
    assert "[Sub] Anime - 01v2 [1080p].mkv" in titles
    assert "[Sub] Anime - 01 [1080p].mkv" in titles
    assert "[Sub] Anime EP02v2 [1080p].mkv" not in titles


async def test_selector_returns_llm_match():
    """Selector should return the LLM-chosen candidate with confidence."""
    candidates = [
        _candidate("[Sub] Anime - 01 [1080p].mkv", "abc1"),
    ]

    llm_tool = AsyncMock()
    llm_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"json": {"info_hash": "abc1", "confidence": 0.95, "reason": "exact match"}},
    )

    selector = TorrentSelector(llm_tool=llm_tool)
    result = await selector.select(
        candidates=candidates,
        episode_number=1,
        title_variants=["Anime"],
        failed_hashes=[],
    )

    assert result.success is True
    assert result.data["matched"] is True
    assert result.data["info_hash"] == "abc1"
    assert result.data["confidence"] == 0.95


async def test_selector_skips_failed_hashes():
    """Selector should not return candidates in the failed_hashes list."""
    candidates = [
        _candidate("[Sub] Anime - 01 [1080p].mkv", "abc1"),
        _candidate("[Sub] Anime - 01 [720p].mkv", "abc2"),
    ]

    llm_tool = AsyncMock()
    llm_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"json": {"info_hash": "abc2", "confidence": 0.9}},
    )

    selector = TorrentSelector(llm_tool=llm_tool)
    result = await selector.select(
        candidates=candidates,
        episode_number=1,
        title_variants=["Anime"],
        failed_hashes=["abc1"],
    )

    assert result.success is True
    assert result.data["info_hash"] == "abc2"


async def test_selector_returns_no_match_when_empty():
    """Selector should return no match when candidates list is empty."""
    selector = TorrentSelector(llm_tool=AsyncMock())
    result = await selector.select(
        candidates=[],
        episode_number=1,
        title_variants=["Anime"],
        failed_hashes=[],
    )

    assert result.success is True
    assert result.data["matched"] is False
