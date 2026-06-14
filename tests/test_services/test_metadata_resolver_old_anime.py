"""Tests for MetadataResolver old/finished anime detection."""

from datetime import UTC, datetime, timedelta

from anime_agent.services.metadata_resolver import MetadataResolver


class TestShouldFallbackToResourceSearch:
    """Test should_fallback_to_resource_search heuristic."""

    def test_finished_status_triggers_fallback(self):
        """AniList FINISHED status should enable resource fallback."""
        resolver = MetadataResolver()
        assert resolver.should_fallback_to_resource_search({"status": "FINISHED"}) is True

    def test_releasing_status_does_not_trigger_fallback(self):
        """RELEASING status should not enable resource fallback."""
        resolver = MetadataResolver()
        assert resolver.should_fallback_to_resource_search({"status": "RELEASING"}) is False

    def test_old_air_date_triggers_fallback(self):
        """Air date older than threshold should enable resource fallback."""
        resolver = MetadataResolver()
        old_date = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        assert resolver.should_fallback_to_resource_search({"air_date": old_date}) is True

    def test_recent_air_date_does_not_trigger_fallback(self):
        """Recent air date should not enable resource fallback."""
        resolver = MetadataResolver()
        recent_date = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        assert resolver.should_fallback_to_resource_search({"air_date": recent_date}) is False

    def test_custom_threshold(self):
        """Threshold should be configurable."""
        resolver = MetadataResolver()
        date_50_days_ago = (datetime.now(UTC) - timedelta(days=50)).isoformat()
        assert resolver.should_fallback_to_resource_search(
            {"air_date": date_50_days_ago}, old_anime_days=30
        ) is True
        assert resolver.should_fallback_to_resource_search(
            {"air_date": date_50_days_ago}, old_anime_days=90
        ) is False

    def test_start_date_fallback_field(self):
        """start_date should be used if air_date is missing."""
        resolver = MetadataResolver()
        old_date = (datetime.now(UTC) - timedelta(days=120)).date().isoformat()
        assert resolver.should_fallback_to_resource_search({"start_date": old_date}) is True

    def test_invalid_air_date_is_ignored(self):
        """Invalid air_date should not crash and result in no fallback."""
        resolver = MetadataResolver()
        assert resolver.should_fallback_to_resource_search({"air_date": "not-a-date"}) is False
