"""refresh_emby node for Episode Graph."""

from typing import Any

from anime_agent.tools.base import BaseTool
from anime_agent.tools.emby_tool import EmbyTool, EmbyToolInput


class RefreshEmbyNode:
    """Trigger an Emby library refresh after files are organized."""

    def __init__(self, emby_tool: BaseTool | None = None):
        self.emby_tool = emby_tool or EmbyTool()

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Refresh the Emby library so the new episode appears."""
        result = await self.emby_tool.invoke(EmbyToolInput(action="refresh_library"))

        if not result.success:
            return {
                "status": "failed",
                "errors": [f"Emby refresh failed: {result.error}"],
            }

        return {
            "status": "completed",
            "emby_refreshed": result.data.get("refreshed", True),
        }
