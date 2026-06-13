"""Tests for notify_user node."""

from unittest.mock import AsyncMock

from anime_agent.agents.episode.nodes.notify_user import NotifyUserNode


async def test_notify_user_sends_completion_message():
    mock_tool = AsyncMock()
    node = NotifyUserNode(notify_tool=mock_tool)

    await node({
        "status": "completed",
        "title_romaji": "Sousou no Frieren",
        "episode_number": 10,
        "errors": [],
    })

    call = mock_tool.invoke.call_args[0][0]
    assert "Sousou no Frieren" in call.message
    assert "10" in call.message
    assert call.title == "AnimeAgent"


async def test_notify_user_sends_failure_message():
    mock_tool = AsyncMock()
    node = NotifyUserNode(notify_tool=mock_tool)

    await node({
        "status": "failed",
        "title_romaji": "Sousou no Frieren",
        "episode_number": 5,
        "errors": ["download timeout"],
    })

    call = mock_tool.invoke.call_args[0][0]
    assert "失败" in call.message
    assert "download timeout" in call.message


async def test_notify_user_swallows_tool_errors():
    mock_tool = AsyncMock()
    mock_tool.invoke.side_effect = RuntimeError("boom")
    node = NotifyUserNode(notify_tool=mock_tool)

    result = await node({
        "status": "completed",
        "title_romaji": "Sousou no Frieren",
        "episode_number": 1,
        "errors": [],
    })

    assert result == {}
