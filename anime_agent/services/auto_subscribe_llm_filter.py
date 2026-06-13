"""LLM-assisted decision making for auto-subscribe rules."""

from typing import Any

from loguru import logger

from anime_agent.tools.llm_tool import LLMTool, LLMToolInput


class AutoSubscribeLLMFilter:
    """Ask an LLM whether a discovered anime should be auto-subscribed.

    This is an optional filter used by :class:`AutoSubscribeRule` when
    ``use_llm`` is enabled.  It returns one of ``subscribe``, ``skip``,
    or ``human_review``.
    """

    def __init__(self, llm_tool: LLMTool | None = None):
        self.llm_tool = llm_tool or LLMTool()

    async def decide(self, anime: dict[str, Any]) -> str:
        """Return 'subscribe', 'skip', or 'human_review'."""
        titles = [
            anime.get("title_chinese"),
            anime.get("title_native"),
            anime.get("title_romaji"),
            anime.get("title_english"),
        ]
        title = next((t for t in titles if t), "Unknown")

        prompt = (
            "You are helping decide whether to auto-subscribe to an anime for automated downloading.\n\n"
            f"Title: {title}\n"
            f"Format: {anime.get('format')}\n"
            f"Genres: {', '.join(anime.get('genres', []) or [])}\n"
            f"Tags: {', '.join(anime.get('tags', []) or [])}\n"
            f"Total episodes: {anime.get('total_episodes')}\n\n"
            "Respond with exactly one of: subscribe, skip, human_review.\n"
            "- subscribe: this looks like a normal TV/OVA series worth tracking\n"
            "- skip: it is a movie, duplicate, or otherwise not worth tracking\n"
            "- human_review: uncertain, needs human confirmation"
        )

        try:
            result = await self.llm_tool.invoke(
                LLMToolInput(prompt=prompt, system_msg=None, json_schema=None)
            )
            if not result.success:
                logger.warning("LLM auto-subscribe decision failed: {}", result.error)
                return "human_review"

            answer = str(result.data or "").strip().lower()
            if "subscribe" in answer:
                return "subscribe"
            if "skip" in answer:
                return "skip"
            return "human_review"
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM auto-subscribe decision error: {}", exc)
            return "human_review"


def _parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class AutoSubscribeRuleMatcher:
    """Match discovered anime against auto-subscribe rules."""

    def __init__(self, rules: list[Any]):
        self.rules = rules

    def matches(self, anime: dict[str, Any]) -> list[Any]:
        """Return the list of rules that match the given anime."""
        matched: list[Any] = []
        for rule in self.rules:
            if not rule.enabled:
                continue
            if self._rule_matches(rule, anime):
                matched.append(rule)
        return matched

    def _rule_matches(self, rule: Any, anime: dict[str, Any]) -> bool:
        genres = {g.strip().lower() for g in (anime.get("genres") or [])}
        formats = {f.strip().lower() for f in (anime.get("format") or [])}
        titles = " ".join(
            str(t).lower()
            for t in [
                anime.get("title_chinese"),
                anime.get("title_native"),
                anime.get("title_romaji"),
                anime.get("title_english"),
            ]
            if t
        )

        include_genres = {g.lower() for g in _parse_list(rule.include_genres)}
        exclude_genres = {g.lower() for g in _parse_list(rule.exclude_genres)}
        include_formats = {f.lower() for f in _parse_list(rule.include_formats)}
        exclude_formats = {f.lower() for f in _parse_list(rule.exclude_formats)}
        include_keywords = [k.lower() for k in _parse_list(rule.include_keywords)]
        exclude_keywords = [k.lower() for k in _parse_list(rule.exclude_keywords)]

        if include_genres and not include_genres.intersection(genres):
            return False
        if exclude_genres and exclude_genres.intersection(genres):
            return False
        if include_formats and not include_formats.intersection(formats):
            return False
        if exclude_formats and exclude_formats.intersection(formats):
            return False
        if include_keywords and not any(k in titles for k in include_keywords):
            return False
        if exclude_keywords and any(k in titles for k in exclude_keywords):
            return False
        if rule.min_score is not None:
            score = anime.get("score") or anime.get("average_score")
            if score is None or float(score) < rule.min_score:
                return False

        return True
