"""Tests for tool-level healthcheck methods used by pre-flight checks."""

from pathlib import Path

import respx
from httpx import Response

from anime_agent.tools.anilist_tool import AniListTool
from anime_agent.tools.bangumi_tool import BangumiTool
from anime_agent.tools.emby_tool import EmbyTool
from anime_agent.tools.filesystem_tool import FileSystemTool
from anime_agent.tools.tmdb_tool import TMDBTool


@respx.mock
async def test_anilist_healthcheck_returns_ok_on_valid_response():
    """AniList healthcheck should succeed when the API responds."""
    route = respx.post("https://graphql.anilist.co").mock(
        return_value=Response(200, json={"data": {"Page": {"media": []}}})
    )

    tool = AniListTool()
    result = await tool.healthcheck()

    assert result.success is True
    assert result.data.get("status") == "ok"
    assert route.called


@respx.mock
async def test_anilist_healthcheck_fails_on_http_error():
    """AniList healthcheck should fail when the API is unreachable."""
    respx.post("https://graphql.anilist.co").mock(return_value=Response(500))

    tool = AniListTool()
    result = await tool.healthcheck()

    assert result.success is False
    assert result.error


@respx.mock
async def test_bangumi_healthcheck_returns_ok_on_valid_response():
    """Bangumi healthcheck should succeed when the API responds."""
    route = respx.get("https://api.bgm.tv/").mock(return_value=Response(200, text="ok"))

    tool = BangumiTool()
    result = await tool.healthcheck()

    assert result.success is True
    assert result.data.get("status") == "ok"
    assert route.called


@respx.mock
async def test_bangumi_healthcheck_fails_on_http_error():
    """Bangumi healthcheck should fail when the API is unreachable."""
    respx.get("https://api.bgm.tv/").mock(return_value=Response(503))

    tool = BangumiTool()
    result = await tool.healthcheck()

    assert result.success is False
    assert result.error


@respx.mock
async def test_emby_healthcheck_returns_ok_on_valid_response():
    """Emby healthcheck should succeed when the public info endpoint responds."""
    route = respx.get("http://localhost:8096/emby/System/Info/Public").mock(
        return_value=Response(200, json={"ServerName": "Emby"})
    )

    tool = EmbyTool(host="http://localhost:8096")
    result = await tool.healthcheck()

    assert result.success is True
    assert result.data.get("status") == "ok"
    assert route.called


@respx.mock
async def test_emby_healthcheck_fails_on_http_error():
    """Emby healthcheck should fail when the server is unreachable."""
    respx.get("http://localhost:8096/emby/System/Info/Public").mock(return_value=Response(500))

    tool = EmbyTool(host="http://localhost:8096")
    result = await tool.healthcheck()

    assert result.success is False
    assert result.error


async def test_filesystem_healthcheck_passes_when_library_path_exists(tmp_path):
    """Filesystem healthcheck should succeed when the media library path exists."""
    tool = FileSystemTool(library_path=str(tmp_path))
    result = await tool.healthcheck()

    assert result.success is True
    assert result.data.get("status") == "ok"
    assert Path(result.data["path"]).exists()


async def test_filesystem_healthcheck_fails_when_library_path_missing():
    """Filesystem healthcheck should fail when the configured path does not exist."""
    tool = FileSystemTool(library_path="/nonexistent/anime/library")
    result = await tool.healthcheck()

    assert result.success is False
    assert "does not exist" in result.error.lower()


async def test_tmdb_healthcheck_passes_with_api_key():
    """TMDB healthcheck should succeed when an API key is configured."""
    tool = TMDBTool(api_key="fake-key")
    result = await tool.healthcheck()

    assert result.success is True
    assert result.data.get("status") == "ok"


async def test_tmdb_healthcheck_fails_without_api_key(monkeypatch):
    """TMDB healthcheck should fail when no API key is configured."""
    monkeypatch.setattr("anime_agent.tools.tmdb_tool.settings.tmdb_api_key", None)
    tool = TMDBTool(api_key=None)
    result = await tool.healthcheck()

    assert result.success is False
    assert "api key" in result.error.lower()
