"""Tests for ConversationalAgent."""

from anime_agent.agents.conversational.agent import ConversationalAgent
from anime_agent.memory.models import Episode, Subscription


async def test_agent_replies_with_subscription_detail(db_session):
    """Agent should answer progress questions using the database."""
    sub = Subscription(
        title_romaji="Sousou no Frieren",
        title_chinese="葬送的芙莉莲",
        status="ongoing",
        total_episodes=2,
    )
    db_session.add(sub)
    await db_session.flush()
    db_session.add_all([
        Episode(subscription_id=sub.id, episode_number=1, status="completed"),
        Episode(subscription_id=sub.id, episode_number=2, status="pending"),
    ])
    await db_session.commit()

    agent = ConversationalAgent(db_session)
    result = await agent.chat("《葬送的芙莉莲》下完了吗？")

    assert result["intent"]["query_type"] == "subscription_detail"
    assert "葬送的芙莉莲" in result["reply"]
    assert "已完成 1 集" in result["reply"]


async def test_agent_lists_active_subscriptions(db_session):
    """Agent should list active subscriptions."""
    sub = Subscription(title_romaji="Test", status="ongoing", total_episodes=1)
    db_session.add(sub)
    await db_session.commit()

    agent = ConversationalAgent(db_session)
    result = await agent.chat("我在下载哪些番？")

    assert result["intent"]["query_type"] == "list_active"
    assert "Test" in result["reply"]
