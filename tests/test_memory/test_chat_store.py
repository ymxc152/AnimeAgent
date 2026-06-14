"""Tests for ChatMessageStore."""

from anime_agent.memory.store import ChatMessageStore


async def test_create_and_list(db_session):
    """Store should create messages and list them by session."""
    store = ChatMessageStore(db_session)

    await store.create(session_id="s1", role="user", content="hello")
    await store.create(
        session_id="s1",
        role="assistant",
        content="hi there",
        intent_json='{"action":"unknown","chat_state":"idle"}',
    )
    await store.create(session_id="s2", role="user", content="other session")

    msgs = await store.list_by_session("s1")
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[0].content == "hello"
    assert msgs[1].role == "assistant"
    assert msgs[1].intent_json is not None


async def test_list_by_session_respects_limit(db_session):
    """list_by_session should respect the limit parameter."""
    store = ChatMessageStore(db_session)

    for i in range(5):
        await store.create(session_id="s1", role="user", content=f"msg {i}")

    msgs = await store.list_by_session("s1", limit=3)
    assert len(msgs) == 3


async def test_list_by_session_ordered_asc(db_session):
    """Messages should be returned in chronological order."""
    store = ChatMessageStore(db_session)

    await store.create(session_id="s1", role="user", content="first")
    await store.create(session_id="s1", role="user", content="second")
    await store.create(session_id="s1", role="user", content="third")

    msgs = await store.list_by_session("s1")
    assert [m.content for m in msgs] == ["first", "second", "third"]


async def test_delete_session(db_session):
    """delete_session should remove all messages for a session."""
    store = ChatMessageStore(db_session)

    await store.create(session_id="s1", role="user", content="hello")
    await store.create(session_id="s1", role="assistant", content="hi")
    await store.create(session_id="s2", role="user", content="other")

    await store.delete_session("s1")

    msgs_s1 = await store.list_by_session("s1")
    assert len(msgs_s1) == 0

    msgs_s2 = await store.list_by_session("s2")
    assert len(msgs_s2) == 1


async def test_create_with_data_json(db_session):
    """Store should persist data_json field."""
    store = ChatMessageStore(db_session)

    await store.create(
        session_id="s1",
        role="assistant",
        content="reply",
        data_json='[{"title":"Test"}]',
    )

    msgs = await store.list_by_session("s1")
    assert len(msgs) == 1
    assert msgs[0].data_json == '[{"title":"Test"}]'
