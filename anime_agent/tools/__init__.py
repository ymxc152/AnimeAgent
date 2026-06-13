"""Tool registry and exports."""

from anime_agent.tools.anilist_tool import AniListTool
from anime_agent.tools.animes_garden_tool import AnimeGardenTool
from anime_agent.tools.bangumi_tool import BangumiTool
from anime_agent.tools.base import BaseTool as _BaseTool
from anime_agent.tools.emby_tool import EmbyTool
from anime_agent.tools.filesystem_tool import FileSystemTool
from anime_agent.tools.llm_tool import LLMTool
from anime_agent.tools.notify_tool import NotifyTool
from anime_agent.tools.qb_tool import QBTool
from anime_agent.tools.rss_tool import RSSTool
from anime_agent.tools.tmdb_tool import TMDBTool

__all__ = [
    "AniListTool",
    "AnimeGardenTool",
    "BangumiTool",
    "EmbyTool",
    "FileSystemTool",
    "LLMTool",
    "NotifyTool",
    "QBTool",
    "RSSTool",
    "TMDBTool",
    "get_all_tools",
]


def get_all_tools() -> list[_BaseTool]:
    """Return a fresh instance of every production tool.

    Used by health check and scheduler pre-flight checks.
    """
    return [
        AniListTool(),
        AnimeGardenTool(),
        BangumiTool(),
        EmbyTool(),
        FileSystemTool(),
        LLMTool(),
        NotifyTool(),
        QBTool(),
        RSSTool(),
        TMDBTool(),
    ]
