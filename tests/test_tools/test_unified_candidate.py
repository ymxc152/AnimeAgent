"""Tests for unified candidate format between RSSTool and AnimeGardenTool."""

from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

import pytest

from anime_agent.tools.rss_tool import RSSTool, RSSToolInput, _normalize_entry
from anime_agent.tools.animes_garden_tool import AnimeGardenTool, AnimeGardenToolInput


class TestRSSToolCandidateFormat:
    """Test RSSTool outputs unified candidate format."""

    def test_normalize_entry_has_source_field(self):
        """Should add source='rss' to normalized entry."""
        entry = SimpleNamespace(
            title="[Sub] Frieren - 01 [1080p].mkv",
            link="magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567",
            published_parsed=None,
            updated_parsed=None,
            enclosures=[],
        )
        entry.get = lambda key, default=None: getattr(entry, key, default)

        result = _normalize_entry(entry)

        assert "source" in result
        assert result["source"] == "rss"

    def test_normalize_entry_has_required_fields(self):
        """Should have all required fields for unified format."""
        entry = SimpleNamespace(
            title="[Sub] Frieren - 01 [1080p].mkv",
            link="magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567",
            published_parsed=None,
            updated_parsed=None,
            enclosures=[],
        )
        entry.get = lambda key, default=None: getattr(entry, key, default)

        result = _normalize_entry(entry)

        # Required fields for unified format
        assert "title" in result
        assert "link" in result
        assert "info_hash" in result
        assert "source" in result
        assert "size" in result
        assert "published" in result

    def test_normalize_entry_extracts_info_hash(self):
        """Should extract info_hash from magnet link."""
        entry = SimpleNamespace(
            title="[Sub] Frieren - 01 [1080p].mkv",
            link="magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567",
            published_parsed=None,
            updated_parsed=None,
            enclosures=[],
        )
        entry.get = lambda key, default=None: getattr(entry, key, default)

        result = _normalize_entry(entry)

        assert result["info_hash"] == "0123456789abcdef0123456789abcdef01234567"


class TestAnimeGardenToolCandidateFormat:
    """Test AnimeGardenTool outputs unified candidate format."""

    @pytest.fixture
    def tool(self):
        """Create AnimeGardenTool instance."""
        return AnimeGardenTool()

    @pytest.fixture
    def mock_response(self):
        """Create mock API response."""
        return {
            "status": "OK",
            "resources": [
                {
                    "id": 2436978,
                    "title": "[jibaketa] Sousou no Frieren - 10 END [1080p].mkv",
                    "magnet": "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567",
                    "href": "https://animes.garden/detail/2436978",
                    "size": 854835,
                    "fansub": {"name": "jibaketa"},
                    "publisher": {"name": "test"},
                    "subjectId": 12345,
                    "createdAt": "2026-06-05T15:15:00.000Z",
                },
            ],
        }

    async def test_invoke_has_source_field(self, tool, mock_response):
        """Should have source='animes_garden' in candidates."""
        with patch.object(tool.client, "get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )

            input_data = AnimeGardenToolInput(search="Frieren")
            result = await tool.invoke(input_data)

            candidate = result.data["candidates"][0]
            assert candidate["source"] == "animes_garden"

    async def test_invoke_has_required_fields(self, tool, mock_response):
        """Should have all required fields for unified format."""
        with patch.object(tool.client, "get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )

            input_data = AnimeGardenToolInput(search="Frieren")
            result = await tool.invoke(input_data)

            candidate = result.data["candidates"][0]

            # Required fields for unified format
            assert "title" in candidate
            assert "link" in candidate
            assert "info_hash" in candidate
            assert "source" in candidate
            assert "size" in candidate
            assert "published" in candidate
            assert "fansub" in candidate
            assert "publisher" in candidate
            assert "detail_url" in candidate
            assert "subject_id" in candidate


class TestUnifiedFormatCompatibility:
    """Test that both tools produce compatible formats."""

    def test_both_formats_have_common_fields(self):
        """Both formats should have these common fields."""
        common_fields = ["title", "link", "info_hash", "source", "size", "published"]

        # RSS format
        entry = SimpleNamespace(
            title="test",
            link="magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567",
            published_parsed=None,
            updated_parsed=None,
            enclosures=[],
        )
        entry.get = lambda key, default=None: getattr(entry, key, default)

        rss_result = _normalize_entry(entry)

        for field in common_fields:
            assert field in rss_result, f"RSS format missing field: {field}"
