"""AniList GraphQL tool for international anime metadata."""

from typing import Any

import httpx

from anime_agent.tools.base import BaseTool, ToolInput, ToolOutput

ANILIST_API_URL = "https://graphql.anilist.co"

_MEDIA_FIELDS = """
    id
    title { romaji native english }
    type
    format
    episodes
    status
    season
    seasonYear
    startDate { year month day }
    endDate { year month day }
    nextAiringEpisode { episode airingAt }
    coverImage { large }
    genres
    tags { name }
"""


class AniListToolInput(ToolInput):
    """Input for AniListTool."""

    action: str  # search / details / seasonal
    query: str | None = None
    media_id: int | None = None
    year: int | None = None
    season: str | None = None  # WINTER / SPRING / SUMMER / FALL


class AniListTool(BaseTool):
    """Fetch anime metadata from AniList GraphQL API."""

    name = "anilist"
    description = "Search and retrieve anime metadata from AniList."

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(timeout=30.0)

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Execute search, details, or seasonal action."""
        anilist_input = AniListToolInput.model_validate(input_data)

        if anilist_input.action == "search":
            if not anilist_input.query:
                return ToolOutput(success=False, error="query is required for search")
            return await self._search(anilist_input.query)
        if anilist_input.action == "details":
            if anilist_input.media_id is None:
                return ToolOutput(success=False, error="media_id is required for details")
            return await self._details(anilist_input.media_id)
        if anilist_input.action == "seasonal":
            if anilist_input.year is None or not anilist_input.season:
                return ToolOutput(success=False, error="year and season are required for seasonal")
            return await self._seasonal(anilist_input.year, anilist_input.season)

        return ToolOutput(success=False, error=f"Unknown action: {anilist_input.action}")

    async def _search(self, query: str) -> ToolOutput:
        graphql_query = f"""
        query ($search: String) {{
            Page (perPage: 10) {{
                media (search: $search, type: ANIME) {{
                    {_MEDIA_FIELDS}
                }}
            }}
        }}
        """
        result = await self._execute(graphql_query, {"search": query})
        if not result.success:
            return result
        media = result.data.get("data", {}).get("Page", {}).get("media", [])
        return ToolOutput(success=True, data={"media": [_normalize_media(m) for m in media]})

    async def _details(self, media_id: int) -> ToolOutput:
        graphql_query = f"""
        query ($id: Int) {{
            Media (id: $id, type: ANIME) {{
                {_MEDIA_FIELDS}
            }}
        }}
        """
        result = await self._execute(graphql_query, {"id": media_id})
        if not result.success:
            return result
        media = result.data.get("data", {}).get("Media")
        if not media:
            return ToolOutput(success=False, error=f"Media {media_id} not found")
        return ToolOutput(success=True, data={"media": _normalize_media(media)})

    async def _seasonal(self, year: int, season: str) -> ToolOutput:
        graphql_query = f"""
        query ($season: MediaSeason, $year: Int) {{
            Page (perPage: 50) {{
                media (season: $season, seasonYear: $year, type: ANIME) {{
                    {_MEDIA_FIELDS}
                }}
            }}
        }}
        """
        result = await self._execute(graphql_query, {"season": season.upper(), "year": year})
        if not result.success:
            return result
        media = result.data.get("data", {}).get("Page", {}).get("media", [])
        return ToolOutput(success=True, data={"media": [_normalize_media(m) for m in media]})

    async def healthcheck(self) -> ToolOutput:
        """Check AniList API reachability with a minimal GraphQL query."""
        result = await self._execute(
            "query { Page(perPage: 1) { media(type: ANIME) { id } } }",
            {},
        )
        if not result.success:
            return result
        return ToolOutput(success=True, data={"status": "ok"})

    async def _execute(self, query: str, variables: dict[str, Any]) -> ToolOutput:
        """Execute a GraphQL query and return raw data or error."""
        try:
            response = await self.client.post(
                ANILIST_API_URL,
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolOutput(success=False, error=f"AniList request failed: {exc}")

        data = response.json()
        if "errors" in data:
            return ToolOutput(success=False, error=f"AniList GraphQL error: {data['errors']}")
        return ToolOutput(success=True, data=data)


def _normalize_media(media: dict[str, Any]) -> dict[str, Any]:
    """Normalize AniList media response into a common dict."""
    title = media.get("title", {}) or {}
    next_ep = media.get("nextAiringEpisode")

    return {
        "anilist_id": media.get("id"),
        "title_romaji": title.get("romaji"),
        "title_native": title.get("native"),
        "title_english": title.get("english"),
        "type": media.get("type"),
        "format": media.get("format"),
        "total_episodes": media.get("episodes"),
        "status": media.get("status"),
        "season": media.get("season"),
        "season_year": media.get("seasonYear"),
        "next_airing_episode": next_ep.get("episode") if next_ep else None,
        "next_airing_at": next_ep.get("airingAt") if next_ep else None,
        "genres": media.get("genres", []),
        "tags": [tag.get("name") for tag in media.get("tags", []) if isinstance(tag, dict)],
        "cover_image": media.get("coverImage", {}).get("large")
        if media.get("coverImage")
        else None,
    }
