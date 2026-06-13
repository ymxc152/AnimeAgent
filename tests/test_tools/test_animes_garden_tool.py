"""Tests for AnimeGardenTool."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from anime_agent.tools.animes_garden_tool import (
    AnimeGardenTool,
    AnimeGardenToolInput,
    _convert_size_kb_to_bytes,
    _extract_info_hash,
)


class TestExtractInfoHash:
    """Test info_hash extraction from magnet links."""

    def test_extract_from_hex_magnet(self):
        """Should extract 40-char hex hash from magnet link."""
        # 40-char hex hash
        magnet = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=test"
        result = _extract_info_hash(magnet)
        assert result == "0123456789abcdef0123456789abcdef01234567"

    def test_extract_from_uppercase_hex_magnet(self):
        """Should extract and lowercase uppercase hex hash."""
        magnet = "magnet:?xt=urn:btih:0123456789ABCDEF0123456789ABCDEF01234567"
        result = _extract_info_hash(magnet)
        assert result == "0123456789abcdef0123456789abcdef01234567"

    def test_extract_from_base32_magnet(self):
        """Should extract and convert 32-char base32 hash."""
        # 32-char base32 hash (M5EQDHT6AVQORG45NHZIHBRYIZ7SR5W7)
        magnet = "magnet:?xt=urn:btih:M5EQDHT6AVQORG45NHZIHBRYIZ7SR5W7&dn=test"
        result = _extract_info_hash(magnet)
        # base32 -> hex conversion
        assert result is not None
        assert len(result) == 40  # hex hash is 40 chars

    def test_returns_none_for_invalid_magnet(self):
        """Should return None for invalid magnet link."""
        result = _extract_info_hash("not a magnet link")
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Should return None for empty string."""
        result = _extract_info_hash("")
        assert result is None


class TestConvertSizeKbToBytes:
    """Test size conversion from KB to bytes."""

    def test_convert_kb_to_bytes(self):
        """Should convert KB to bytes."""
        assert _convert_size_kb_to_bytes(1024) == 1048576

    def test_convert_zero(self):
        """Should handle zero."""
        assert _convert_size_kb_to_bytes(0) == 0

    def test_convert_small_value(self):
        """Should convert small value."""
        assert _convert_size_kb_to_bytes(1) == 1024


class TestAnimeGardenToolInput:
    """Test AnimeGardenToolInput validation."""

    def test_valid_input(self):
        """Should accept valid input."""
        input_data = AnimeGardenToolInput(search="Frieren")
        assert input_data.search == "Frieren"
        assert input_data.page == 1

    def test_custom_page(self):
        """Should accept custom page number."""
        input_data = AnimeGardenToolInput(search="Frieren", page=2)
        assert input_data.page == 2


class TestAnimeGardenTool:
    """Test AnimeGardenTool."""

    @pytest.fixture
    def tool(self):
        """Create AnimeGardenTool instance."""
        return AnimeGardenTool()

    @pytest.fixture
    def mock_response(self):
        """Create mock API response with 40-char hex hash."""
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

    async def test_invoke_success(self, tool, mock_response):
        """Should return candidates on successful API call."""
        with patch.object(tool.client, "get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )

            input_data = AnimeGardenToolInput(search="Frieren")
            result = await tool.invoke(input_data)

            assert result.success is True
            assert len(result.data["candidates"]) == 1
            assert result.data["candidates"][0]["info_hash"] == "0123456789abcdef0123456789abcdef01234567"

    async def test_invoke_extracts_info_hash(self, tool, mock_response):
        """Should extract info_hash from magnet link."""
        with patch.object(tool.client, "get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )

            input_data = AnimeGardenToolInput(search="Frieren")
            result = await tool.invoke(input_data)

            candidate = result.data["candidates"][0]
            assert candidate["info_hash"] == "0123456789abcdef0123456789abcdef01234567"
            assert candidate["source"] == "animes_garden"

    async def test_invoke_converts_size(self, tool, mock_response):
        """Should convert size from KB to bytes."""
        with patch.object(tool.client, "get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )

            input_data = AnimeGardenToolInput(search="Frieren")
            result = await tool.invoke(input_data)

            candidate = result.data["candidates"][0]
            assert candidate["size"] == 854835 * 1024  # KB to bytes

    async def test_invoke_parses_date(self, tool, mock_response):
        """Should parse ISO date string."""
        with patch.object(tool.client, "get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )

            input_data = AnimeGardenToolInput(search="Frieren")
            result = await tool.invoke(input_data)

            candidate = result.data["candidates"][0]
            assert candidate["published"] == "2026-06-05T15:15:00+00:00"

    async def test_invoke_http_error(self, tool):
        """Should return error on HTTP failure."""
        with patch.object(tool.client, "get") as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404),
            )

            input_data = AnimeGardenToolInput(search="Frieren")
            result = await tool.invoke(input_data)

            assert result.success is False
            assert "error" in result.error.lower()

    async def test_invoke_empty_results(self, tool):
        """Should return empty candidates when no results."""
        with patch.object(tool.client, "get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: {"status": "OK", "resources": []},
                raise_for_status=lambda: None,
            )

            input_data = AnimeGardenToolInput(search="NonexistentAnime")
            result = await tool.invoke(input_data)

            assert result.success is True
            assert len(result.data["candidates"]) == 0

    async def test_invoke_invalid_json(self, tool):
        """Should return error on invalid JSON response."""
        with patch.object(tool.client, "get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: (_ for _ in ()).throw(ValueError("Invalid JSON")),
                raise_for_status=lambda: None,
            )

            input_data = AnimeGardenToolInput(search="Frieren")
            result = await tool.invoke(input_data)

            assert result.success is False

    async def test_healthcheck_success(self, tool):
        """Should return success on health check."""
        with patch.object(tool.client, "get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                raise_for_status=lambda: None,
            )

            result = await tool.healthcheck()
            assert result.success is True

    async def test_healthcheck_failure(self, tool):
        """Should return failure on health check error."""
        with patch.object(tool.client, "get") as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            result = await tool.healthcheck()
            assert result.success is False
