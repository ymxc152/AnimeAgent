"""Tests for ContentFilter."""

from anime_agent.services.content_filter import ContentFilter, FilterRules


def test_filter_excludes_ova():
    """ContentFilter should exclude OVA when configured."""
    rules = FilterRules(exclude_formats=["OVA"])
    anime = {"format": "OVA", "duration": 24, "genres": ["Fantasy"], "type": "ANIME"}

    result = ContentFilter(rules).apply(anime)

    assert result.allowed is False
    assert "OVA" in result.reason


def test_filter_excludes_short_episodes():
    """ContentFilter should exclude anime shorter than min_duration."""
    rules = FilterRules(min_duration_minutes=5)
    anime = {"format": "TV", "duration": 3, "genres": ["Fantasy"], "type": "ANIME"}

    result = ContentFilter(rules).apply(anime)

    assert result.allowed is False
    assert "duration" in result.reason.lower()


def test_filter_excludes_adult_genres():
    """ContentFilter should exclude anime with adult genres."""
    rules = FilterRules(exclude_genres=["Hentai"])
    anime = {"format": "TV", "duration": 24, "genres": ["Hentai"], "type": "ANIME"}

    result = ContentFilter(rules).apply(anime)

    assert result.allowed is False
    assert "Hentai" in result.reason


def test_filter_allows_valid_tv_anime():
    """ContentFilter should allow a standard TV anime."""
    rules = FilterRules(
        exclude_formats=["OVA", "ONA"],
        exclude_genres=["Hentai"],
        min_duration_minutes=5,
        require_anime_type=True,
    )
    anime = {"format": "TV", "duration": 24, "genres": ["Fantasy"], "type": "ANIME"}

    result = ContentFilter(rules).apply(anime)

    assert result.allowed is True
    assert result.reason == ""


def test_filter_can_allow_movies():
    """ContentFilter should allow movies when exclude_movies is false."""
    rules = FilterRules(exclude_movies=False)
    anime = {"format": "Movie", "duration": 90, "genres": ["Fantasy"], "type": "ANIME"}

    result = ContentFilter(rules).apply(anime)

    assert result.allowed is True
