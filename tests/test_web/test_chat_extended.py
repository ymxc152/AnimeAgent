"""Extended tests for chat API endpoints: session management and history."""


async def test_chat_returns_session_id(client):
    """POST /api/chat should return a session_id."""
    response = await client.post("/api/chat", json={"message": "帮助"})
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert len(data["session_id"]) == 16


async def test_chat_reuses_session_id(client):
    """POST /api/chat should reuse session_id when provided."""
    r1 = await client.post("/api/chat", json={"message": "帮助", "session_id": "my-sid"})
    assert r1.json()["session_id"] == "my-sid"

    r2 = await client.post("/api/chat", json={"message": "帮助", "session_id": "my-sid"})
    assert r2.json()["session_id"] == "my-sid"


async def test_chat_history_empty(client):
    """GET /api/chat/history for unknown session should return empty list."""
    response = await client.get("/api/chat/history", params={"session_id": "unknown"})
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "unknown"
    assert data["messages"] == []


async def test_chat_history_after_messages(client):
    """GET /api/chat/history should return messages after chat."""
    await client.post("/api/chat", json={"message": "帮助", "session_id": "hist-sid"})

    response = await client.get("/api/chat/history", params={"session_id": "hist-sid"})
    assert response.status_code == 200
    data = response.json()

    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "帮助"
    assert data["messages"][1]["role"] == "assistant"


async def test_chat_history_delete(client):
    """DELETE /api/chat/history should clear messages."""
    await client.post("/api/chat", json={"message": "帮助", "session_id": "del-sid"})

    # Verify messages exist
    r1 = await client.get("/api/chat/history", params={"session_id": "del-sid"})
    assert len(r1.json()["messages"]) == 2

    # Delete
    r2 = await client.delete("/api/chat/history", params={"session_id": "del-sid"})
    assert r2.status_code == 200

    # Verify gone
    r3 = await client.get("/api/chat/history", params={"session_id": "del-sid"})
    assert len(r3.json()["messages"]) == 0


async def test_chat_help_intent(client):
    """POST /api/chat with help keyword should return help reply."""
    response = await client.post("/api/chat", json={"message": "帮助"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"]["action"] == "help"
    assert "订阅" in data["reply"]


async def test_chat_with_session_continuity(client):
    """Multiple messages in same session should maintain context."""
    sid = "continuity-sid"
    await client.post("/api/chat", json={"message": "帮助", "session_id": sid})
    await client.post("/api/chat", json={"message": "我在追哪些？", "session_id": sid})

    response = await client.get("/api/chat/history", params={"session_id": sid})
    data = response.json()
    assert len(data["messages"]) == 4  # 2 user + 2 assistant
