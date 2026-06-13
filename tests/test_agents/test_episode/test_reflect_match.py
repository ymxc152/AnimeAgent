"""Tests for reflect_match node."""

from unittest.mock import AsyncMock

from anime_agent.agents.episode.nodes.reflect_match import ReflectMatchNode
from anime_agent.tools.base import ToolOutput


def _state(
    candidates: list | None = None,
    failed_hashes: list | None = None,
    resource_searched: bool = False,
    low_confidence_count: int = 1,
) -> dict:
    return {
        "subscription_id": 42,
        "episode_number": 1,
        "title_romaji": "Sousou no Frieren",
        "title_native": "葬送のフリーレン",
        "title_chinese": "葬送的芙莉莲",
        "torrent_candidates": candidates or [],
        "torrent_failed_hashes": failed_hashes or [],
        "resource_searched": resource_searched,
        "low_confidence_count": low_confidence_count,
    }


async def test_reflect_match_auto_approves_high_confidence():
    """reflect_match should auto-approve a confident candidate."""
    llm = AsyncMock()
    llm.invoke.return_value = ToolOutput(
        success=True,
        data={
            "json": {
                "action": "auto_approve",
                "info_hash": "abc1",
                "confidence": 0.9,
                "reason": "Clear match",
            }
        },
    )

    node = ReflectMatchNode(llm_tool=llm)
    result = await node(
        _state(candidates=[{"title": "test", "info_hash": "abc1", "size": 1024**3}])
    )

    assert result["status"] == "matched"
    assert result["matched_torrent"]["info_hash"] == "abc1"
    assert result["low_confidence_count"] == 0


async def test_reflect_match_requests_search():
    """reflect_match should request broader search when candidates are poor."""
    llm = AsyncMock()
    llm.invoke.return_value = ToolOutput(
        success=True,
        data={
            "json": {
                "action": "search_resources",
                "confidence": 0.4,
                "reason": "Candidates look off-topic",
            }
        },
    )

    node = ReflectMatchNode(llm_tool=llm)
    result = await node(
        _state(candidates=[{"title": "wrong anime", "info_hash": "abc1", "size": 1024**3}])
    )

    assert result["status"] == "search_resources"


async def test_reflect_match_waits_for_better_candidates():
    """reflect_match should schedule resume when episode may be too new."""
    llm = AsyncMock()
    llm.invoke.return_value = ToolOutput(
        success=True,
        data={
            "json": {
                "action": "wait",
                "confidence": 0.3,
                "reason": "Episode may not have released yet",
            }
        },
    )

    node = ReflectMatchNode(llm_tool=llm)
    result = await node(
        _state(candidates=[{"title": "maybe", "info_hash": "abc1", "size": 1024**3}])
    )

    assert result["status"] == "schedule_resume"


async def test_reflect_match_escalates_to_human_review():
    """reflect_match should escalate when LLM is uncertain."""
    llm = AsyncMock()
    llm.invoke.return_value = ToolOutput(
        success=True,
        data={
            "json": {
                "action": "human_review",
                "confidence": 0.2,
                "reason": "Genuinely ambiguous",
            }
        },
    )

    node = ReflectMatchNode(llm_tool=llm)
    result = await node(
        _state(candidates=[{"title": "maybe", "info_hash": "abc1", "size": 1024**3}])
    )

    assert result["status"] == "human_review"
    assert result["requires_human"] is True


async def test_reflect_match_rejects_failed_hashes():
    """reflect_match should not auto-approve a candidate already marked failed."""
    llm = AsyncMock()
    llm.invoke.return_value = ToolOutput(
        success=True,
        data={
            "json": {
                "action": "auto_approve",
                "info_hash": "abc1",
                "confidence": 0.9,
                "reason": "Looks good",
            }
        },
    )

    node = ReflectMatchNode(llm_tool=llm)
    result = await node(
        _state(
            candidates=[{"title": "test", "info_hash": "abc1", "size": 1024**3}],
            failed_hashes=["abc1"],
        )
    )

    assert result["status"] != "matched"


async def test_reflect_match_no_candidates_triggers_search():
    """reflect_match should trigger search when there are no candidates at all."""
    node = ReflectMatchNode(llm_tool=AsyncMock())
    result = await node(_state(candidates=[], resource_searched=False))

    assert result["status"] == "search_resources"


async def test_reflect_match_llm_failure_escalates():
    """reflect_match should escalate to human review when the LLM call fails."""
    llm = AsyncMock()
    llm.invoke.return_value = ToolOutput(success=False, error="timeout")

    node = ReflectMatchNode(llm_tool=llm)
    result = await node(
        _state(candidates=[{"title": "test", "info_hash": "abc1", "size": 1024**3}])
    )

    assert result["status"] == "human_review"
    assert result["requires_human"] is True
