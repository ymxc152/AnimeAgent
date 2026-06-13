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
