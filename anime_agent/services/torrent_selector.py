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
        prefiltered = self._prefilter(candidates, episode_number, failed_hashes, title_variants)

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
        title_variants: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Keep only candidates that match the target episode number and title."""
        title_tokens = self._extract_title_tokens(title_variants or [])
        result = []
        for candidate in candidates:
            info_hash = candidate.get("info_hash")
            if info_hash and info_hash in failed_hashes:
                continue

            title = candidate.get("title", "")
            if not self._episode_matches(title, episode_number):
                continue

            if title_tokens and not self._title_matches(title, title_tokens):
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
            # Explicit prefix: EP12, ep12; also allow version suffixes: EP01v2
            rf"(?:EP|ep)0?{ep}(?:[\]\)\s.\-|v]|$)",
            # Standalone or bracketed: [12], (12), space+12, - 12; allow 01v2
            # Negative lookbehind: not preceded by a digit (rejects "01-12" range)
            # Negative lookahead: episode not followed by range markers like -digit or ~digit
            rf"(?<!\d)[\[\(\s]-?\s*0?{ep}(?![~-]\d)(?:[\]\)\s.\-|v]|$)",
            # CJK markers
            rf"第0?{ep}[集话話]",
        ]
        return any(re.search(pattern, title) for pattern in patterns)

    def _extract_title_tokens(self, title_variants: list[str]) -> set[str]:
        """Extract significant searchable tokens from title variants.

        Skips all-CJK variants (RSS titles rarely contain Chinese/Japanese names)
        and very short or generic tokens to avoid over-filtering.
        """
        tokens: set[str] = set()
        generic = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "her", "was", "one", "our", "out", "day", "get", "has", "him", "his", "how", "its", "may", "new", "now", "old", "see", "two", "who", "boy", "did", "she", "use", "her", "way", "many", "oil", "sit", "set", "run", "eat", "far", "sea", "eye", "ago", "off", "too", "any", "say", "man", "try", "ask", "end", "why", "let", "put", "say", "she", "try", "way", "own", "say", "too", "old", "tell", "very", "when", "much", "would", "there", "their", "what", "said", "have", "each", "which", "will", "about", "could", "other", "after", "first", "never", "these", "think", "where", "being", "every", "great", "might", "shall", "still", "those", "while", "this", "that", "with", "from", "they", "know", "want", "been", "good", "much", "some", "time", "very", "when", "come", "here", "just", "like", "long", "make", "many", "over", "such", "take", "than", "them", "well", "were"}
        for variant in title_variants:
            if not variant:
                continue
            # Skip all-CJK variants; RSS titles usually use romaji for non-CJK shows.
            if all("\u4e00" <= c <= "\u9fff" or "\u3040" <= c <= "\u309f" or "\u30a0" <= c <= "\u30ff" for c in variant if c.isalpha()):
                continue
            normalized = re.sub(r"[^a-zA-Z0-9]+", " ", variant).lower()
            for token in normalized.split():
                if len(token) >= 3 and token not in generic:
                    tokens.add(token)
        return tokens

    def _title_matches(self, title: str, tokens: set[str]) -> bool:
        """Return True if the candidate title contains at least one title token."""
        normalized = re.sub(r"[^a-zA-Z0-9]+", " ", title).lower()
        title_words = set(normalized.split())
        return bool(title_words & tokens)

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
