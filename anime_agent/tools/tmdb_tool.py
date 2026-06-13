"""TMDB tool for TV show metadata and season/episode mapping."""

import httpx

from anime_agent.config import settings
from anime_agent.tools.base import BaseTool, ToolInput, ToolOutput

TMDB_API_BASE = "https://api.themoviedb.org/3"


class TMDBToolInput(ToolInput):
    """Input for TMDBTool."""

    action: str  # search / details / season
    query: str | None = None
    tmdb_id: int | None = None
    season_number: int = 1


class TMDBTool(BaseTool):
    """Fetch TV metadata from The Movie Database (TMDB)."""

    name = "tmdb"
    description = "Search TMDB and retrieve season/episode mappings for Emby."

    def __init__(self, client: httpx.AsyncClient | None = None, api_key: str | None = None):
        self.client = client or httpx.AsyncClient()
        self.api_key = api_key if api_key is not None else settings.tmdb_api_key

    async def healthcheck(self) -> ToolOutput:
        """Check that TMDB API key is configured."""
        if not self.api_key:
            return ToolOutput(success=False, error="TMDB api key is not configured")
        return ToolOutput(success=True, data={"status": "ok"})

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Execute search, details, or season action."""
        tmdb_input = TMDBToolInput.model_validate(input_data)

        if not self.api_key:
            return ToolOutput(success=False, error="TMDB api key is required")

        if tmdb_input.action == "search":
            if not tmdb_input.query:
                return ToolOutput(success=False, error="query is required for search")
            return await self._search(tmdb_input.query)
        if tmdb_input.action == "details":
            if tmdb_input.tmdb_id is None:
                return ToolOutput(success=False, error="tmdb_id is required for details")
            return await self._details(tmdb_input.tmdb_id)
        if tmdb_input.action == "season":
            if tmdb_input.tmdb_id is None:
                return ToolOutput(success=False, error="tmdb_id is required for season")
            return await self._season(tmdb_input.tmdb_id, tmdb_input.season_number)

        return ToolOutput(success=False, error=f"Unknown action: {tmdb_input.action}")

    async def _search(self, query: str) -> ToolOutput:
        try:
            response = await self.client.get(
                f"{TMDB_API_BASE}/search/tv",
                params={"api_key": self.api_key, "query": query},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolOutput(success=False, error=f"TMDB search failed: {exc}")

        data = response.json()
        results = [
            {
                "tmdb_id": item.get("id"),
                "name": item.get("name"),
                "first_air_date": item.get("first_air_date"),
            }
            for item in data.get("results", [])
        ]
        return ToolOutput(success=True, data={"results": results})

    async def _details(self, tmdb_id: int) -> ToolOutput:
        try:
            response = await self.client.get(
                f"{TMDB_API_BASE}/tv/{tmdb_id}",
                params={"api_key": self.api_key},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolOutput(success=False, error=f"TMDB details failed: {exc}")

        data = response.json()
        return ToolOutput(
            success=True,
            data={
                "show": {
                    "tmdb_id": data.get("id"),
                    "name": data.get("name"),
                    "number_of_seasons": data.get("number_of_seasons"),
                    "number_of_episodes": data.get("number_of_episodes"),
                    "first_air_date": data.get("first_air_date"),
                }
            },
        )

    async def _season(self, tmdb_id: int, season_number: int) -> ToolOutput:
        try:
            response = await self.client.get(
                f"{TMDB_API_BASE}/tv/{tmdb_id}/season/{season_number}",
                params={"api_key": self.api_key},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolOutput(success=False, error=f"TMDB season failed: {exc}")

        data = response.json()
        episodes = [
            {
                "episode_number": ep.get("episode_number"),
                "name": ep.get("name"),
                "air_date": ep.get("air_date"),
            }
            for ep in data.get("episodes", [])
        ]
        return ToolOutput(
            success=True,
            data={
                "season": {
                    "season_number": data.get("season_number"),
                    "name": data.get("name"),
                    "episodes": episodes,
                }
            },
        )
