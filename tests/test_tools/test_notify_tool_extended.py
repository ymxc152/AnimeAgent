"""Extended tests for NotifyTool — apprise URL parsing, error handling."""

from unittest.mock import AsyncMock, MagicMock, patch

from anime_agent.tools.notify_tool import NotifyTool, NotifyToolInput


class TestNotifyToolInvoke:
    async def test_sends_notification_with_apprise(self):
        mock_apprise = AsyncMock()
        mock_apprise.async_notify.return_value = True

        tool = NotifyTool(apprise_obj=mock_apprise)
        result = await tool.invoke(NotifyToolInput(message="Test message"))

        assert result.success is True
        assert result.data["apprise_sent"] is True
        mock_apprise.async_notify.assert_called_once()

    async def test_returns_success_without_apprise_urls(self):
        tool = NotifyTool(apprise_urls="")
        result = await tool.invoke(NotifyToolInput(message="Test"))

        assert result.success is True
        assert result.data["apprise_sent"] is False

    async def test_handles_apprise_exception(self):
        mock_apprise = AsyncMock()
        mock_apprise.async_notify.side_effect = Exception("Network error")

        tool = NotifyTool(apprise_obj=mock_apprise)
        result = await tool.invoke(NotifyToolInput(message="Test"))

        assert result.success is True
        assert result.data["apprise_sent"] is False


class TestNotifyToolGetApprise:
    def test_returns_none_when_no_urls(self):
        tool = NotifyTool(apprise_urls="")
        assert tool._get_apprise() is None

    def test_returns_none_when_urls_is_none(self):
        tool = NotifyTool(apprise_urls="")
        assert tool._get_apprise() is None

    def test_creates_apprise_from_urls(self):
        with patch("anime_agent.tools.notify_tool.apprise.Apprise") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            tool = NotifyTool(apprise_urls="tgram://token/chat,discord://webhook")
            result = tool._get_apprise()

            assert result is mock_instance
            assert mock_instance.add.call_count == 2

    def test_skips_empty_urls_in_csv(self):
        with patch("anime_agent.tools.notify_tool.apprise.Apprise") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            tool = NotifyTool(apprise_urls="tgram://token/chat,,  ,discord://webhook")
            tool._get_apprise()

            # Should add 2 URLs (skipping empty ones)
            assert mock_instance.add.call_count == 2

    def test_returns_preconfigured_obj(self):
        mock_obj = MagicMock()
        tool = NotifyTool(apprise_obj=mock_obj)
        assert tool._get_apprise() is mock_obj


class TestNotifyToolHealthcheck:
    async def test_healthcheck_succeeds(self):
        tool = NotifyTool(apprise_urls="")
        result = await tool.healthcheck()
        assert result.success is True
