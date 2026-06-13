"""Tests for subscription endpoints."""

from anime_agent.memory.models import Subscription


async def test_list_subscriptions_returns_saved_subscriptions(client, db_session):
    """GET /api/subscriptions should return all subscriptions."""
    subscription = Subscription(
        bangumi_id=10,
        anilist_id=20,
        title_romaji="Sousou no Frieren",
        title_chinese="葬送的芙莉莲",
        total_episodes=28,
        local_folder_name="葬送的芙莉莲",
        status="ongoing",
        auto_download_enabled=True,
    )
    db_session.add(subscription)
    await db_session.commit()

    response = await client.get("/api/subscriptions")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert data[0]["title_romaji"] == "Sousou no Frieren"
    assert data[0]["auto_download_enabled"] is True


async def test_create_subscription_stores_new_subscription(client):
    """POST /api/subscriptions should create and return a subscription."""
    payload = {
        "title_romaji": "Sousou no Frieren",
        "title_chinese": "葬送的芙莉莲",
        "total_episodes": 28,
        "auto_download_enabled": True,
    }

    response = await client.post("/api/subscriptions", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["id"] is not None
    assert data["title_romaji"] == "Sousou no Frieren"
    assert data["title_chinese"] == "葬送的芙莉莲"
    assert data["total_episodes"] == 28
    assert data["auto_download_enabled"] is True


async def test_update_subscription_toggles_auto_download(client, db_session):
    """PATCH /api/subscriptions/{id} should update allowed fields."""
    subscription = Subscription(
        bangumi_id=10,
        title_romaji="Sousou no Frieren",
        title_chinese="葬送的芙莉莲",
        total_episodes=28,
        local_folder_name="葬送的芙莉莲",
        auto_download_enabled=True,
    )
    db_session.add(subscription)
    await db_session.commit()

    response = await client.patch(
        f"/api/subscriptions/{subscription.id}",
        json={"auto_download_enabled": False, "local_folder_name": "Frieren"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["auto_download_enabled"] is False
    assert data["local_folder_name"] == "Frieren"


async def test_delete_subscription_removes_subscription(client, db_session):
    """DELETE /api/subscriptions/{id} should remove the subscription."""
    subscription = Subscription(
        bangumi_id=10,
        title_romaji="Sousou no Frieren",
        title_chinese="葬送的芙莉莲",
        total_episodes=28,
        local_folder_name="葬送的芙莉莲",
    )
    db_session.add(subscription)
    await db_session.commit()

    response = await client.delete(f"/api/subscriptions/{subscription.id}")
    assert response.status_code == 204

    response = await client.get("/api/subscriptions")
    assert response.json() == []
