"""notify_user node for Episode Graph — send completion/failure notifications."""

from typing import Any

from anime_agent.tools.notify_tool import NotifyTool, NotifyToolInput
from anime_agent.utils.logger import logger


class NotifyUserNode:
    """Notify the user about episode completion or failures.

    Uses :class:`NotifyTool` so the notification is sent through any configured
    apprise URLs and is always logged.  Failures to notify are non-fatal.
    """

    def __init__(self, notify_tool: NotifyTool | None = None):
        self.notify_tool = notify_tool or NotifyTool()

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Send a notification based on the current episode state."""
        status = state.get("status", "unknown")
        title = state.get("title_romaji") or state.get("title_native") or "Unknown"
        episode = state.get("episode_number")
        errors = state.get("errors", [])

        if status in {"completed", "organized", "organized_with_warnings"}:
            message = f"{title} 第 {episode} 集下载整理完成"
        elif status == "failed":
            error_text = "; ".join(str(e) for e in errors[-3:]) or "未知错误"
            message = f"{title} 第 {episode} 集处理失败: {error_text}"
        else:
            message = f"{title} 第 {episode} 集状态: {status}"

        logger.info("Notifying user: {}", message)

        try:
            await self.notify_tool.invoke(
                NotifyToolInput(message=message, title="AnimeAgent")
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("notify_user failed: {}", exc)

        return {}
