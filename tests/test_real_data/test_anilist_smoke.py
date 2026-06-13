"""Real-data smoke test for AniListTool."""

import pytest

from anime_agent.tools.anilist_tool import AniListTool, AniListToolInput


@pytest.mark.real_data
async def test_anilist_seasonal_returns_anime() -> None:
    """AniList should return non-empty seasonal anime data."""
    tool = AniListTool()
    result = await tool.invoke(
        AniListToolInput(action="seasonal", year=2024, season="FALL")
    )
    assert result.success, result.error
    media = result.data.get("media", [])
    assert len(media) > 0
    first = media[0]
    assert "title_romaji" in first or "title" in first


@pytest.mark.real_data
async def test_anilist_details_returns_info() -> None:
    """AniList should return details for a known title (Attack on Titan)."""
    tool = AniListTool()
    result = await tool.invoke(AniListToolInput(action="details", media_id=16498))
    assert result.success, result.error
    media = result.data.get("media", {})
    assert isinstance(media, dict)
    assert media.get("title_romaji")
