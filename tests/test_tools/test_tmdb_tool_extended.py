"""Extended tests for TMDBTool — details, error handling, edge cases."""

import respx
from httpx import Response

from anime_agent.tools.tmdb_tool import TMDBTool, TMDBToolInput

# ── details action ──────────────────────────────────────────────────────


class TestTMDBDetails:
    @respx.mock
    async def test_gets_show_details(self):
        api_response = {
            "id": 789,
            "name": "Frieren",
            "number_of_seasons": 2,
            "number_of_episodes": 28,
            "first_air_date": "2023-09-29",
        }
        respx.get("https://api.themoviedb.org/3/tv/789").mock(
            return_value=Response(200, json=api_response)
        )

        tool = TMDBTool(api_key="test-key")
        result = await tool.invoke(TMDBToolInput(action="details", tmdb_id=789))

        assert result.success is True
        show = result.data["show"]
        assert show["tmdb_id"] == 789
        assert show["name"] == "Frieren"
        assert show["number_of_seasons"] == 2

    @respx.mock
    async def test_details_handles_http_error(self):
        respx.get("https://api.themoviedb.org/3/tv/999").mock(
            return_value=Response(404, json={"status_message": "Not found"})
        )

        tool = TMDBTool(api_key="test-key")
        result = await tool.invoke(TMDBToolInput(action="details", tmdb_id=999))

        assert result.success is False
        assert "failed" in result.error.lower()


# ── Input validation ────────────────────────────────────────────────────


class TestTMDBInputValidation:
    async def test_search_requires_query(self):
        tool = TMDBTool(api_key="test-key")
        result = await tool.invoke(TMDBToolInput(action="search", query=None))

        assert result.success is False
        assert "query" in result.error.lower()

    async def test_details_requires_tmdb_id(self):
        tool = TMDBTool(api_key="test-key")
        result = await tool.invoke(TMDBToolInput(action="details"))

        assert result.success is False
        assert "tmdb_id" in result.error.lower()

    async def test_season_requires_tmdb_id(self):
        tool = TMDBTool(api_key="test-key")
        result = await tool.invoke(TMDBToolInput(action="season"))

        assert result.success is False
        assert "tmdb_id" in result.error.lower()

    async def test_unknown_action(self):
        tool = TMDBTool(api_key="test-key")
        result = await tool.invoke(TMDBToolInput(action="nonexistent"))

        assert result.success is False
        assert "Unknown action" in result.error


# ── HTTP error handling ─────────────────────────────────────────────────


class TestTMDBHttpErrors:
    @respx.mock
    async def test_search_handles_http_error(self):
        respx.get("https://api.themoviedb.org/3/search/tv").mock(
            return_value=Response(429, json={"status_message": "Rate limited"})
        )

        tool = TMDBTool(api_key="test-key")
        result = await tool.invoke(TMDBToolInput(action="search", query="Frieren"))

        assert result.success is False
        assert "failed" in result.error.lower()

    @respx.mock
    async def test_season_handles_http_error(self):
        respx.get("https://api.themoviedb.org/3/tv/789/season/1").mock(
            return_value=Response(500, json={"status_message": "Server error"})
        )

        tool = TMDBTool(api_key="test-key")
        result = await tool.invoke(TMDBToolInput(action="season", tmdb_id=789, season_number=1))

        assert result.success is False
        assert "failed" in result.error.lower()


# ── Healthcheck ─────────────────────────────────────────────────────────


class TestTMDBHealthcheck:
    async def test_healthcheck_fails_without_api_key(self):
        tool = TMDBTool(api_key="")
        result = await tool.healthcheck()

        assert result.success is False
        assert "api key" in result.error.lower()

    async def test_healthcheck_succeeds_with_api_key(self):
        tool = TMDBTool(api_key="test-key")
        result = await tool.healthcheck()

        assert result.success is True
        assert result.data["status"] == "ok"


# ── Search with empty results ───────────────────────────────────────────


class TestTMDBSearchEdgeCases:
    @respx.mock
    async def test_search_returns_empty_results(self):
        respx.get("https://api.themoviedb.org/3/search/tv").mock(
            return_value=Response(200, json={"results": []})
        )

        tool = TMDBTool(api_key="test-key")
        result = await tool.invoke(TMDBToolInput(action="search", query="Nonexistent"))

        assert result.success is True
        assert result.data["results"] == []

    @respx.mock
    async def test_season_returns_empty_episodes(self):
        respx.get("https://api.themoviedb.org/3/tv/789/season/99").mock(
            return_value=Response(200, json={"season_number": 99, "name": "Special", "episodes": []})
        )

        tool = TMDBTool(api_key="test-key")
        result = await tool.invoke(TMDBToolInput(action="season", tmdb_id=789, season_number=99))

        assert result.success is True
        assert result.data["season"]["episodes"] == []
