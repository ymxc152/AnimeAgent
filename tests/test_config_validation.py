"""Tests for configuration validation."""

import os
from unittest.mock import patch

from anime_agent.config import Settings


class TestURLValidation:
    """Test URL field validation."""

    def test_valid_openai_base_url(self):
        """Should accept valid HTTP/HTTPS URLs for openai_base_url."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(openai_base_url="https://api.openai.com/v1", _env_file=None)
            assert settings.openai_base_url == "https://api.openai.com/v1"

    def test_valid_localhost_url(self):
        """Should accept localhost URLs."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(openai_base_url="http://localhost:11434/v1", _env_file=None)
            assert settings.openai_base_url == "http://localhost:11434/v1"

    def test_valid_qb_host(self):
        """Should accept valid qBittorrent host."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(qb_host="http://localhost:8080", _env_file=None)
            assert settings.qb_host == "http://localhost:8080"

    def test_valid_emby_host(self):
        """Should accept valid Emby host."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(emby_host="http://localhost:8096", _env_file=None)
            assert settings.emby_host == "http://localhost:8096"


class TestNumericValidation:
    """Test numeric field validation."""

    def test_valid_check_interval(self):
        """Should accept positive check_interval_seconds."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(check_interval_seconds=600, _env_file=None)
            assert settings.check_interval_seconds == 600

    def test_valid_min_duration(self):
        """Should accept positive filter_min_duration_minutes."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(filter_min_duration_minutes=5, _env_file=None)
            assert settings.filter_min_duration_minutes == 5

    def test_valid_log_level(self):
        """Should accept valid log levels."""
        with patch.dict(os.environ, {}, clear=True):
            for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                settings = Settings(log_level=level, _env_file=None)
                assert settings.log_level == level


class TestDefaultValues:
    """Test default configuration values."""

    def test_default_llm_provider(self):
        """Should have default llm_provider."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.llm_provider == "openai"

    def test_default_openai_model(self):
        """Should have default openai_model."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.openai_model == "gpt-4o-mini"

    def test_default_check_interval(self):
        """Should have default check_interval_seconds."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.check_interval_seconds == 60

    def test_default_log_level(self):
        """Should have default log_level."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.log_level == "INFO"

    def test_default_filter_exclude_genres(self):
        """Should have default filter_exclude_genres."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
            assert "Hentai" in settings.filter_exclude_genres
            assert "Ecchi" in settings.filter_exclude_genres

    def test_default_filter_exclude_formats(self):
        """Should have default filter_exclude_formats."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
            assert "OVA" in settings.filter_exclude_formats
            assert "ONA" in settings.filter_exclude_formats


class TestPropertyMethods:
    """Test property methods."""

    def test_filter_exclude_genres_parsing(self):
        """Should parse comma-separated genres."""
        with patch.dict(os.environ, {"FILTER_EXCLUDE_GENRES": "Action,Comedy,Romance"}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.filter_exclude_genres == ["Action", "Comedy", "Romance"]

    def test_filter_exclude_genres_strips_whitespace(self):
        """Should strip whitespace from genres."""
        with patch.dict(os.environ, {"FILTER_EXCLUDE_GENRES": "Action , Comedy , Romance"}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.filter_exclude_genres == ["Action", "Comedy", "Romance"]

    def test_filter_exclude_genres_empty_string(self):
        """Should handle empty string."""
        with patch.dict(os.environ, {"FILTER_EXCLUDE_GENRES": ""}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.filter_exclude_genres == []

    def test_filter_exclude_formats_parsing(self):
        """Should parse comma-separated formats."""
        with patch.dict(os.environ, {"FILTER_EXCLUDE_FORMATS": "OVA,ONA,Movie"}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.filter_exclude_formats == ["OVA", "ONA", "Movie"]

    def test_filter_exclude_formats_strips_whitespace(self):
        """Should strip whitespace from formats."""
        with patch.dict(os.environ, {"FILTER_EXCLUDE_FORMATS": "OVA , ONA , Movie"}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.filter_exclude_formats == ["OVA", "ONA", "Movie"]

    def test_filter_exclude_formats_empty_string(self):
        """Should handle empty string."""
        with patch.dict(os.environ, {"FILTER_EXCLUDE_FORMATS": ""}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.filter_exclude_formats == []
