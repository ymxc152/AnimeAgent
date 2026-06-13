"""Tests for the tool registry used by health check and scheduler."""

from anime_agent.tools import get_all_tools
from anime_agent.tools.base import BaseTool


def test_tool_registry_returns_known_tools():
    """Registry should return an instance of every production tool."""
    tools = get_all_tools()
    names = {tool.name for tool in tools}

    expected = {
        "anilist",
        "bangumi",
        "emby",
        "filesystem",
        "llm",
        "notify",
        "qbittorrent",
        "rss",
        "tmdb",
    }
    assert expected.issubset(names)
    assert all(isinstance(tool, BaseTool) for tool in tools)
