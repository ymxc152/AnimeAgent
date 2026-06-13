"""Content filtering rules for discovered anime."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FilterRules:
    """User-configurable content filter rules."""

    exclude_ova: bool = True
    exclude_movies: bool = False
    min_duration_minutes: int = 5
    exclude_genres: list[str] = field(default_factory=list)
    exclude_formats: list[str] = field(default_factory=list)
    require_anime_type: bool = True

    def __post_init__(self) -> None:
        self.exclude_genres = [g.lower() for g in self.exclude_genres]
        self.exclude_formats = [f.upper() for f in self.exclude_formats]


@dataclass
class FilterResult:
    """Result of applying a filter to an anime."""

    allowed: bool
    reason: str = ""


class ContentFilter:
    """Apply filter rules to anime candidates."""

    def __init__(self, rules: FilterRules):
        self.rules = rules

    def apply(self, anime: dict[str, Any]) -> FilterResult:
        """Return True if the anime passes all filter rules."""
        format_value = str(anime.get("format", "")).upper()
        duration = anime.get("duration") or 0
        anime_type = str(anime.get("type", "")).upper()

        # Format filtering
        if self.rules.exclude_ova and format_value == "OVA":
            return FilterResult(False, "Excluded format: OVA")

        if self.rules.exclude_formats and format_value in self.rules.exclude_formats:
            return FilterResult(False, f"Excluded format: {format_value}")

        # Movie filtering
        if self.rules.exclude_movies and format_value == "MOVIE":
            return FilterResult(False, "Excluded format: Movie")

        # Duration filtering
        if duration and duration < self.rules.min_duration_minutes:
            return FilterResult(
                False,
                f"Duration {duration}min below minimum {self.rules.min_duration_minutes}min",
            )

        # Genre filtering
        for raw_genre in anime.get("genres", []):
            genre = str(raw_genre).lower()
            if genre in self.rules.exclude_genres:
                return FilterResult(False, f"Excluded genre: {raw_genre}")

        # Type filtering (supports both AniList "ANIME" and Bangumi type=2)
        if self.rules.require_anime_type:
            is_anime = anime_type == "ANIME" or anime_type == "2"
            if not is_anime:
                return FilterResult(False, f"Not an anime type: {anime_type}")

        return FilterResult(True)
