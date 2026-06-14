"""Tests for multi-turn dialogue and session management."""

from anime_agent.agents.conversational.agent import ConversationalAgent
from anime_agent.memory.models import Episode, Subscription


async def test_session_id_generated_if_not_provided(db_session):
    """Agent should generate a session_id when none is given."""
    agent = ConversationalAgent(db_session)
    result = await agent.chat("帮助")

    assert "session_id" in result
    assert len(result["session_id"]) == 16


async def test_session_id_preserved_across_turns(db_session):
    """Same session_id should be reused across calls."""
    agent = ConversationalAgent(db_session)

    r1 = await agent.chat("帮助", session_id="test-sid")
    assert r1["session_id"] == "test-sid"

    r2 = await agent.chat("我在追哪些？", session_id="test-sid")
    assert r2["session_id"] == "test-sid"


async def test_messages_persisted_in_db(db_session):
    """Each turn should save user + assistant messages."""
    agent = ConversationalAgent(db_session)

    await agent.chat("帮助", session_id="s1")

    from anime_agent.memory.store import ChatMessageStore

    store = ChatMessageStore(db_session)
    msgs = await store.list_by_session("s1")
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[0].content == "帮助"
    assert msgs[1].role == "assistant"


async def test_help_returns_capability_list(db_session):
    """Help intent should return a structured capability list."""
    agent = ConversationalAgent(db_session)
    result = await agent.chat("帮助")

    assert result["intent"]["action"] == "help"
    assert "订阅" in result["reply"]
    assert "追番" in result["reply"] or "下载" in result["reply"]


async def test_query_status_with_session(db_session):
    """Status queries should work with session management."""
    sub = Subscription(
        title_romaji="Test",
        title_chinese="测试番",
        status="ongoing",
        total_episodes=1,
    )
    db_session.add(sub)
    await db_session.commit()

    agent = ConversationalAgent(db_session)
    result = await agent.chat("我在追哪些？", session_id="s2")

    assert result["intent"]["action"] == "query_status"
    assert "测试番" in result["reply"]


async def test_retry_episode(db_session):
    """Retry intent should reset failed episodes to pending."""
    sub = Subscription(
        title_romaji="Test",
        title_chinese="测试番",
        status="ongoing",
        total_episodes=2,
    )
    db_session.add(sub)
    await db_session.flush()
    db_session.add_all(
        [
            Episode(subscription_id=sub.id, episode_number=1, status="completed"),
            Episode(
                subscription_id=sub.id, episode_number=2, status="failed", error_log="some error"
            ),
        ]
    )
    await db_session.commit()

    agent = ConversationalAgent(db_session)
    result = await agent.chat("重试 测试番")

    assert result["intent"]["action"] == "retry_episode"
    assert result["data"]["success"] is True
    assert result["data"]["retried_count"] == 1


async def test_unknown_intent_without_llm(db_session):
    """Unknown intent should still return a valid response."""
    agent = ConversationalAgent(db_session)  # no LLM
    result = await agent.chat("asdfghjkl")

    assert result["intent"]["action"] == "unknown"
    assert "没太听懂" in result["reply"] or "帮助" in result["reply"]


async def test_reply_has_intent_json_persisted(db_session):
    """Assistant messages should have intent_json with chat_state."""
    agent = ConversationalAgent(db_session)
    await agent.chat("帮助", session_id="s3")

    import json

    from anime_agent.memory.store import ChatMessageStore

    store = ChatMessageStore(db_session)
    msgs = await store.list_by_session("s3")
    assistant_msg = [m for m in msgs if m.role == "assistant"][0]

    intent = json.loads(assistant_msg.intent_json)
    assert "chat_state" in intent
    assert intent["chat_state"] == "idle"
