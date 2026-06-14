"""Extended web endpoint tests — episode detail, update 404, status filter."""

from anime_agent.memory.models import Episode, Subscription


async def test_get_episode_detail(client, db_session):
    """GET /api/episodes/{id} should return full episode details."""
    sub = Subscription(
        bangumi_id=100,
        title_romaji="Frieren",
        title_chinese="葬送的芙莉莲",
        total_episodes=12,
        local_folder_name="Frieren",
    )
    db_session.add(sub)
    await db_session.flush()

    ep = Episode(
        subscription_id=sub.id,
        episode_number=1,
        title="Ep 1",
        status="completed",
        torrent_hash="abc123",
        torrent_name="test.mkv",
    )
    db_session.add(ep)
    await db_session.commit()

    response = await client.get(f"/api/episodes/{ep.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["episode_number"] == 1
    assert data["status"] == "completed"
    assert data["subscription_title"] == "葬送的芙莉莲"


async def test_get_episode_detail_404(client):
    """GET /api/episodes/{id} should return 404 for nonexistent episode."""
    response = await client.get("/api/episodes/99999")
    assert response.status_code == 404


async def test_update_subscription_404(client):
    """PATCH /api/subscriptions/{id} should return 404 for nonexistent subscription."""
    response = await client.patch(
        "/api/subscriptions/99999",
        json={"auto_download_enabled": False},
    )
    assert response.status_code == 404


async def test_list_episodes_with_status_filter(client, db_session):
    """GET /api/episodes?status=completed should filter by status."""
    sub = Subscription(
        bangumi_id=200,
        title_romaji="Test",
        total_episodes=3,
        local_folder_name="Test",
    )
    db_session.add(sub)
    await db_session.flush()

    for i, status in enumerate(["pending", "completed", "failed"], 1):
        db_session.add(Episode(subscription_id=sub.id, episode_number=i, status=status))
    await db_session.commit()

    response = await client.get("/api/episodes?status=completed")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "completed"


async def test_list_episodes_with_subscription_filter(client, db_session):
    """GET /api/episodes?subscription_id=X should filter by subscription."""
    sub1 = Subscription(bangumi_id=301, title_romaji="A", total_episodes=1, local_folder_name="A")
    sub2 = Subscription(bangumi_id=302, title_romaji="B", total_episodes=1, local_folder_name="B")
    db_session.add_all([sub1, sub2])
    await db_session.flush()

    db_session.add(Episode(subscription_id=sub1.id, episode_number=1, status="pending"))
    db_session.add(Episode(subscription_id=sub2.id, episode_number=1, status="pending"))
    await db_session.commit()

    response = await client.get(f"/api/episodes?subscription_id={sub1.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["subscription_id"] == sub1.id


async def test_delete_subscription_404(client):
    """DELETE /api/subscriptions/{id} should return 404 for nonexistent subscription."""
    response = await client.delete("/api/subscriptions/99999")
    assert response.status_code == 404


async def test_list_subscriptions_with_episode_stats(client, db_session):
    """GET /api/subscriptions should include episode statistics."""
    sub = Subscription(
        bangumi_id=400,
        title_romaji="Stats Test",
        total_episodes=3,
        local_folder_name="Stats",
    )
    db_session.add(sub)
    await db_session.flush()

    db_session.add(Episode(subscription_id=sub.id, episode_number=1, status="completed"))
    db_session.add(Episode(subscription_id=sub.id, episode_number=2, status="pending"))
    db_session.add(Episode(subscription_id=sub.id, episode_number=3, status="failed"))
    await db_session.commit()

    response = await client.get("/api/subscriptions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ep_completed"] == 1
    assert data[0]["ep_pending"] == 1
    assert data[0]["ep_failed"] == 1


async def test_health_endpoint(client):
    """GET /api/health should return ok."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
