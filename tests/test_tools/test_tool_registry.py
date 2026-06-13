"""Tests for tool registry."""

import pytest

from anime_agent.tools import get_all_tools, AnimeGardenTool


class TestToolRegistry:
    """Test tool registry."""

    def test_get_all_tools_returns_list(self):
        """Should return a list of tools."""
        tools = get_all_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_get_all_tools_includes_animes_garden(self):
        """Should include AnimeGardenTool in the list."""
        tools = get_all_tools()
        tool_names = [tool.name for tool in tools]
        assert "animes_garden" in tool_names

    def test_get_all_tools_includes_rss(self):
        """Should include RSSTool in the list."""
        tools = get_all_tools()
        tool_names = [tool.name for tool in tools]
        assert "rss" in tool_names

    def test_all_tools_have_invoke(self):
        """All tools should have invoke method."""
        tools = get_all_tools()
        for tool in tools:
            assert hasattr(tool, "invoke")
            assert callable(tool.invoke)

    def test_all_tools_have_healthcheck(self):
        """All tools should have healthcheck method."""
        tools = get_all_tools()
        for tool in tools:
            assert hasattr(tool, "healthcheck")
            assert callable(tool.healthcheck)

    def test_animes_garden_tool_import(self):
        """Should be able to import AnimeGardenTool directly."""
        from anime_agent.tools import AnimeGardenTool
        assert AnimeGardenTool is not None
