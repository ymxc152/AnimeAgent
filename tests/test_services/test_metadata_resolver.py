"""Tests for MetadataResolver."""

from unittest.mock import AsyncMock

from anime_agent.services.metadata_resolver import MetadataResolver
from anime_agent.tools.base import ToolOutput


def _bangumi_subject(bangumi_id: int = 123, title: str = "葬送的芙莉莲") -> dict:
    return {
        "bangumi_id": bangumi_id,
        "title_chinese": title,
        "title_native": title,
        "title_romaji": "Sousou no Frieren",
        "type": 2,
        "air_date": "2023-09-29",
        "total_episodes": 28,
        "tags": ["奇幻", "冒险"],
    }


def _anilist_media(anilist_id: int = 456) -> dict:
    return {
        "anilist_id": anilist_id,
        "title_romaji": "Sousou no Frieren",
        "title_native": "葬送のフリーレン",
        "title_english": "Frieren: Beyond Journey's End",
        "format": "TV",
        "total_episodes": 28,
        "status": "FINISHED",
        "season": "FALL",
        "season_year": 2023,
        "next_airing_episode": None,
        "genres": ["Adventure", "Drama"],
    }


async def test_resolver_prefers_bangumi_search_results():
    """Resolver should return Bangumi results when available."""
    bangumi = AsyncMock()
    bangumi.invoke.return_value = ToolOutput(
        success=True, data={"subjects": [_bangumi_subject()]}
    )
    anilist = AsyncMock()

    resolver = MetadataResolver(bangumi=bangumi, anilist=anilist)
    result = await resolver.search("葬送的芙莉莲")

    assert result.success is True
    assert len(result.data["candidates"]) == 1
    assert result.data["candidates"][0]["bangumi_id"] == 123
    assert result.data["source"] == "bangumi"
    anilist.invoke.assert_not_awaited()


async def test_resolver_fallback_to_anilist_when_bangumi_empty():
    """Resolver should fallback to AniList when Bangumi returns no results."""
    bangumi = AsyncMock()
    bangumi.invoke.return_value = ToolOutput(success=True, data={"subjects": []})
    anilist = AsyncMock()
    anilist.invoke.return_value = ToolOutput(
        success=True, data={"media": [_anilist_media()]}
    )

    resolver = MetadataResolver(bangumi=bangumi, anilist=anilist)
    result = await resolver.search("Frieren")

    assert result.success is True
    assert len(result.data["candidates"]) == 1
    assert result.data["candidates"][0]["anilist_id"] == 456
    assert result.data["source"] == "anilist"


async def test_resolver_returns_error_when_both_sources_fail():
    """Resolver should fail when both Bangumi and AniList fail."""
    bangumi = AsyncMock()
    bangumi.invoke.return_value = ToolOutput(success=False, error="Bangumi down")
    anilist = AsyncMock()
    anilist.invoke.return_value = ToolOutput(success=False, error="AniList down")

    resolver = MetadataResolver(bangumi=bangumi, anilist=anilist)
    result = await resolver.search("Frieren")

    assert result.success is False
    assert "Bangumi" in result.error and "AniList" in result.error


async def test_resolver_cross_references_anilist_for_bangumi_subject():
    """Resolver should enrich Bangumi subject with AniList IDs when possible."""
    bangumi = AsyncMock()
    bangumi.invoke.return_value = ToolOutput(
        success=True,
        data={
            "subject": {
                **_bangumi_subject(),
                "anilist_id": 456,
            }
        },
    )
    anilist = AsyncMock()
    anilist.invoke.return_value = ToolOutput(
        success=True, data={"media": [_anilist_media()]}
    )

    resolver = MetadataResolver(bangumi=bangumi, anilist=anilist)
    result = await resolver.get_details(bangumi_id=123)

    assert result.success is True
    details = result.data["details"]
    assert details["bangumi_id"] == 123
    assert details["anilist_id"] == 456
    assert details["title_chinese"] == "葬送的芙莉莲"
    assert details["title_english"] == "Frieren: Beyond Journey's End"
