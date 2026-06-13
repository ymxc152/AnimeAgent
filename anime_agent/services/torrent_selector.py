"""Torrent selection — LLM-driven with episode-number pre-filtering."""

import re
from typing import Any

from anime_agent.tools.base import BaseTool, ToolOutput
from anime_agent.tools.llm_tool import LLMToolInput

# Maximum candidates sent to the LLM to keep prompts manageable.
_MAX_CANDIDATES = 20


class TorrentSelector:
    """Select the best torrent candidate for an episode.

    Strategy: pre-filter only by episode number (no title keyword matching),
    then let the LLM choose the best candidate using romaji title, quality,
    and release-group heuristics.
    """

    def __init__(self, llm_tool: BaseTool | None = None):
        self.llm_tool = llm_tool

    async def select(
        self,
        candidates: list[dict[str, Any]],
        episode_number: int,
        title_variants: list[str],
        failed_hashes: list[str],
    ) -> ToolOutput:
        """Pre-filter by episode number, then LLM selection."""
        prefiltered = self._prefilter(candidates, episode_number, failed_hashes)

        if not prefiltered:
            return ToolOutput(
                success=True,
                data={
                    "matched": False,
                    "reason": "No candidates after episode-number filter",
                    "prefiltered": [],
                },
            )

        if self.llm_tool is None:
            return self._heuristic_select(prefiltered)

        schema = {
            "title": "TorrentMatchResult",
            "description": "Best torrent match for the target episode",
            "type": "object",
            "properties": {
                "info_hash": {"type": "string"},
                "confidence": {"type": "number"},
                "reason": {"type": "string"},
            },
            "required": ["info_hash", "confidence"],
        }

        prompt = self._build_prompt(prefiltered, episode_number, title_variants)
        llm_result = await self.llm_tool.invoke(
            LLMToolInput(prompt=prompt, json_schema=schema, system_msg=self._system_msg())
        )

        if not llm_result.success:
            return self._heuristic_select(prefiltered)

        json_data = llm_result.data.get("json", {})
        info_hash = json_data.get("info_hash")
        confidence = json_data.get("confidence", 0.0)

        matched = next((c for c in prefiltered if c.get("info_hash") == info_hash), None)
        if matched is None:
            return ToolOutput(
                success=True,
                data={
                    "matched": False,
                    "reason": "LLM chose an unknown candidate",
                },
            )

        return ToolOutput(
            success=True,
            data={
                "matched": True,
                "info_hash": info_hash,
                "title": matched.get("title"),
                "link": matched.get("link"),
                "confidence": confidence,
                "reason": json_data.get("reason", ""),
                "prefiltered": prefiltered,
            },
        )

    # ------------------------------------------------------------------
    # Pre-filter: episode number only
    # ------------------------------------------------------------------

    def _prefilter(
        self,
        candidates: list[dict[str, Any]],
        episode_number: int,
        failed_hashes: list[str],
    ) -> list[dict[str, Any]]:
        """Keep only candidates that match the target episode number."""
        result = []
        for candidate in candidates:
            info_hash = candidate.get("info_hash")
            if info_hash and info_hash in failed_hashes:
                continue

            title = candidate.get("title", "")
            if not self._episode_matches(title, episode_number):
                continue

            result.append(candidate)

        # Sort by size descending and cap to avoid overwhelming the LLM.
        result.sort(key=lambda c: c.get("size", 0), reverse=True)
        return result[:_MAX_CANDIDATES]

    def _episode_matches(self, title: str, episode_number: int) -> bool:
        """Check if the title indicates the target episode number.

        Matches: - 12, EP12, [12], 第12集, etc.
        Rejects: 01-12 (range), 01~12 (range).
        """
        ep = episode_number
        patterns = [
            # Explicit prefix: EP12, ep12
            rf"(?:EP|ep)0?{ep}(?:[\]\)\s.\-|]|$)",
            # Standalone or bracketed: [12], (12), space+12, - 12
            # Negative lookbehind: not preceded by a digit (rejects "01-12" range)
            # Negative lookahead: episode not followed by range markers like -digit or ~digit
            rf"(?<!\d)[\[\(\s]-?\s*0?{ep}(?![~-]\d)(?:[\]\)\s.\-|]|$)",
            # CJK markers
            rf"第0?{ep}[集话話]",
        ]
        return any(re.search(pattern, title) for pattern in patterns)

    # ------------------------------------------------------------------
    # Heuristic fallback (no LLM)
    # ------------------------------------------------------------------

    def _heuristic_select(self, candidates: list[dict[str, Any]]) -> ToolOutput:
        """Fallback: pick the largest file."""
        if not candidates:
            return ToolOutput(success=True, data={"matched": False, "reason": "No candidates"})

        best = max(candidates, key=lambda c: c.get("size", 0))
        return ToolOutput(
            success=True,
            data={
                "matched": True,
                "info_hash": best.get("info_hash"),
                "title": best.get("title"),
                "link": best.get("link"),
                "confidence": 0.5,
                "reason": "Heuristic fallback: largest file",
                "prefiltered": candidates,
            },
        )

    # ------------------------------------------------------------------
    # LLM prompt
    # ------------------------------------------------------------------

    def _system_msg(self) -> str:
        return (
            "You are an anime torrent matching assistant. Your job is to pick the "
            "BEST torrent for a given episode from a list of RSS candidates.\n\n"
            "Matching rules (in priority order):\n"
            "1. The torrent title MUST indicate the correct episode number.\n"
            "2. Match by the ROMAJI title (English/romanized). Ignore CJK title differences.\n"
            "3. Prefer higher quality: 1080p > 720p > 480p. HEVC/H.265 is a plus.\n"
            "4. Prefer releases with subtitles (SUB/CHS/CHT/ML in the title).\n"
            "5. Prefer well-known release groups (LoliHouse, ANi, SubsPlease, etc.).\n"
            "6. Avoid batch/complete packs (look for single episode markers).\n\n"
            "Return ONLY a JSON object with info_hash, confidence (0.0-1.0), and reason.\n"
            "If you are reasonably confident (>= 0.5), pick a candidate.\n"
            "If absolutely none match, set info_hash to empty string and confidence to 0.0."
        )

    def _build_prompt(
        self,
        candidates: list[dict[str, Any]],
        episode_number: int,
        title_variants: list[str],
    ) -> str:
        # Pick the best title variant to display: prefer romaji, then chinese, then native.
        display_title = ""
        for variant in title_variants:
            if variant and all(ord(c) < 0x4E00 or ord(c) > 0x9FFF for c in variant):
                display_title = variant
                break
        if not display_title and title_variants:
            display_title = title_variants[0]

        lines = [
            f"Target anime: {display_title}",
            f"Episode: {episode_number}",
            f"All known titles: {' / '.join(title_variants)}",
            "",
            "Candidates (sorted by size, largest first):",
        ]
        for idx, candidate in enumerate(candidates, 1):
            size_mb = candidate.get("size", 0) / (1024 * 1024) if candidate.get("size") else 0
            lines.append(
                f"{idx}. [{size_mb:.0f}MB] {candidate.get('title')} "
                f"|| hash={candidate.get('info_hash')}"
            )
        lines.extend(
            [
                "",
                "Pick the best candidate. Return JSON: {info_hash, confidence, reason}.",
            ]
        )
        return "\n".join(lines)
