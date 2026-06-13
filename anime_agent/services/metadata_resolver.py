"""Metadata resolver with Bangumi priority and AniList/TMDB fallback."""

from typing import Any

from anime_agent.tools.anilist_tool import AniListTool, AniListToolInput
from anime_agent.tools.bangumi_tool import BangumiTool, BangumiToolInput
from anime_agent.tools.base import BaseTool, ToolOutput
from anime_agent.tools.tmdb_tool import TMDBTool


class MetadataResolver:
    """Resolve anime metadata across Bangumi, AniList, and TMDB."""

    def __init__(
        self,
        bangumi: BaseTool | None = None,
        anilist: BaseTool | None = None,
        tmdb: BaseTool | None = None,
    ):
        self.bangumi = bangumi or BangumiTool()
        self.anilist = anilist or AniListTool()
        self.tmdb = tmdb or TMDBTool()

    async def search(self, query: str) -> ToolOutput:
        """Search for anime candidates. Bangumi first, AniList fallback."""
        bgm_result = await self.bangumi.invoke(BangumiToolInput(action="search", query=query))
        if bgm_result.success and bgm_result.data.get("subjects"):
            candidates = [_unify_bangumi_subject(s) for s in bgm_result.data["subjects"]]
            return ToolOutput(success=True, data={"candidates": candidates, "source": "bangumi"})

        anilist_result = await self.anilist.invoke(AniListToolInput(action="search", query=query))
        if anilist_result.success and anilist_result.data.get("media"):
            candidates = [_unify_anilist_media(m) for m in anilist_result.data["media"]]
            return ToolOutput(success=True, data={"candidates": candidates, "source": "anilist"})

        errors = []
        if not bgm_result.success:
            errors.append(f"Bangumi: {bgm_result.error}")
        if not anilist_result.success:
            errors.append(f"AniList: {anilist_result.error}")
        if not errors:
            errors.append("No candidates found")
        return ToolOutput(success=False, error="; ".join(errors))

    async def get_details(
        self, bangumi_id: int | None = None, anilist_id: int | None = None
    ) -> ToolOutput:
        """Fetch and cross-reference details from Bangumi and AniList."""
        details: dict[str, Any] = {}

        if bangumi_id:
            bgm_result = await self.bangumi.invoke(
                BangumiToolInput(action="details", subject_id=bangumi_id)
            )
            if bgm_result.success:
                details = _unify_bangumi_subject(bgm_result.data["subject"])

        if anilist_id:
            anilist_result = await self.anilist.invoke(
                AniListToolInput(action="details", media_id=anilist_id)
            )
            if anilist_result.success:
                anilist_details = _unify_anilist_media(anilist_result.data["media"])
                details = _merge_details(details, anilist_details)
        elif details and details.get("title_romaji"):
            # Try to cross-reference AniList by romaji title
            anilist_result = await self.anilist.invoke(
                AniListToolInput(action="search", query=details["title_romaji"])
            )
            if anilist_result.success and anilist_result.data.get("media"):
                anilist_details = _unify_anilist_media(anilist_result.data["media"][0])
                details = _merge_details(details, anilist_details)

        if not details:
            return ToolOutput(success=False, error="Could not resolve metadata")

        return ToolOutput(success=True, data={"details": details})

    async def get_seasonal(self, year: int, season: str) -> ToolOutput:
        """Fetch seasonal anime with Bangumi priority and AniList fallback."""
        bgm_result = await self.bangumi.invoke(
            BangumiToolInput(action="seasonal", year=year, season=season)
        )
        if bgm_result.success and bgm_result.data.get("subjects"):
            candidates = [_unify_bangumi_subject(s) for s in bgm_result.data["subjects"]]
            return ToolOutput(success=True, data={"candidates": candidates, "source": "bangumi"})

        anilist_result = await self.anilist.invoke(
            AniListToolInput(action="seasonal", year=year, season=season)
        )
        if not anilist_result.success:
            return anilist_result
        candidates = [_unify_anilist_media(m) for m in anilist_result.data.get("media", [])]
        return ToolOutput(success=True, data={"candidates": candidates, "source": "anilist"})


def _unify_bangumi_subject(subject: dict[str, Any]) -> dict[str, Any]:
    """Normalize Bangumi subject to unified metadata dict."""
    tags = subject.get("tags", []) or []
    return {
        "bangumi_id": subject.get("bangumi_id"),
        "anilist_id": subject.get("anilist_id"),
        "tmdb_id": subject.get("tmdb_id"),
        "title_romaji": subject.get("title_romaji"),
        "title_native": subject.get("title_native"),
        "title_chinese": subject.get("title_chinese"),
        "format": subject.get("format"),
        "type": subject.get("type"),
        "air_date": subject.get("air_date"),
        "total_episodes": subject.get("total_episodes"),
        "tags": tags,
        "genres": subject.get("genres", []) or tags,
        "image": subject.get("image"),
    }


def _unify_anilist_media(media: dict[str, Any]) -> dict[str, Any]:
    """Normalize AniList media to unified metadata dict."""
    return {
        "anilist_id": media.get("anilist_id"),
        "bangumi_id": media.get("bangumi_id"),
        "tmdb_id": media.get("tmdb_id"),
        "title_romaji": media.get("title_romaji"),
        "title_native": media.get("title_native"),
        "title_english": media.get("title_english"),
        "format": media.get("format"),
        "type": media.get("type"),
        "season": media.get("season"),
        "season_year": media.get("season_year"),
        "status": media.get("status"),
        "total_episodes": media.get("total_episodes"),
        "next_airing_episode": media.get("next_airing_episode"),
        "next_airing_at": media.get("next_airing_at"),
        "tags": media.get("tags", []) or media.get("genres", []),
        "image": media.get("cover_image"),
    }


def _merge_details(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Merge metadata from two sources, preferring primary for titles."""
    merged = {**fallback, **primary}
    # Fill missing fields from fallback
    for key, value in fallback.items():
        if not merged.get(key):
            merged[key] = value
    return merged
