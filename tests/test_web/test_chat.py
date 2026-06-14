"""Tests for the conversational chat endpoint."""

from anime_agent.memory.models import Episode, Subscription


async def test_chat_lists_active_subscriptions(client, db_session):
    """POST /api/chat should answer list-active questions."""
    sub = Subscription(
        title_romaji="Sousou no Frieren",
        title_chinese="葬送的芙莉莲",
        status="ongoing",
        total_episodes=2,
    )
    db_session.add(sub)
    await db_session.flush()
    db_session.add_all(
        [
            Episode(subscription_id=sub.id, episode_number=1, status="completed"),
            Episode(subscription_id=sub.id, episode_number=2, status="pending"),
        ]
    )
    await db_session.commit()

    response = await client.post("/api/chat", json={"message": "我在下载哪些番？"})
    assert response.status_code == 200
    data = response.json()

    assert "葬送的芙莉莲" in data["reply"]
    assert data["intent"]["query_type"] == "list_active"


async def test_chat_subscription_detail(client, db_session):
    """POST /api/chat should answer progress questions."""
    sub = Subscription(
        title_romaji="Sousou no Frieren",
        title_chinese="葬送的芙莉莲",
        status="ongoing",
        total_episodes=2,
    )
    db_session.add(sub)
    await db_session.flush()
    db_session.add_all(
        [
            Episode(subscription_id=sub.id, episode_number=1, status="completed"),
            Episode(subscription_id=sub.id, episode_number=2, status="pending"),
        ]
    )
    await db_session.commit()

    response = await client.post("/api/chat", json={"message": "《葬送的芙莉莲》下完了吗？"})
    assert response.status_code == 200
    data = response.json()

    assert data["intent"]["query_type"] == "subscription_detail"
    assert "已完成 1 集" in data["reply"]


async def test_chat_unknown_input(client):
    """POST /api/chat should gracefully handle unknown intents."""
    response = await client.post("/api/chat", json={"message": "hello world"})
    assert response.status_code == 200
    data = response.json()

    assert data["intent"]["action"] == "unknown"
