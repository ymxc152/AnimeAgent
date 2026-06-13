"""Tests for NotifyTool."""

from unittest.mock import AsyncMock, MagicMock

from anime_agent.tools.notify_tool import NotifyTool, NotifyToolInput


async def test_notify_tool_sends_via_apprise():
    """NotifyTool should send a notification through apprise when configured."""
    mock_apprise = MagicMock()
    mock_apprise.async_notify = AsyncMock(return_value=True)

    tool = NotifyTool(apprise_obj=mock_apprise)
    result = await tool.invoke(NotifyToolInput(message="Episode 1 downloaded"))

    assert result.success is True
    mock_apprise.async_notify.assert_awaited_once_with(
        body="Episode 1 downloaded", title="AnimeAgent"
    )


async def test_notify_tool_returns_success_when_apprise_fails():
    """NotifyTool should still return success if apprise fails (non-blocking)."""
    mock_apprise = MagicMock()
    mock_apprise.async_notify = AsyncMock(return_value=False)

    tool = NotifyTool(apprise_obj=mock_apprise)
    result = await tool.invoke(NotifyToolInput(message="Episode 1 downloaded"))

    assert result.success is True
    assert result.data["apprise_sent"] is False


async def test_notify_tool_skips_apprise_when_no_urls():
    """NotifyTool should skip apprise and just log when no URLs are configured."""
    tool = NotifyTool(apprise_urls="")
    result = await tool.invoke(NotifyToolInput(message="Episode 1 downloaded"))

    assert result.success is True
    assert result.data["apprise_sent"] is False
