"""AnimeGarden resource search tool for anime torrent fallback."""

import re
from datetime import datetime

import httpx

from anime_agent.tools.base import BaseTool, ToolInput, ToolOutput


class AnimeGardenToolInput(ToolInput):
    """Input for AnimeGardenTool."""

    search: str
    page: int = 1


def _extract_info_hash(magnet: str) -> str | None:
    """Extract info_hash from magnet link and normalize to lowercase."""
    if not magnet:
        return None
    # Match 40-char hex hash or 32-char base32 hash
    match = re.search(r"urn:btih:([a-fA-F0-9]{40}|[a-zA-Z0-9]{32})", magnet)
    if match:
        hash_str = match.group(1)
        # If 32 chars (base32), convert to hex
        if len(hash_str) == 32:
            try:
                import base64
                decoded = base64.b32decode(hash_str.upper())
                return decoded.hex()
            except Exception:
                return hash_str.lower()
        return hash_str.lower()
    return None


def _convert_size_kb_to_bytes(size_kb: int) -> int:
    """Convert size from kilobytes to bytes."""
    return size_kb * 1024


def _parse_iso_date(date_str: str) -> str | None:
    """Parse ISO 8601 date string and return ISO format with timezone."""
    if not date_str:
        return None
    try:
        # Parse ISO 8601 format
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.isoformat()
    except (ValueError, AttributeError):
        return None


class AnimeGardenTool(BaseTool):
    """Search anime torrent resources via Anime Garden API as RSS fallback."""

    name = "animes_garden"
    description = "Search anime torrent resources via Anime Garden API as RSS fallback."

    BASE_URL = "https://api.animes.garden"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(timeout=30.0)

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Search for anime resources via Anime Garden API."""
        if not isinstance(input_data, AnimeGardenToolInput):
            return ToolOutput(
                success=False,
                error="Input must be AnimeGardenToolInput",
            )

        try:
            url = f"{self.BASE_URL}/resources"
            params: dict[str, str | int] = {
                "search": input_data.search,
                "page": input_data.page,
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            resources = data.get("resources", [])

            candidates = []
            for resource in resources:
                magnet = resource.get("magnet", "")
                info_hash = _extract_info_hash(magnet)

                if not info_hash:
                    continue

                size_kb = resource.get("size", 0)
                size_bytes = _convert_size_kb_to_bytes(size_kb)

                published = _parse_iso_date(resource.get("createdAt", ""))

                fansub = resource.get("fansub", {})
                publisher = resource.get("publisher", {})

                candidate = {
                    "info_hash": info_hash,
                    "title": resource.get("title", ""),
                    "link": magnet,
                    "source": "animes_garden",
                    "size": size_bytes,
                    "published": published,
                    "fansub": fansub.get("name", ""),
                    "publisher": publisher.get("name", ""),
                    "detail_url": resource.get("href", ""),
                    "subject_id": resource.get("subjectId"),
                }
                candidates.append(candidate)

            return ToolOutput(
                success=True,
                data={"candidates": candidates, "total": len(candidates)},
            )

        except httpx.HTTPStatusError as exc:
            return ToolOutput(
                success=False,
                error=f"HTTP error {exc.response.status_code}: {exc}",
            )
        except httpx.ConnectError as exc:
            return ToolOutput(
                success=False,
                error=f"Connection error: {exc}",
            )
        except Exception as exc:
            return ToolOutput(
                success=False,
                error=f"AnimeGarden search failed: {exc}",
            )

    async def healthcheck(self) -> ToolOutput:
        """Check if AnimeGarden API is accessible."""
        try:
            response = await self.client.get(f"{self.BASE_URL}/resources", params={"search": "test", "page": 1})
            response.raise_for_status()
            return ToolOutput(success=True)
        except Exception as exc:
            return ToolOutput(success=False, error=str(exc))
