"""Tests for ScheduleResumeNode."""

from datetime import UTC, datetime, timedelta

import pytest

from anime_agent.agents.episode.nodes.schedule_resume import ScheduleResumeNode


@pytest.fixture
def base_state():
    return {
        "episode_number": 1,
        "subscription_id": 1,
    }


async def test_schedule_resume_uses_rss_wait_interval_for_waiting_for_rss(base_state):
    """waiting_for_rss should use the longer RSS wait interval."""
    node = ScheduleResumeNode(interval_seconds=60, rss_wait_seconds=3600)
    base_state["status"] = "waiting_for_rss"

    result = await node(base_state)

    resume_after = datetime.fromisoformat(result["resume_after"])
    expected_min = datetime.now(UTC) + timedelta(seconds=3500)
    expected_max = datetime.now(UTC) + timedelta(seconds=3700)
    assert expected_min <= resume_after <= expected_max


async def test_schedule_resume_uses_default_interval_for_other_statuses(base_state):
    """Non-RSS-wait statuses should use the default interval."""
    node = ScheduleResumeNode(interval_seconds=60, rss_wait_seconds=3600)
    base_state["status"] = "search_resources"

    result = await node(base_state)

    resume_after = datetime.fromisoformat(result["resume_after"])
    expected_min = datetime.now(UTC) + timedelta(seconds=50)
    expected_max = datetime.now(UTC) + timedelta(seconds=70)
    assert expected_min <= resume_after <= expected_max


async def test_schedule_resume_preserves_existing_resume_after_for_downloading(base_state):
    """Downloading state should keep the resume_after set by PollDownloadNode."""
    node = ScheduleResumeNode(interval_seconds=60, rss_wait_seconds=3600)
    existing = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    base_state["status"] = "downloading"
    base_state["resume_after"] = existing

    result = await node(base_state)

    assert result["resume_after"] == existing
