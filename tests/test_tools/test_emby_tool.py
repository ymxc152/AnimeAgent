"""Tests for EmbyTool."""

import respx
from httpx import Response

from anime_agent.tools.emby_tool import EmbyTool, EmbyToolInput


@respx.mock
async def test_emby_tool_refreshes_all_libraries():
    """EmbyTool should refresh all libraries."""
    route = respx.post("https://emby.example.com/emby/Library/Refresh").mock(
        return_value=Response(204)
    )

    tool = EmbyTool(
        host="https://emby.example.com",
        api_key="test-key",
        library_name="Anime",
    )
    result = await tool.invoke(EmbyToolInput(action="refresh_all"))

    assert result.success is True
    assert route.called


@respx.mock
async def test_emby_tool_finds_library_and_refreshes():
    """EmbyTool should find a library by name and refresh it."""
    respx.get("https://emby.example.com/emby/Library/SelectableMediaFolders").mock(
        return_value=Response(
            200,
            json=[
                {"Id": "lib-1", "Name": "Anime"},
                {"Id": "lib-2", "Name": "Movies"},
            ],
        )
    )
    refresh_route = respx.post("https://emby.example.com/emby/Items/lib-1/Refresh").mock(
        return_value=Response(204)
    )

    tool = EmbyTool(
        host="https://emby.example.com",
        api_key="test-key",
        library_name="Anime",
    )
    result = await tool.invoke(EmbyToolInput(action="refresh_library"))

    assert result.success is True
    assert refresh_route.called


@respx.mock
async def test_emby_tool_returns_error_when_library_not_found():
    """EmbyTool should fail when the configured library does not exist."""
    respx.get("https://emby.example.com/emby/Library/SelectableMediaFolders").mock(
        return_value=Response(200, json=[{"Id": "lib-2", "Name": "Movies"}])
    )

    tool = EmbyTool(
        host="https://emby.example.com",
        api_key="test-key",
        library_name="Anime",
    )
    result = await tool.invoke(EmbyToolInput(action="refresh_library"))

    assert result.success is False
    assert "not found" in result.error.lower()


async def test_emby_tool_returns_error_without_api_key(monkeypatch):
    """EmbyTool should fail if no API key is configured."""
    monkeypatch.setattr("anime_agent.tools.emby_tool.settings.emby_api_key", None)
    tool = EmbyTool(host="https://emby.example.com", api_key=None, library_name="Anime")
    result = await tool.invoke(EmbyToolInput(action="refresh_all"))

    assert result.success is False
    assert "api key" in result.error.lower()
