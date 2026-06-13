"""Tests for poll_download node."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from anime_agent.agents.episode.nodes.poll_download import PollDownloadNode
from anime_agent.tools.base import ToolOutput


def _state(torrent_hash: str | None = "abc1") -> dict:
    return {
        "subscription_id": 42,
        "episode_number": 1,
        "torrent_hash": torrent_hash,
    }


async def test_poll_download_returns_downloading_when_incomplete():
    """poll_download should report downloading when progress < 1."""
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"status": {"progress": 0.5, "state": "downloading"}},
    )

    node = PollDownloadNode(qb_tool=qb_tool)
    result = await node(_state())

    assert result["status"] == "downloading"
    assert result["download_progress"] == 0.5
    assert result["resume_after"]
    qb_tool.invoke.assert_awaited_once()


async def test_poll_download_returns_downloaded_when_complete():
    """poll_download should report downloaded and capture files when progress == 1."""
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={
            "status": {
                "progress": 1.0,
                "state": "uploading",
                "content_path": "/downloads/Anime - 01.mkv",
                "name": "Anime - 01.mkv",
                "added_at": datetime.now(UTC),
                "last_speed_at": datetime.now(UTC),
            }
        },
    )

    node = PollDownloadNode(qb_tool=qb_tool)
    result = await node(_state())

    assert result["status"] == "downloaded"
    assert result["download_files"] == ["/downloads/Anime - 01.mkv"]
    assert result["torrent_name"] == "Anime - 01.mkv"


async def test_poll_download_fails_without_hash():
    """poll_download should fail if no torrent hash is present."""
    node = PollDownloadNode(qb_tool=AsyncMock())
    result = await node(_state(torrent_hash=None))

    assert result["status"] == "failed"
    assert result["errors"]


async def test_poll_download_captures_tool_error():
    """poll_download should capture qBittorrent errors."""
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(success=False, error="qB down")

    node = PollDownloadNode(qb_tool=qb_tool)
    result = await node(_state())

    assert result["status"] == "failed"
    assert "qB down" in result["errors"][0]


async def test_poll_download_uses_save_path_when_content_path_missing():
    """poll_download should fall back to save_path when content_path is absent."""
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={
            "status": {
                "progress": 1.0,
                "state": "uploading",
                "save_path": "/downloads",
                "name": "Anime - 01",
                "added_at": datetime.now(UTC),
                "last_speed_at": datetime.now(UTC),
            }
        },
    )

    node = PollDownloadNode(qb_tool=qb_tool)
    result = await node(_state())

    assert result["status"] == "downloaded"
    assert result["download_files"] == ["/downloads"]


async def test_resume_after_is_future_timestamp():
    """The resume_after timestamp should be in the future."""
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"status": {"progress": 0.1}},
    )

    node = PollDownloadNode(qb_tool=qb_tool)
    result = await node(_state())

    resume_after = datetime.fromisoformat(result["resume_after"])
    assert resume_after.tzinfo is not None
    assert resume_after > datetime.now(resume_after.tzinfo)


async def test_poll_download_returns_retry_match_on_error_state():
    """poll_download should return retry_match when torrent is in error state."""
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"status": {"progress": 0.3, "state": "error"}},
    )

    node = PollDownloadNode(qb_tool=qb_tool)
    result = await node(_state())

    assert result["status"] == "retry_match"
    assert "abc1" in result["torrent_failed_hashes"]
    assert result["matched_torrent"] is None


async def test_poll_download_returns_retry_match_on_missing_files():
    """poll_download should return retry_match when torrent has missing files."""
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"status": {"progress": 0.0, "state": "missingFiles"}},
    )

    node = PollDownloadNode(qb_tool=qb_tool)
    result = await node(_state())

    assert result["status"] == "retry_match"


async def test_poll_download_deletes_torrent_when_switching():
    """poll_download should delete the torrent from qBittorrent when switching candidates."""
    qb_tool = AsyncMock()
    qb_tool.invoke.side_effect = [
        ToolOutput(success=True, data={"status": {"progress": 0.0, "state": "error"}}),
        ToolOutput(success=True, data={"deleted": True}),
    ]

    node = PollDownloadNode(qb_tool=qb_tool)
    result = await node(_state())

    assert result["status"] == "retry_match"
    assert qb_tool.invoke.await_count == 2
    delete_call = qb_tool.invoke.await_args_list[1][0][0]
    assert delete_call.action == "delete"
    assert delete_call.torrent_hash == "abc1"
    assert delete_call.delete_files is False


async def test_poll_download_uses_shorter_interval_for_metadata():
    """poll_download should poll more frequently while metadata is downloading."""
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"status": {"progress": 0.0, "state": "metaDL"}},
    )

    node = PollDownloadNode(qb_tool=qb_tool)
    result = await node(_state())

    assert result["status"] == "downloading"
    resume_after = datetime.fromisoformat(result["resume_after"])
    expected_max = datetime.now(UTC) + timedelta(minutes=3)
    assert resume_after < expected_max


async def test_poll_download_maps_remote_path_to_local_share():
    """poll_download should translate qBittorrent's remote path to local mounted path."""
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={
            "status": {
                "progress": 1.0,
                "state": "uploading",
                "content_path": "F:\\下载\\Anime - 01.mkv",
                "name": "Anime - 01.mkv",
                "added_at": datetime.now(UTC),
                "last_speed_at": datetime.now(UTC),
            }
        },
    )

    with patch(
        "anime_agent.agents.episode.nodes.poll_download.settings.qb_path_map_remote",
        "F:\\下载",
    ), patch(
        "anime_agent.agents.episode.nodes.poll_download.settings.qb_path_map_local",
        "Z:\\下载",
    ):
        node = PollDownloadNode(qb_tool=qb_tool)
        result = await node(_state())

    assert result["status"] == "downloaded"
    assert result["download_files"] == ["Z:\\下载\\Anime - 01.mkv"]


async def test_poll_download_uses_longer_interval_for_healthy():
    """poll_download should poll less frequently for healthy downloads."""
    now = datetime.now(UTC)
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={
            "status": {
                "progress": 0.5,
                "state": "downloading",
                "download_speed": 1024000,
                "added_at": now - timedelta(minutes=10),
                "last_speed_at": now - timedelta(minutes=5),
            }
        },
    )

    node = PollDownloadNode(qb_tool=qb_tool)
    result = await node(_state())

    assert result["status"] == "downloading"
    resume_after = datetime.fromisoformat(result["resume_after"])
    expected_min = datetime.now(UTC) + timedelta(minutes=25)
    expected_max = datetime.now(UTC) + timedelta(minutes=35)
    assert expected_min < resume_after < expected_max
