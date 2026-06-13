"""Real-data smoke test using the local Anime Garden RSS fixture."""

from pathlib import Path

import pytest
import respx
from httpx import Response

from anime_agent.tools.rss_tool import RSSTool, RSSToolInput


@pytest.fixture
def animes_garden_feed() -> str:
    """Return the real Anime Garden RSS fixture as text."""
    fixture_path = Path(__file__).parent.parent / "test_tools" / "fixtures" / "animes_garden_feed.xml"
    return fixture_path.read_text(encoding="utf-8")


@pytest.mark.real_data
@respx.mock
async def test_rss_smoke_parses_animes_garden_feed(animes_garden_feed: str) -> None:
    """RSSTool should parse the real Anime Garden fixture."""
    route = respx.get("https://api.animes.garden/feed.xml").mock(
        return_value=Response(200, text=animes_garden_feed)
    )

    tool = RSSTool()
    result = await tool.invoke(RSSToolInput(url="https://api.animes.garden/feed.xml"))

    assert result.success, result.error
    assert len(result.data["entries"]) == 101
    first = result.data["entries"][0]
    assert first["title"]
    assert first["link"]
    assert first["published"]
    assert route.called
