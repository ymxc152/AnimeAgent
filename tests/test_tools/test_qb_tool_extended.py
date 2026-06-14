"""Extended tests for QBTool — list, error handling, hash extraction, edge cases."""

from unittest.mock import MagicMock

from anime_agent.tools.qb_tool import (
    QBTool,
    QBToolInput,
    _extract_hash_from_url,
    _get_value,
    _unix_to_utc,
)

# ── _list action ────────────────────────────────────────────────────────


class TestQBToolList:
    async def test_list_returns_tagged_torrents(self):
        mock_client = MagicMock()
        mock_client.torrents_info.return_value = [
            {
                "hash": "ABC123",
                "name": "Anime - 01.mkv",
                "progress": 1.0,
                "state": "completed",
                "dlspeed": 0,
                "size": 536870912,
                "added_on": 1700000000,
                "last_activity": 1700001000,
            }
        ]

        tool = QBTool(client=mock_client)
        result = await tool.invoke(QBToolInput(action="list"))

        assert result.success is True
        assert len(result.data["torrents"]) == 1
        assert result.data["torrents"][0]["name"] == "Anime - 01.mkv"
        mock_client.torrents_info.assert_called_once_with(tag="anime-agent")

    async def test_list_returns_empty_when_no_torrents(self):
        mock_client = MagicMock()
        mock_client.torrents_info.return_value = []

        tool = QBTool(client=mock_client)
        result = await tool.invoke(QBToolInput(action="list"))

        assert result.success is True
        assert result.data["torrents"] == []

    async def test_list_handles_exception(self):
        mock_client = MagicMock()
        mock_client.torrents_info.side_effect = Exception("Connection lost")

        tool = QBTool(client=mock_client)
        result = await tool.invoke(QBToolInput(action="list"))

        assert result.success is False
        assert "Connection lost" in result.error


# ── Unknown action ──────────────────────────────────────────────────────


class TestQBToolUnknownAction:
    async def test_returns_error_for_unknown_action(self):
        tool = QBTool(client=MagicMock())
        result = await tool.invoke(QBToolInput(action="nonexistent"))

        assert result.success is False
        assert "Unknown action" in result.error


# ── Error handling ──────────────────────────────────────────────────────


class TestQBToolErrorHandling:
    async def test_add_handles_exception(self):
        mock_client = MagicMock()
        mock_client.torrents_add.side_effect = Exception("Auth failed")

        tool = QBTool(client=mock_client)
        result = await tool.invoke(
            QBToolInput(action="add", torrent_url="magnet:?xt=urn:btih:abc123")
        )

        assert result.success is False
        assert "Auth failed" in result.error

    async def test_get_status_handles_exception(self):
        mock_client = MagicMock()
        mock_client.torrents_info.side_effect = Exception("Timeout")

        tool = QBTool(client=mock_client)
        result = await tool.invoke(
            QBToolInput(action="get_status", torrent_hash="abc123")
        )

        assert result.success is False
        assert "Timeout" in result.error

    async def test_get_status_requires_hash(self):
        tool = QBTool(client=MagicMock())
        result = await tool.invoke(QBToolInput(action="get_status"))

        assert result.success is False
        assert "torrent_hash" in result.error

    async def test_delete_requires_hash(self):
        tool = QBTool(client=MagicMock())
        result = await tool.invoke(QBToolInput(action="delete"))

        assert result.success is False
        assert "torrent_hash" in result.error

    async def test_delete_handles_exception(self):
        mock_client = MagicMock()
        mock_client.torrents_delete.side_effect = Exception("Permission denied")

        tool = QBTool(client=mock_client)
        result = await tool.invoke(
            QBToolInput(action="delete", torrent_hash="abc123")
        )

        assert result.success is False
        assert "Permission denied" in result.error


# ── _get_status with timestamps ─────────────────────────────────────────


class TestQBToolStatusTimestamps:
    async def test_status_with_added_on_and_last_activity(self):
        mock_client = MagicMock()
        mock_client.torrents_info.return_value = [
            {
                "hash": "ABC123",
                "name": "test.mkv",
                "progress": 0.5,
                "state": "downloading",
                "dlspeed": 0,
                "size": 1000,
                "added_on": 1700000000,
                "last_activity": 1700001000,
            }
        ]

        tool = QBTool(client=mock_client)
        result = await tool.invoke(
            QBToolInput(action="get_status", torrent_hash="abc123")
        )

        assert result.success is True
        status = result.data["status"]
        assert status["added_at"] is not None
        assert status["last_speed_at"] is not None

    async def test_status_with_active_download_speed(self):
        mock_client = MagicMock()
        mock_client.torrents_info.return_value = [
            {
                "hash": "ABC123",
                "name": "test.mkv",
                "progress": 0.5,
                "state": "downloading",
                "dlspeed": 500000,
                "size": 1000,
                "added_on": 1700000000,
                "last_activity": None,
            }
        ]

        tool = QBTool(client=mock_client)
        result = await tool.invoke(
            QBToolInput(action="get_status", torrent_hash="abc123")
        )

        assert result.success is True
        assert result.data["status"]["download_speed"] == 500000


# ── _extract_hash_from_url ──────────────────────────────────────────────


class TestExtractHash:
    def test_extracts_40char_hex_hash(self):
        url = "magnet:?xt=urn:btih:abc123def4567890abc123def4567890abcdef12"
        assert _extract_hash_from_url(url) == "abc123def4567890abc123def4567890abcdef12"

    def test_extracts_base32_hash(self):
        # 32-char base32 string decodes to 20 bytes (40 hex chars)
        # This is the standard base32 info hash format in magnet links
        import base64
        b32 = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        expected_hex = base64.b32decode(b32).hex()
        url = f"magnet:?xt=urn:btih:{b32}"
        result = _extract_hash_from_url(url)
        assert result == expected_hex

    def test_returns_none_for_non_magnet_url(self):
        assert _extract_hash_from_url("https://example.com/file.torrent") is None

    def test_normalizes_uppercase_hash(self):
        url = "magnet:?xt=urn:btih:ABC123DEF4567890ABC123DEF4567890ABCDEF12"
        result = _extract_hash_from_url(url)
        assert result == "abc123def4567890abc123def4567890abcdef12"

    def test_handles_short_hash(self):
        url = "magnet:?xt=urn:btih:abcdef1234567890"
        result = _extract_hash_from_url(url)
        assert result == "abcdef1234567890"


# ── _get_value helper ───────────────────────────────────────────────────


class TestGetValue:
    def test_gets_from_dict(self):
        assert _get_value({"key": "value"}, "key") == "value"

    def test_gets_from_object(self):
        class Obj:
            key = "value"
        assert _get_value(Obj(), "key") == "value"

    def test_returns_none_for_missing_dict_key(self):
        assert _get_value({}, "missing") is None

    def test_returns_none_for_missing_attr(self):
        assert _get_value(object(), "missing") is None


# ── _unix_to_utc helper ─────────────────────────────────────────────────


class TestUnixToUtc:
    def test_converts_timestamp(self):
        from datetime import UTC
        dt = _unix_to_utc(1700000000)
        assert dt.year == 2023
        assert dt.tzinfo == UTC
