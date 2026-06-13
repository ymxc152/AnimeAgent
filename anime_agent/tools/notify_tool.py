"""Notification tool using apprise (optional) and structured logging."""

import apprise

from anime_agent.config import settings
from anime_agent.tools.base import BaseTool, ToolInput, ToolOutput
from anime_agent.utils.logger import logger


class NotifyToolInput(ToolInput):
    """Input for NotifyTool."""

    message: str
    title: str = "AnimeAgent"


class NotifyTool(BaseTool):
    """Send notifications via apprise if configured; always log the message."""

    name = "notify"
    description = "Send notifications through apprise or structured logs."

    def __init__(self, apprise_obj: apprise.Apprise | None = None, apprise_urls: str | None = None):
        self.apprise_urls = apprise_urls if apprise_urls is not None else settings.apprise_urls
        self.apprise_obj = apprise_obj

    def _get_apprise(self) -> apprise.Apprise | None:
        if self.apprise_obj is not None:
            return self.apprise_obj
        if not self.apprise_urls:
            return None
        obj = apprise.Apprise()
        for url in self.apprise_urls.split(","):
            url = url.strip()
            if url:
                obj.add(url)
        return obj

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Log the message and optionally send via apprise."""
        notify_input = NotifyToolInput.model_validate(input_data)

        logger.info("Notification: {}", notify_input.message)

        apprise_obj = self._get_apprise()
        if apprise_obj is None:
            return ToolOutput(success=True, data={"apprise_sent": False})

        try:
            sent = await apprise_obj.async_notify(
                body=notify_input.message, title=notify_input.title
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Apprise notification failed: {}", exc)
            sent = False

        return ToolOutput(success=True, data={"apprise_sent": bool(sent)})
