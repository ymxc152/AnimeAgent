"""Tests for the stats endpoint."""

from anime_agent.memory.models import Episode, Subscription


async def test_stats_returns_subscription_and_episode_counts(client, db_session):
    """Stats should aggregate subscription and episode status counts."""
    subscription = Subscription(
        bangumi_id=1,
        anilist_id=2,
        title_romaji="Sousou no Frieren",
        title_chinese="葬送的芙莉莲",
        total_episodes=3,
        local_folder_name="葬送的芙莉莲",
        status="ongoing",
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

    response = await client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()

    assert data["subscriptions"]["total"] == 1
    assert data["subscriptions"]["ongoing"] == 1
    assert data["episodes"]["pending"] == 1
    assert data["episodes"]["completed"] == 1
    assert data["episodes"]["failed"] == 1
