"""Tests for AniListTool."""

import respx
from httpx import Response

from anime_agent.tools.anilist_tool import AniListTool, AniListToolInput


@respx.mock
async def test_anilist_tool_searches_anime():
    """AniListTool should search anime and return normalized results."""
    api_response = {
        "data": {
            "Page": {
                "media": [
                    {
                        "id": 456,
                        "title": {"romaji": "Sousou no Frieren", "native": "葬送のフリーレン", "english": "Frieren"},
                        "type": "ANIME",
                        "format": "TV",
                        "episodes": 28,
                        "nextAiringEpisode": {"episode": 29, "airingAt": 1700000000},
                    }
                ]
            }
        }
    }
    route = respx.post("https://graphql.anilist.co").mock(return_value=Response(200, json=api_response))

    tool = AniListTool()
    result = await tool.invoke(AniListToolInput(action="search", query="Frieren"))

    assert result.success is True
    assert len(result.data["media"]) == 1
    media = result.data["media"][0]
    assert media["anilist_id"] == 456
    assert media["title_romaji"] == "Sousou no Frieren"
    assert media["title_native"] == "葬送のフリーレン"
    assert media["title_english"] == "Frieren"
    assert media["next_airing_episode"] == 29
    assert route.called


@respx.mock
async def test_anilist_tool_gets_media_details():
    """AniListTool should fetch media details by AniList ID."""
    api_response = {
        "data": {
            "Media": {
                "id": 456,
                "title": {"romaji": "Sousou no Frieren", "native": "葬送のフリーレン"},
                "type": "ANIME",
                "format": "TV",
                "episodes": 28,
                "status": "FINISHED",
                "season": "FALL",
                "seasonYear": 2023,
                "nextAiringEpisode": None,
            }
        }
    }
    route = respx.post("https://graphql.anilist.co").mock(return_value=Response(200, json=api_response))

    tool = AniListTool()
    result = await tool.invoke(AniListToolInput(action="details", media_id=456))

    assert result.success is True
    media = result.data["media"]
    assert media["anilist_id"] == 456
    assert media["status"] == "FINISHED"
    assert media["season"] == "FALL"
    assert media["season_year"] == 2023
    assert route.called


@respx.mock
async def test_anilist_tool_returns_error_on_http_failure():
    """AniListTool should return failed ToolOutput on HTTP errors."""
    respx.post("https://graphql.anilist.co").mock(return_value=Response(500))

    tool = AniListTool()
    result = await tool.invoke(AniListToolInput(action="search", query="test"))

    assert result.success is False
    assert result.error
