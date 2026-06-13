"""Tests for RSSTool."""

from pathlib import Path

import pytest
import respx
from httpx import Response

from anime_agent.tools.rss_tool import RSSTool, RSSToolInput, clear_rss_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear RSS cache before each test to avoid cross-test interference."""
    clear_rss_cache()
    yield
    clear_rss_cache()


@respx.mock
async def test_rss_tool_parses_entries_from_feed():
    """RSSTool should fetch a feed and return parsed entries."""
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>[SubGroup] Anime Title - 01 [1080p].mkv</title>
          <link>https://example.com/torrent/123</link>
          <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
          <enclosure url="https://example.com/torrent/123.torrent" length="536870912" type="application/x-bittorrent" />
        </item>
      </channel>
    </rss>
    """
    route = respx.get("https://example.com/rss").mock(return_value=Response(200, text=rss_xml))

    tool = RSSTool()
    result = await tool.invoke(RSSToolInput(url="https://example.com/rss"))

    assert result.success is True
    assert "entries" in result.data
    assert len(result.data["entries"]) == 1
    entry = result.data["entries"][0]
    assert entry["title"] == "[SubGroup] Anime Title - 01 [1080p].mkv"
    assert entry["link"] == "https://example.com/torrent/123.torrent"
    assert entry["published"] == "2024-01-01T00:00:00+00:00"
    assert entry["size"] == 536870912
    assert route.called


@respx.mock
async def test_rss_tool_returns_error_on_http_failure():
    """RSSTool should return a failed ToolOutput when the feed is unreachable."""
    respx.get("https://example.com/rss").mock(return_value=Response(500))

    tool = RSSTool()
    result = await tool.invoke(RSSToolInput(url="https://example.com/rss"))

    assert result.success is False
    assert result.error


@respx.mock
async def test_rss_tool_applies_parser_rules():
    """RSSTool should filter entries by include/exclude regex rules."""
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>[SubGroup] Anime - 01 [1080p].mkv</title>
          <link>https://example.com/1</link>
        </item>
        <item>
          <title>[SubGroup] Anime - 01 [720p][HEVC].mkv</title>
          <link>https://example.com/2</link>
        </item>
        <item>
          <title>[SubGroup] Other Show - 01 [1080p].mkv</title>
          <link>https://example.com/3</link>
        </item>
      </channel>
    </rss>
    """
    respx.get("https://example.com/rss").mock(return_value=Response(200, text=rss_xml))

    tool = RSSTool()
    result = await tool.invoke(
        RSSToolInput(
            url="https://example.com/rss",
            parser_rules={"include": [r"Anime"], "exclude": [r"HEVC"]},
        )
    )

    assert result.success is True
    titles = {e["title"] for e in result.data["entries"]}
    assert titles == {"[SubGroup] Anime - 01 [1080p].mkv"}


@respx.mock
async def test_rss_tool_extracts_info_hash_from_magnet():
    """RSSTool should extract info_hash from magnet links."""
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:nyaa="https://nyaa.si/xmlns/nyaa">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>[SubGroup] Anime - 01 [1080p].mkv</title>
          <link>magnet:?xt=urn:btih:abc123def456&amp;dn=anime</link>
          <nyaa:infoHash>abc123def4567890abc123def4567890abcdef12</nyaa:infoHash>
        </item>
      </channel>
    </rss>
    """
    respx.get("https://example.com/rss").mock(return_value=Response(200, text=rss_xml))

    tool = RSSTool()
    result = await tool.invoke(RSSToolInput(url="https://example.com/rss"))

    assert result.success is True
    entry = result.data["entries"][0]
    assert entry["info_hash"] == "abc123def4567890abc123def4567890abcdef12"


@pytest.fixture
def animes_garden_feed() -> str:
    """Return the real Anime Garden RSS fixture as text."""
    fixture_path = Path(__file__).parent / "fixtures" / "animes_garden_feed.xml"
    return fixture_path.read_text(encoding="utf-8")


@respx.mock
async def test_rss_tool_parses_real_animes_garden_feed(animes_garden_feed: str):
    """RSSTool should parse the user's real Anime Garden feed fixture."""
    route = respx.get("https://api.animes.garden/feed.xml").mock(
        return_value=Response(200, text=animes_garden_feed)
    )

    tool = RSSTool()
    result = await tool.invoke(RSSToolInput(url="https://api.animes.garden/feed.xml"))

    assert result.success is True
    assert result.data["title"]
    assert len(result.data["entries"]) == 101
    entry = result.data["entries"][0]
    assert entry["title"]
    assert entry["link"].startswith("magnet:?xt=urn:btih:")
    assert entry["published"]
    assert route.called
