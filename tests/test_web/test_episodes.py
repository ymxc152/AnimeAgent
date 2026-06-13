"""Tests for episode endpoints."""

from anime_agent.memory.models import Episode, Subscription


async def test_list_episodes_filters_by_subscription(client, db_session):
    """GET /api/episodes should support filtering by subscription_id."""
    subscription = Subscription(
        bangumi_id=10,
        title_romaji="Sousou no Frieren",
        title_chinese="葬送的芙莉莲",
        total_episodes=2,
        local_folder_name="葬送的芙莉莲",
    )
    db_session.add(subscription)
    await db_session.flush()

    db_session.add_all(
        [
            Episode(subscription_id=subscription.id, episode_number=1, status="pending"),
            Episode(subscription_id=subscription.id, episode_number=2, status="completed"),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/episodes?subscription_id={subscription.id}")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert {ep["episode_number"] for ep in data} == {1, 2}


async def test_retry_episode_resets_failed_status(client, db_session):
    """POST /api/episodes/{id}/retry should reset a failed episode to pending."""
    subscription = Subscription(
        bangumi_id=10,
        title_romaji="Sousou no Frieren",
        title_chinese="葬送的芙莉莲",
        total_episodes=1,
        local_folder_name="葬送的芙莉莲",
    )
    db_session.add(subscription)
    await db_session.flush()

    episode = Episode(
        subscription_id=subscription.id,
        episode_number=1,
        status="failed",
        error_log="previous failure",
    )
    db_session.add(episode)
    await db_session.commit()

    response = await client.post(f"/api/episodes/{episode.id}/retry")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "pending"
    assert data["error_log"] == ""


async def test_list_episodes_filters_by_multiple_statuses(client, db_session):
    """GET /api/episodes should support comma-separated status filtering."""
    subscription = Subscription(
        bangumi_id=10,
        title_romaji="Sousou no Frieren",
        title_chinese="葬送的芙莉莲",
        total_episodes=3,
        local_folder_name="葬送的芙莉莲",
    )
    db_session.add(subscription)
    await db_session.flush()

    db_session.add_all(
        [
            Episode(subscription_id=subscription.id, episode_number=1, status="pending"),
            Episode(subscription_id=subscription.id, episode_number=2, status="completed"),
            Episode(subscription_id=subscription.id, episode_number=3, status="failed"),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/episodes?status=pending,failed")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert {ep["episode_number"] for ep in data} == {1, 3}


async def test_get_episode_detail_returns_full_fields(client, db_session):
    """GET /api/episodes/{id} should return full episode details."""
    subscription = Subscription(
        bangumi_id=10,
        title_romaji="Sousou no Frieren",
        title_chinese="葬送的芙莉莲",
        total_episodes=1,
        local_folder_name="葬送的芙莉莲",
    )
    db_session.add(subscription)
    await db_session.flush()

    episode = Episode(
        subscription_id=subscription.id,
        episode_number=1,
        status="downloading",
        torrent_title="[Sub] Frieren - 01",
        torrent_hash="abc123",
        torrent_status="downloading",
        torrent_last_speed=1.5,
    )
    db_session.add(episode)
    await db_session.commit()

    response = await client.get(f"/api/episodes/{episode.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == episode.id
    assert data["subscription_title"] == "葬送的芙莉莲"
    assert data["torrent_title"] == "[Sub] Frieren - 01"
    assert data["torrent_hash"] == "abc123"
    assert data["torrent_last_speed"] == 1.5
    assert "torrent_candidates" in data
