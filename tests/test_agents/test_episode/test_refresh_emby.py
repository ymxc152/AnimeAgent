"""Tests for refresh_emby node."""

from unittest.mock import AsyncMock

from anime_agent.agents.episode.nodes.refresh_emby import RefreshEmbyNode
from anime_agent.tools.base import ToolOutput


def _state() -> dict:
    return {
        "subscription_id": 42,
        "episode_number": 1,
        "organized_path": "/media/Anime/Test Anime",
    }


async def test_refresh_emby_completes_on_success():
    """refresh_emby should mark the workflow completed when refresh succeeds."""
    emby_tool = AsyncMock()
    emby_tool.invoke.return_value = ToolOutput(
        success=True, data={"refreshed": True, "library_id": "1"}
    )

    node = RefreshEmbyNode(emby_tool=emby_tool)
    result = await node(_state())

    assert result["status"] == "completed"
    assert result["emby_refreshed"] is True
    emby_tool.invoke.assert_awaited_once()


async def test_refresh_emby_fails_on_tool_error():
    """refresh_emby should fail when Emby returns an error."""
    emby_tool = AsyncMock()
    emby_tool.invoke.return_value = ToolOutput(success=False, error="Emby unreachable")

    node = RefreshEmbyNode(emby_tool=emby_tool)
    result = await node(_state())

    assert result["status"] == "failed"
    assert "Emby unreachable" in result["errors"][0]
