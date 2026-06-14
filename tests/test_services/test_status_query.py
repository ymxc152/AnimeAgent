"""Tests for StatusQueryService."""

import pytest

from anime_agent.memory.models import Episode, Subscription
from anime_agent.services.status_query import StatusQueryService


@pytest.fixture
async def service(db_session):
    """Return a StatusQueryService backed by the test session."""
    return StatusQueryService(db_session)


async def test_list_active_returns_ongoing_subscriptions(service, db_session):
    """list_active should only return ongoing subscriptions with counts."""
    sub = Subscription(title_romaji="Frieren", status="ongoing", total_episodes=2)
    db_session.add(sub)
    await db_session.flush()
    db_session.add_all([
        Episode(subscription_id=sub.id, episode_number=1, status="completed"),
        Episode(subscription_id=sub.id, episode_number=2, status="pending"),
    ])
    await db_session.commit()

    result = await service.list_active()

    assert len(result) == 1
    assert result[0]["title"] == "Frieren"
    assert result[0]["completed"] == 1
    assert result[0]["pending"] == 1


async def test_subscription_detail_finds_by_title(service, db_session):
    """subscription_detail should fuzzy-match titles."""
    sub = Subscription(
        title_romaji="Sousou no Frieren",
        title_chinese="葬送的芙莉莲",
        status="ongoing",
        total_episodes=1,
    )
    db_session.add(sub)
    await db_session.flush()
    db_session.add(Episode(subscription_id=sub.id, episode_number=1, status="completed"))
    await db_session.commit()

    result = await service.subscription_detail("芙莉莲")

    assert result is not None
    assert result["title"] == "葬送的芙莉莲"
    assert result["completed"] == 1


async def test_subscription_detail_returns_none_for_unknown(service):
    """subscription_detail should return None when title not found."""
    result = await service.subscription_detail("不存在的番")
    assert result is None


async def test_pending_torrents_returns_waiting_episodes(service, db_session):
    """pending_torrents should return episodes waiting for torrents."""
    sub = Subscription(title_romaji="Test", status="ongoing")
    db_session.add(sub)
    await db_session.flush()
    db_session.add(
        Episode(subscription_id=sub.id, episode_number=1, status="waiting_for_rss")
    )
    await db_session.commit()

    result = await service.pending_torrents()

    assert len(result) == 1
    assert result[0]["status"] == "waiting_for_rss"
    assert result[0]["episode_number"] == 1


async def test_anime_info_returns_metadata(service, db_session):
    """anime_info should return subscription metadata."""
    sub = Subscription(
        title_romaji="Test",
        title_chinese="测试",
        status="completed",
        total_episodes=12,
        season_year=2024,
        season="FALL",
    )
    db_session.add(sub)
    await db_session.commit()

    result = await service.anime_info("测试")

    assert result is not None
    assert result["total_episodes"] == 12
    assert result["season"] == "FALL"


async def test_failed_tasks_returns_failed_episodes(service, db_session):
    """failed_tasks should return recent failed episodes."""
    sub = Subscription(title_romaji="Test", status="ongoing")
    db_session.add(sub)
    await db_session.flush()
    db_session.add(
        Episode(subscription_id=sub.id, episode_number=3, status="failed", error_log="timeout")
    )
    await db_session.commit()

    result = await service.failed_tasks()

    assert len(result) == 1
    assert result[0]["episode_number"] == 3
    assert "timeout" in result[0]["error_log"]
