"""Tests for QBTool."""

from unittest.mock import MagicMock, PropertyMock

from anime_agent.tools.qb_tool import QBTool, QBToolInput


async def test_qb_tool_adds_torrent_from_magnet():
    """QBTool should add a torrent and return its normalized hash."""
    mock_client = MagicMock()
    mock_client.torrents_add.return_value = "Ok."

    tool = QBTool(client=mock_client)
    result = await tool.invoke(
        QBToolInput(
            action="add",
            torrent_url="magnet:?xt=urn:btih:abc123def4567890abc123def4567890abcdef12&dn=anime",
            save_path="C:\\Downloads\\Anime",
        )
    )

    assert result.success is True
    assert result.data["hash"] == "abc123def4567890abc123def4567890abcdef12"
    mock_client.torrents_add.assert_called_once_with(
        urls="magnet:?xt=urn:btih:abc123def4567890abc123def4567890abcdef12&dn=anime",
        save_path="C:\\Downloads\\Anime",
        tags="anime-agent",
    )


async def test_qb_tool_add_torrent_requires_url():
    """QBTool should fail when adding without a torrent URL."""
    tool = QBTool(client=MagicMock())
    result = await tool.invoke(QBToolInput(action="add"))

    assert result.success is False
    assert "torrent_url" in result.error


async def test_qb_tool_returns_torrent_status():
    """QBTool should fetch and normalize torrent status from qBittorrent."""
    mock_client = MagicMock()
    mock_client.torrents_info.return_value = [
        {
            "hash": "ABC123DEF4567890ABC123DEF4567890ABCDEF12",
            "name": "Anime - 01.mkv",
            "progress": 0.75,
            "state": "downloading",
            "dlspeed": 1024000,
            "size": 536870912,
        }
    ]

    tool = QBTool(client=mock_client)
    result = await tool.invoke(
        QBToolInput(action="get_status", torrent_hash="abc123def4567890abc123def4567890abcdef12")
    )

    assert result.success is True
    status = result.data["status"]
    assert status["hash"] == "abc123def4567890abc123def4567890abcdef12"
    assert status["name"] == "Anime - 01.mkv"
    assert status["progress"] == 0.75
    assert status["state"] == "downloading"
    assert status["download_speed"] == 1024000
    assert status["size"] == 536870912
    mock_client.torrents_info.assert_called_once_with(torrent_hashes="ABC123DEF4567890ABC123DEF4567890ABCDEF12")


async def test_qb_tool_returns_not_found_when_torrent_missing():
    """QBTool should report not found when the torrent hash does not exist."""
    mock_client = MagicMock()
    mock_client.torrents_info.return_value = []

    tool = QBTool(client=mock_client)
    result = await tool.invoke(
        QBToolInput(action="get_status", torrent_hash="abc123def4567890abc123def4567890abcdef12")
    )

    assert result.success is False
    assert "not found" in result.error.lower()


async def test_qb_tool_deletes_torrent():
    """QBTool should delete a torrent by hash."""
    mock_client = MagicMock()

    tool = QBTool(client=mock_client)
    result = await tool.invoke(
        QBToolInput(action="delete", torrent_hash="abc123def4567890abc123def4567890abcdef12")
    )

    assert result.success is True
    mock_client.torrents_delete.assert_called_once_with(
        torrent_hashes="ABC123DEF4567890ABC123DEF4567890ABCDEF12", delete_files=False
    )


async def test_qb_tool_healthcheck_succeeds():
    """QBTool healthcheck should succeed when qBittorrent responds."""
    mock_client = MagicMock()
    type(mock_client.app).version = PropertyMock(return_value="v4.6.0")

    tool = QBTool(client=mock_client)
    result = await tool.healthcheck()

    assert result.success is True
    assert result.data["version"] == "v4.6.0"


async def test_qb_tool_healthcheck_fails_on_connection_error():
    """QBTool healthcheck should fail when qBittorrent is unreachable."""
    mock_client = MagicMock()
    type(mock_client.app).version = PropertyMock(side_effect=Exception("Connection refused"))

    tool = QBTool(client=mock_client)
    result = await tool.healthcheck()

    assert result.success is False
    assert "Connection refused" in result.error
