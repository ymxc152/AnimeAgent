"""Tests for ScheduleResumeNode."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from anime_agent.agents.episode.nodes.schedule_resume import ScheduleResumeNode
from anime_agent.tools.base import ToolOutput


def _mock_llm(action: str = "schedule", interval: int = 600, **params) -> AsyncMock:
    """Return a mock LLM tool that returns a single JSON action."""
    mock = AsyncMock()
    mock.invoke.return_value = ToolOutput(
        success=True,
        data={"text": json.dumps({"action": action, "reasoning": "test", "interval": interval, **params})},
    )
    return mock


@pytest.fixture
def base_state():
    return {
        "episode_number": 1,
        "subscription_id": 1,
    }


async def test_schedule_resume_uses_rss_wait_interval_for_waiting_for_rss(base_state):
    """waiting_for_rss should use the longer RSS wait interval."""
    node = ScheduleResumeNode(
        interval_seconds=60,
        rss_wait_seconds=3600,
        llm_tool=_mock_llm("schedule", interval=3600),
    )
    base_state["status"] = "waiting_for_rss"

    result = await node(base_state)

    resume_after = datetime.fromisoformat(result["resume_after"])
    expected_min = datetime.now(UTC) + timedelta(seconds=3500)
    expected_max = datetime.now(UTC) + timedelta(seconds=3700)
    assert expected_min <= resume_after <= expected_max


async def test_schedule_resume_uses_default_interval_for_other_statuses(base_state):
    """Non-RSS-wait statuses should use the default interval."""
    node = ScheduleResumeNode(
        interval_seconds=60,
        rss_wait_seconds=3600,
        llm_tool=_mock_llm("schedule", interval=60),
    )
    base_state["status"] = "search_resources"

    result = await node(base_state)

    resume_after = datetime.fromisoformat(result["resume_after"])
    expected_min = datetime.now(UTC) + timedelta(seconds=50)
    expected_max = datetime.now(UTC) + timedelta(seconds=70)
    assert expected_min <= resume_after <= expected_max


async def test_schedule_resume_preserves_existing_resume_after_for_downloading(base_state):
    """Downloading state should keep the resume_after set by PollDownloadNode."""
    node = ScheduleResumeNode(
        interval_seconds=60,
        rss_wait_seconds=3600,
        llm_tool=_mock_llm("schedule", interval=60),
    )
    existing = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    base_state["status"] = "downloading"
    base_state["resume_after"] = existing

    result = await node(base_state)

    assert result["resume_after"] == existing


async def test_schedule_resume_uses_adaptive_interval_for_downloading_without_existing(base_state):
    """Downloading without existing resume_after should use health-based interval."""
    node = ScheduleResumeNode(
        interval_seconds=60,
        rss_wait_seconds=3600,
        llm_tool=_mock_llm("schedule", interval=60),
    )
    base_state["status"] = "downloading"
    base_state["_poll_context"] = {
        "health_eval": {"state": "metadata_downloading"},
    }

    result = await node(base_state)

    resume_after = datetime.fromisoformat(result["resume_after"])
    expected_min = datetime.now(UTC) + timedelta(seconds=110)
    expected_max = datetime.now(UTC) + timedelta(seconds=130)
    assert expected_min <= resume_after <= expected_max


async def test_schedule_resume_uses_stalled_interval_for_stalled_torrent(base_state):
    """Stalled torrent should use the shorter stalled interval."""
    node = ScheduleResumeNode(
        interval_seconds=60,
        rss_wait_seconds=3600,
        llm_tool=_mock_llm("schedule", interval=60),
    )
    base_state["status"] = "downloading"
    base_state["_poll_context"] = {
        "health_eval": {"state": "stalled"},
    }

    result = await node(base_state)

    resume_after = datetime.fromisoformat(result["resume_after"])
    expected_min = datetime.now(UTC) + timedelta(seconds=290)
    expected_max = datetime.now(UTC) + timedelta(seconds=310)
    assert expected_min <= resume_after <= expected_max


async def test_schedule_resume_uses_healthy_interval_for_healthy_torrent(base_state):
    """Healthy torrent should use the longer healthy interval."""
    node = ScheduleResumeNode(
        interval_seconds=60,
        rss_wait_seconds=3600,
        llm_tool=_mock_llm("schedule", interval=60),
    )
    base_state["status"] = "downloading"
    base_state["_poll_context"] = {
        "health_eval": {"state": "healthy"},
    }

    result = await node(base_state)

    resume_after = datetime.fromisoformat(result["resume_after"])
    expected_min = datetime.now(UTC) + timedelta(seconds=1790)
    expected_max = datetime.now(UTC) + timedelta(seconds=1810)
    assert expected_min <= resume_after <= expected_max
