"""Tests for TMDBTool."""

import respx
from httpx import Response

from anime_agent.tools.tmdb_tool import TMDBTool, TMDBToolInput


@respx.mock
async def test_tmdb_tool_searches_tv():
    """TMDBTool should search TV shows and return normalized results."""
    api_response = {
        "results": [
            {"id": 789, "name": "Frieren: Beyond Journey's End", "first_air_date": "2023-09-29"}
        ]
    }
    route = respx.get("https://api.themoviedb.org/3/search/tv").mock(
        return_value=Response(200, json=api_response)
    )

    tool = TMDBTool(api_key="test-key")
    result = await tool.invoke(TMDBToolInput(action="search", query="Frieren"))

    assert result.success is True
    assert len(result.data["results"]) == 1
    show = result.data["results"][0]
    assert show["tmdb_id"] == 789
    assert show["name"] == "Frieren: Beyond Journey's End"
    assert route.called


@respx.mock
async def test_tmdb_tool_gets_season_details():
    """TMDBTool should fetch season details for episode mapping."""
    api_response = {
        "id": 12345,
        "name": "Season 1",
        "season_number": 1,
        "episodes": [
            {"episode_number": 1, "name": "The Journey's End", "air_date": "2023-09-29"},
            {"episode_number": 2, "name": "The Priest's Lie", "air_date": "2023-10-06"},
        ],
    }
    route = respx.get("https://api.themoviedb.org/3/tv/789/season/1").mock(
        return_value=Response(200, json=api_response)
    )

    tool = TMDBTool(api_key="test-key")
    result = await tool.invoke(TMDBToolInput(action="season", tmdb_id=789, season_number=1))

    assert result.success is True
    season = result.data["season"]
    assert season["season_number"] == 1
    assert len(season["episodes"]) == 2
    assert season["episodes"][0]["episode_number"] == 1
    assert route.called


async def test_tmdb_tool_returns_error_without_credentials(monkeypatch):
    """TMDBTool should fail if no API key is configured."""
    monkeypatch.setattr("anime_agent.tools.tmdb_tool.settings.tmdb_api_key", None)
    tool = TMDBTool(api_key=None)
    result = await tool.invoke(TMDBToolInput(action="search", query="Frieren"))

    assert result.success is False
    assert "api key" in result.error.lower()
