"""Tests for CompletionChecker."""

from datetime import UTC, datetime, timedelta

from anime_agent.memory.models import Episode, Subscription
from anime_agent.services.completion_checker import CompletionChecker


def _episodes(*statuses: str) -> list[Episode]:
    return [Episode(episode_number=i + 1, status=s) for i, s in enumerate(statuses)]


def test_checker_marks_subscription_completed_when_all_episodes_done():
    """CompletionChecker should mark subscription completed when all episodes are completed."""
    subscription = Subscription(total_episodes=3)
    episodes = _episodes("completed", "completed", "completed")

    result = CompletionChecker().check(subscription, episodes)

    assert result.is_completed is True
    assert result.all_episodes_completed is True


def test_checker_not_completed_with_pending_episodes():
    """CompletionChecker should not mark completed when episodes are pending."""
    subscription = Subscription(total_episodes=3)
    episodes = _episodes("completed", "pending", "pending")

    result = CompletionChecker().check(subscription, episodes)

    assert result.is_completed is False
    assert result.all_episodes_completed is False


def test_checker_detects_finished_status():
    """CompletionChecker should mark completed when status is FINISHED and all episodes aired."""
    subscription = Subscription(
        total_episodes=2,
        status="ongoing",
    )
    episodes = _episodes("completed", "completed")

    result = CompletionChecker().check(
        subscription, episodes, external_status="FINISHED"
    )

    assert result.is_completed is True


def test_checker_detects_last_episode_aired():
    """CompletionChecker should mark completed when nextAiringEpisode is absent and enough time passed."""
    subscription = Subscription(total_episodes=1)
    episodes = _episodes("completed")

    result = CompletionChecker().check(
        subscription,
        episodes,
        external_status="RELEASING",
        last_airing_at=datetime.now(UTC) - timedelta(days=20),
    )

    assert result.is_completed is True


def test_checker_waits_when_still_releasing():
    """CompletionChecker should not mark completed while still releasing."""
    subscription = Subscription(total_episodes=3)
    episodes = _episodes("completed", "completed", "pending")

    result = CompletionChecker().check(
        subscription, episodes, external_status="RELEASING"
    )

    assert result.is_completed is False
