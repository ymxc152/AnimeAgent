"""Tests for poll_download node."""

from datetime import datetime
from unittest.mock import AsyncMock

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
                "save_path": "/downloads",
                "name": "Anime - 01",
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
