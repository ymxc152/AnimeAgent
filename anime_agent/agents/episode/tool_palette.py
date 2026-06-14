"""Shared tool palette for all agent nodes."""

from typing import Any

from anime_agent.tools.base import BaseTool


class ToolPalette:
    """Centralized tool registry for agent nodes.

    Each agent node gets tools from this palette instead of instantiating
    its own tools. This ensures consistent configuration and health checking.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._initialized = False

    def _ensure_init(self) -> None:
        """Lazy initialization of tools."""
        if self._initialized:
            return
        from anime_agent.tools.animes_garden_tool import AnimeGardenTool
        from anime_agent.tools.bash_tool import BashTool
        from anime_agent.tools.emby_tool import EmbyTool
        from anime_agent.tools.filesystem_tool import FileSystemTool
        from anime_agent.tools.llm_tool import LLMTool
        from anime_agent.tools.notify_tool import NotifyTool
        from anime_agent.tools.qb_tool import QBTool
        from anime_agent.tools.rss_tool import RSSTool

        self._tools = {
            "llm": LLMTool(),
            "bash": BashTool(),
            "rss": RSSTool(),
            "qbit": QBTool(),
            "filesystem": FileSystemTool(),
            "emby": EmbyTool(),
            "anime_garden": AnimeGardenTool(),
            "notify": NotifyTool(),
        }
        self._initialized = True

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        self._ensure_init()
        return self._tools.get(name)

    def get_all(self) -> dict[str, BaseTool]:
        """Get all tools."""
        self._ensure_init()
        return dict(self._tools)

    async def healthcheck(self) -> dict[str, Any]:
        """Run healthcheck on all tools."""
        self._ensure_init()
        results = {}
        for name, tool in self._tools.items():
            try:
                result = await tool.healthcheck()
                results[name] = {"ok": result.success, "error": result.error}
            except Exception as exc:
                results[name] = {"ok": False, "error": str(exc)}
        return results


# Module-level singleton
palette = ToolPalette()
