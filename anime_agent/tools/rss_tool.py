"""RSS feed tool for fetching and parsing anime torrent feeds."""

import asyncio
import re
import time
from datetime import UTC, datetime
from typing import Any, cast

import feedparser
import httpx

from anime_agent.tools.base import BaseTool, ToolInput, ToolOutput

# Module-level RSS response cache: url -> (timestamp, parsed_entries, feed_title)
_RSS_CACHE: dict[str, tuple[float, list[dict[str, Any]], str]] = {}
_RSS_CACHE_TTL = 300  # 5 minutes


def clear_rss_cache() -> None:
    """Clear the RSS response cache. Useful for testing."""
    _RSS_CACHE.clear()


class RSSToolInput(ToolInput):
    """Input for RSSTool."""

    url: str
    parser_rules: dict[str, Any] = {}


class RSSTool(BaseTool):
    """Fetch and parse RSS/Atom feeds."""

    name = "rss"
    description = "Fetch and parse RSS/Atom feeds for anime torrent candidates."

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(timeout=30.0)

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Fetch the feed and return normalized entries, with caching and 429 retry."""
        rss_input = cast(RSSToolInput, input_data)

        # Check cache first
        cached = _RSS_CACHE.get(rss_input.url)
        if cached is not None:
            ts, entries, title = cached
            if time.monotonic() - ts < _RSS_CACHE_TTL:
                filtered = _apply_parser_rules(entries, rss_input.parser_rules)
                return ToolOutput(
                    success=True, data={"entries": filtered, "title": title}
                )

        # Fetch with retry for 429
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.get(rss_input.url)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 10 * (attempt + 1)))
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_after)
                        continue
                    return ToolOutput(
                        success=False,
                        error=f"RSS feed rate limited (429) after {max_retries} retries",
                    )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                if attempt < max_retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                return ToolOutput(success=False, error=f"Failed to fetch RSS feed: {exc}")

            feed = feedparser.parse(response.text)
            entries = [_normalize_entry(entry) for entry in feed.entries]
            title = feed.feed.get("title", "")

            # Update cache
            _RSS_CACHE[rss_input.url] = (time.monotonic(), entries, title)

            filtered = _apply_parser_rules(entries, rss_input.parser_rules)
            return ToolOutput(
                success=True, data={"entries": filtered, "title": title}
            )

        return ToolOutput(success=False, error="RSS fetch failed after retries")


def _apply_parser_rules(
    entries: list[dict[str, Any]], parser_rules: dict[str, Any]
) -> list[dict[str, Any]]:
    """Filter entries by include/exclude regex rules applied to the title."""
    include_patterns = [re.compile(p) for p in parser_rules.get("include", []) if p]
    exclude_patterns = [re.compile(p) for p in parser_rules.get("exclude", []) if p]

    result = []
    for entry in entries:
        title = entry.get("title", "")
        if include_patterns and not any(p.search(title) for p in include_patterns):
            continue
        if exclude_patterns and any(p.search(title) for p in exclude_patterns):
            continue
        result.append(entry)
    return result


def _normalize_entry(entry: feedparser.FeedParserDict) -> dict[str, Any]:
    """Convert a feedparser entry into a normalized candidate dict."""
    published = None
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        pp = entry.published_parsed
        published = datetime(pp[0], pp[1], pp[2], pp[3], pp[4], pp[5], tzinfo=UTC).isoformat()
    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
        up = entry.updated_parsed
        published = datetime(up[0], up[1], up[2], up[3], up[4], up[5], tzinfo=UTC).isoformat()

    enclosure_url = ""
    size = 0
    if hasattr(entry, "enclosures") and entry.enclosures:
        enclosure = entry.enclosures[0]
        enclosure_url = enclosure.get("href", "") or enclosure.get("url", "")
        try:
            size = int(enclosure.get("length", 0))
        except (ValueError, TypeError):
            size = 0

    # Prefer the direct download/magnet enclosure over the detail page link.
    link = enclosure_url or entry.get("link", "")
    info_hash = _extract_info_hash(entry, link)

    return {
        "title": entry.get("title", ""),
        "link": link,
        "published": published,
        "size": size,
        "info_hash": info_hash,
        "source": "rss",
    }


def _extract_info_hash(entry: feedparser.FeedParserDict, link: str) -> str | None:
    """Extract info_hash from nyaa extension, enclosure magnet, or direct link."""
    # Nyaa-style namespace
    for key in ("nyaa_infohash", "infohash", "info_hash"):
        value = entry.get(key)
        if value:
            return str(value).lower()

    # Enclosure magnet link: magnet:?xt=urn:btih:<hash>&...
    enclosures = entry.get("enclosures", [])
    if enclosures:
        enclosure_link = enclosures[0].get("href", "")
        magnet_match = re.search(r"urn:btih:([a-zA-Z0-9]+)", enclosure_link)
        if magnet_match:
            return _normalize_hash(magnet_match.group(1))

    # Direct link magnet
    magnet_match = re.search(r"urn:btih:([a-zA-Z0-9]+)", link)
    if magnet_match:
        return _normalize_hash(magnet_match.group(1))

    return None


def _normalize_hash(raw_hash: str) -> str | None:
    """Normalize a 40-char hex or 32-char base32 info_hash to lowercase hex."""
    raw = raw_hash.strip().upper()
    if len(raw) == 40:
        return raw.lower()
    if len(raw) == 32:
        try:
            import base64

            decoded = base64.b32decode(raw)
            return decoded.hex()
        except ValueError:
            return raw.lower()
    return raw.lower()
