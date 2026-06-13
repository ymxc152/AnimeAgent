"""Resolve base series title and numeric season from anime metadata.

This avoids hard-coding every possible season/sequel naming convention by
combining a fast rule-based pass with an LLM fallback for ambiguous titles.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from anime_agent.tools.base import BaseTool, ToolOutput
from anime_agent.tools.llm_tool import LLMTool, LLMToolInput
from anime_agent.utils.logger import logger


@dataclass(frozen=True)
class SeriesMetadata:
    """Clean series-level metadata for file organization."""

    series_title: str
    season_number: int


# Fast-path regexes for common season/sequel suffixes across languages.
_SEASON_TITLE_PATTERNS = [
    # Chinese: 第二季 / 第2季 / 2期 / 第2期 / 第II季 etc.
    r"\s*第\s*([一二三四五六七八九十IVX\d]+)\s*季\s*$",
    r"\s*第\s*([一二三四五六七八九十IVX\d]+)\s*期\s*$",
    # English / Romaji: Season 2, 2nd Season, Second Season, S2
    r"\s+season\s*(\d+)\s*$",
    r"\s+(\d+)(?:st|nd|rd|th)\s+season\s*$",
    r"\s+(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+season\s*$",
    r"\s+s(\d+)\s*$",
    # Japanese style: 2期, 第2シーズン
    r"\s+(\d+)\s*期\s*$",
    r"\s+第\s*(\d+)\s*シーズン\s*$",
]

_ROMAN_NUMERALS = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
_CHINESE_NUMERALS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_ORDINAL_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}


def _parse_number(raw: str) -> int | None:
    """Parse an Arabic numeral, Chinese numeral, or Roman numeral."""
    raw = raw.strip().upper()
    if raw.isdigit():
        return int(raw)
    if raw in _ROMAN_NUMERALS:
        return _ROMAN_NUMERALS[raw]
    # Chinese numerals can combine: 十二, 二十, etc.
    total = 0
    last = 0
    for ch in raw:
        value = _CHINESE_NUMERALS.get(ch)
        if value is None:
            return None
        if value >= 10 and last > 0:
            total += last * value
            last = 0
        else:
            total += value
            last = value
    return total or None


class SeriesMetadataResolver:
    """Extract series title and season number from anime metadata."""

    def __init__(self, llm_tool: BaseTool | None = None):
        self.llm_tool = llm_tool or LLMTool()

    async def resolve(self, anime: dict[str, Any]) -> SeriesMetadata:
        """Return series metadata, using rules first and LLM as fallback."""
        rule_result = self._rule_based(anime)
        if rule_result is not None:
            return rule_result

        return await self._llm_based(anime)

    def _rule_based(self, anime: dict[str, Any]) -> SeriesMetadata | None:
        """Try to strip season suffix and infer season number from titles."""
        title = (
            anime.get("title_chinese")
            or anime.get("title_romaji")
            or anime.get("title_native")
            or ""
        )
        if not title:
            return None

        series_title = title
        season_number = 1
        stripped = False

        for pattern in _SEASON_TITLE_PATTERNS:
            match = re.search(pattern, series_title, flags=re.IGNORECASE)
            if match:
                raw = match.group(1).strip()
                # Handle ordinal words like "second"
                lower = raw.lower()
                if lower in _ORDINAL_WORDS:
                    season_number = _ORDINAL_WORDS[lower]
                else:
                    parsed = _parse_number(raw)
                    season_number = parsed if parsed is not None else 1
                series_title = series_title[: match.start()].strip()
                stripped = True
                break

        # If nothing was stripped and the title contains a bare trailing number
        # like "Anime 2", be conservative and treat it as season 2 only when
        # the format makes it clearly a sequel.
        if not stripped:
            bare_match = re.search(r"\s+(\d+)\s*$", title)
            if bare_match and anime.get("season") and int(bare_match.group(1)) > 1:
                series_title = title[: bare_match.start()].strip()
                season_number = int(bare_match.group(1))
                stripped = True

        if not series_title:
            return None

        # If we couldn't find an explicit season marker but the title still has
        # a trailing number/roman numeral that could be a season, punt to the
        # LLM rather than guessing.
        if not stripped and re.search(r"\s+(\d+|[IVX]+)\s*$", title, flags=re.IGNORECASE):
            return None

        return SeriesMetadata(series_title=series_title, season_number=season_number)

    async def _llm_based(self, anime: dict[str, Any]) -> SeriesMetadata:
        """Ask an LLM to disambiguate the base series name and season number."""
        title = (
            anime.get("title_chinese")
            or anime.get("title_romaji")
            or anime.get("title_native")
            or "Unknown"
        )

        payload = {
            "title_chinese": anime.get("title_chinese"),
            "title_romaji": anime.get("title_romaji"),
            "title_native": anime.get("title_native"),
            "format": anime.get("format"),
            "season": anime.get("season"),
            "season_year": anime.get("season_year"),
            "total_episodes": anime.get("total_episodes"),
        }

        prompt = (
            "You are extracting structured metadata from an anime entry. "
            "Return a JSON object with exactly two keys:\n"
            "- series_title: the base series name, with season/sequel suffixes removed. "
            "Preserve the language of the most complete title (prefer Chinese if available).\n"
            "- season_number: the integer season number (1 if no explicit season).\n\n"
            f"Input: {json.dumps(payload, ensure_ascii=False)}\n\n"
            "Respond with JSON only."
        )

        try:
            result = await self.llm_tool.invoke(
                LLMToolInput(
                    prompt=prompt,
                    system_msg="Return valid JSON with keys series_title and season_number.",
                    json_schema={"series_title": "string", "season_number": "integer"},
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM series metadata resolution failed: {}", exc)
            result = ToolOutput(success=False, error=str(exc))

        if result.success and isinstance(result.data, dict):
            json_data = result.data.get("json", {})
            series_title = json_data.get("series_title", title).strip()
            try:
                season_number = max(1, int(json_data.get("season_number", 1)))
            except (ValueError, TypeError):
                season_number = 1
            if series_title:
                return SeriesMetadata(series_title=series_title, season_number=season_number)

        logger.warning(
            "Falling back to raw title for series metadata: {} (LLM result: {})",
            title,
            result.error if not result.success else "unexpected format",
        )
        return SeriesMetadata(series_title=title, season_number=1)
