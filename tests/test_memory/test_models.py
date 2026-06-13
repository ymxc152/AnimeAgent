"""Tests for database models."""


from anime_agent.memory.models import Episode, Subscription


class TestEpisodeModel:
    """Test Episode model."""

    def test_episode_has_torrent_candidates_field(self):
        """Episode model should have torrent_candidates column."""
        assert hasattr(Episode, "torrent_candidates")
        # Check the column exists in the table
        column_names = [c.name for c in Episode.__table__.columns]
        assert "torrent_candidates" in column_names

    def test_episode_has_torrent_failed_hashes_field(self):
        """Episode model should have torrent_failed_hashes column."""
        column_names = [c.name for c in Episode.__table__.columns]
        assert "torrent_failed_hashes" in column_names

    def test_episode_has_status_column(self):
        """Episode model should have status column."""
        column_names = [c.name for c in Episode.__table__.columns]
        assert "status" in column_names

    def test_episode_has_low_confidence_count_column(self):
        """Episode model should have low_confidence_count column."""
        column_names = [c.name for c in Episode.__table__.columns]
        assert "low_confidence_count" in column_names

    def test_episode_column_defaults(self):
        """Episode columns should have correct defaults."""
        status_col = Episode.__table__.columns["status"]
        assert status_col.default.arg == "pending"

        lcc_col = Episode.__table__.columns["low_confidence_count"]
        assert lcc_col.default.arg == 0


class TestSubscriptionModel:
    """Test Subscription model."""

    def test_subscription_has_required_columns(self):
        """Subscription model should have required columns."""
        column_names = [c.name for c in Subscription.__table__.columns]
        assert "title_romaji" in column_names
        assert "title_native" in column_names
        assert "title_chinese" in column_names
        assert "total_episodes" in column_names
        assert "status" in column_names

    def test_subscription_column_defaults(self):
        """Subscription columns should have correct defaults."""
        status_col = Subscription.__table__.columns["status"]
        assert status_col.default.arg == "ongoing"

        auto_col = Subscription.__table__.columns["auto_download_enabled"]
        assert auto_col.default.arg is True
