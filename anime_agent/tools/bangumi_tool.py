"""Bangumi (bgm.tv) tool for Chinese anime metadata."""

from typing import Any
from urllib.parse import quote

import httpx

from anime_agent.tools.base import BaseTool, ToolInput, ToolOutput

BANGUMI_API_BASE = "https://api.bgm.tv"


class BangumiToolInput(ToolInput):
    """Input for BangumiTool."""

    action: str  # search / details / calendar / seasonal
    query: str | None = None
    subject_id: int | None = None
    year: int | None = None
    season: str | None = None  # WINTER / SPRING / SUMMER / FALL


class BangumiTool(BaseTool):
    """Fetch Chinese anime metadata from Bangumi."""

    name = "bangumi"
    description = "Search and retrieve anime metadata from Bangumi (bgm.tv)."

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(
            headers={"User-Agent": "AnimeAgent/0.1.0 (contact@example.com)"},
            timeout=30.0,
        )

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Execute search or details action."""
        bgm_input = BangumiToolInput.model_validate(input_data)

        if bgm_input.action == "search":
            if not bgm_input.query:
                return ToolOutput(success=False, error="query is required for search")
            return await self._search(bgm_input.query)
        if bgm_input.action == "details":
            if bgm_input.subject_id is None:
                return ToolOutput(success=False, error="subject_id is required for details")
            return await self._details(bgm_input.subject_id)
        if bgm_input.action == "calendar":
            return await self._calendar()
        if bgm_input.action == "seasonal":
            return await self._seasonal(bgm_input.year, bgm_input.season)

        return ToolOutput(success=False, error=f"Unknown action: {bgm_input.action}")

    async def healthcheck(self) -> ToolOutput:
        """Check Bangumi API reachability."""
        try:
            response = await self.client.get(BANGUMI_API_BASE)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolOutput(success=False, error=f"Bangumi healthcheck failed: {exc}")
        return ToolOutput(success=True, data={"status": "ok"})

    async def _search(self, query: str) -> ToolOutput:
        url = f"{BANGUMI_API_BASE}/search/subject/{quote(query)}"
        try:
            response = await self.client.get(url, params={"type": 2, "responseGroup": "large"})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolOutput(success=False, error=f"Bangumi search failed: {exc}")

        data = response.json()
        subjects = [_normalize_subject(item) for item in data.get("list", [])]
        return ToolOutput(
            success=True, data={"subjects": subjects, "total": data.get("results", 0)}
        )

    async def _details(self, subject_id: int) -> ToolOutput:
        url = f"{BANGUMI_API_BASE}/v0/subjects/{subject_id}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolOutput(success=False, error=f"Bangumi details failed: {exc}")

        data = response.json()
        return ToolOutput(success=True, data={"subject": _normalize_subject(data)})

    async def _calendar(self) -> ToolOutput:
        """Fetch currently airing anime from Bangumi calendar."""
        url = f"{BANGUMI_API_BASE}/calendar"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolOutput(success=False, error=f"Bangumi calendar failed: {exc}")

        data = response.json()
        subjects: list[dict[str, Any]] = []
        for day in data:
            for item in day.get("items", []):
                subjects.append(_normalize_subject(item))
        return ToolOutput(success=True, data={"subjects": subjects})

    async def _seasonal(self, year: int | None = None, season: str | None = None) -> ToolOutput:
        """Fetch seasonal anime by filtering calendar results by air_date.

        Bangumi ``/calendar`` only returns the currently airing slate, so we
        filter by the requested year and season months.  If no year/season is
        provided, all calendar items are returned.
        """
        calendar_result = await self._calendar()
        if not calendar_result.success:
            return calendar_result

        all_subjects = calendar_result.data.get("subjects", [])
        if year is None or season is None:
            return ToolOutput(success=True, data={"subjects": all_subjects})

        season_months = {
            "WINTER": (1, 3),
            "SPRING": (4, 6),
            "SUMMER": (7, 9),
            "FALL": (10, 12),
        }
        months = season_months.get(season.upper(), (1, 12))

        filtered: list[dict[str, Any]] = []
        for subject in all_subjects:
            air_date = subject.get("air_date", "")
            if not air_date:
                continue
            try:
                parts = air_date.split("-")
                air_year = int(parts[0])
                air_month = int(parts[1]) if len(parts) > 1 else 0
            except (ValueError, IndexError):
                continue
            if air_year == year and months[0] <= air_month <= months[1]:
                filtered.append(subject)

        return ToolOutput(success=True, data={"subjects": filtered})


def _normalize_subject(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Bangumi subject response into a common dict."""
    name = item.get("name", "")
    name_cn = item.get("name_cn", "")
    title_chinese = name_cn or name

    tags = []
    for tag in item.get("tags", []):
        if isinstance(tag, dict):
            tags.append(tag.get("name", ""))
        elif isinstance(tag, str):
            tags.append(tag)

    eps = item.get("eps")
    total_episodes = int(eps) if eps else None

    # Map Bangumi platform/type hints to a generic format for filtering.
    # Bangumi does not expose a direct "format" field like AniList, so we
    # default to "TV" and only override for obvious OVA/movie cases.
    platform = str(item.get("platform", "")).lower()
    name_lower = name.lower()
    if "movie" in platform or "剧场版" in name_lower:
        format_value = "MOVIE"
    elif "ova" in platform or "oav" in name_lower:
        format_value = "OVA"
    elif "ona" in platform:
        format_value = "ONA"
    else:
        format_value = "TV"

    return {
        "bangumi_id": item.get("id"),
        "title_native": name,
        "title_chinese": title_chinese,
        "title_romaji": name if not name_cn else name,
        "type": item.get("type"),
        "format": format_value,
        "air_date": item.get("air_date"),
        "total_episodes": total_episodes,
        "summary": item.get("summary", ""),
        "tags": tags,
        "genres": tags,
        "image": item.get("images", {}).get("large")
        if isinstance(item.get("images"), dict)
        else None,
    }
