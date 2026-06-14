"""Tests for ToolPalette — centralized tool registry."""

from unittest.mock import AsyncMock

import pytest

from anime_agent.agents.episode.tool_palette import ToolPalette


@pytest.fixture
def palette():
    """Create a fresh ToolPalette for each test."""
    return ToolPalette()


class TestToolPaletteGet:
    def test_get_returns_tool_by_name(self, palette):
        """Should return a tool instance for a known name."""
        tool = palette.get("llm")
        assert tool is not None

    def test_get_returns_none_for_unknown(self, palette):
        """Should return None for an unknown tool name."""
        tool = palette.get("nonexistent_tool")
        assert tool is None

    def test_get_all_returns_dict(self, palette):
        """Should return all tools as a dict."""
        tools = palette.get_all()
        assert isinstance(tools, dict)
        assert "llm" in tools
        assert "bash" in tools
        assert "rss" in tools
        assert "qbit" in tools
        assert "filesystem" in tools
        assert "emby" in tools
        assert "anime_garden" in tools
        assert "notify" in tools

    def test_get_all_returns_copy(self, palette):
        """Should return a copy, not the internal dict."""
        tools1 = palette.get_all()
        tools2 = palette.get_all()
        assert tools1 is not tools2


class TestToolPaletteInit:
    def test_lazy_initialization(self, palette):
        """Should not initialize tools until first access."""
        assert palette._initialized is False
        palette.get("llm")
        assert palette._initialized is True

    def test_only_initializes_once(self, palette):
        """Should only initialize tools once."""
        palette.get("llm")
        tools1 = palette.get_all()
        palette.get("bash")
        tools2 = palette.get_all()
        # Same internal dict
        assert tools1 is not tools2  # get_all returns a copy
        # But the underlying tools are the same instances
        assert palette.get("llm") is palette.get("llm")


class TestToolPaletteHealthcheck:
    async def test_healthcheck_returns_results_for_all_tools(self, palette):
        """Should return health status for all tools."""
        results = await palette.healthcheck()
        assert isinstance(results, dict)
        assert "llm" in results
        assert "ok" in results["llm"]

    async def test_healthcheck_handles_tool_exception(self, palette):
        """Should handle exceptions from individual tool healthchecks."""
        # Ensure tools are initialized before replacing one with a mock
        palette.get("llm")
        failing_tool = AsyncMock()
        failing_tool.healthcheck.side_effect = RuntimeError("Tool broken")
        palette._tools["llm"] = failing_tool

        results = await palette.healthcheck()
        assert results["llm"]["ok"] is False
        assert "Tool broken" in results["llm"]["error"]
