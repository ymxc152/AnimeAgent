"""Tests for poll_download node."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from anime_agent.agents.episode.nodes.poll_download import PollDownloadNode
from anime_agent.tools.base import ToolOutput


def _mock_llm(action: str = "wait", **params) -> AsyncMock:
    """Return a mock LLM tool that returns a single JSON action."""
    mock = AsyncMock()
    mock.invoke.return_value = ToolOutput(
        success=True,
        data={"text": json.dumps({"action": action, "reasoning": "test", **params})},
    )
    return mock


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

    node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("wait"))
    result = await node(_state())

    assert result["status"] == "downloading"
    assert result["download_progress"] == 0.5
    assert result["resume_after"]
    qb_tool.invoke.assert_awaited()


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

    node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("done"))
    result = await node(_state())

    assert result["status"] == "downloaded"
    assert result["download_files"] == ["/downloads/Anime - 01.mkv"]
    assert result["torrent_name"] == "Anime - 01.mkv"


async def test_poll_download_fails_without_hash():
    """poll_download should fail if no torrent hash is present."""
    node = PollDownloadNode(qb_tool=AsyncMock(), llm_tool=_mock_llm("abort"))
    result = await node(_state(torrent_hash=None))

    assert result["status"] == "failed"
    assert result["errors"]


async def test_poll_download_captures_tool_error():
    """poll_download should handle qBittorrent errors by switching candidates."""
    qb_tool = AsyncMock()
    qb_tool.invoke.side_effect = [
        ToolOutput(success=False, error="qB down"),  # _load_context fails
        ToolOutput(success=False, error="qB down"),  # _act switch tries delete
    ]

    node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("switch"))
    result = await node(_state())

    assert result["status"] == "retry_match"
    assert "abc1" in result["torrent_failed_hashes"]


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

    node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("done"))
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

    node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("wait"))
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

    node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("switch"))
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

    node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("switch"))
    result = await node(_state())

    assert result["status"] == "retry_match"


async def test_poll_download_deletes_torrent_when_switching():
    """poll_download should delete the torrent from qBittorrent when switching candidates."""
    qb_tool = AsyncMock()
    qb_tool.invoke.side_effect = [
        ToolOutput(success=True, data={"status": {"progress": 0.0, "state": "error"}}),
        ToolOutput(success=True, data={"deleted": True}),
    ]

    node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("switch"))
    result = await node(_state())

    assert result["status"] == "retry_match"
    assert qb_tool.invoke.await_count == 2
    delete_call = qb_tool.invoke.await_args_list[1][0][0]
    assert delete_call.action == "delete"
    assert delete_call.torrent_hash == "abc1"
    assert delete_call.delete_files is False


async def test_poll_download_uses_shorter_interval_for_metadata():
    """poll_download should poll more frequently while metadata is downloading (LLM decides interval)."""
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"status": {"progress": 0.0, "state": "metaDL"}},
    )

    node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("wait", interval=120))
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
        node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("done"))
        result = await node(_state())

    assert result["status"] == "downloaded"
    assert result["download_files"] == ["Z:\\下载\\Anime - 01.mkv"]


async def test_poll_download_uses_longer_interval_for_healthy():
    """poll_download should poll less frequently for healthy downloads (LLM decides interval)."""
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

    node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("wait", interval=1800))
    result = await node(_state())

    assert result["status"] == "downloading"
    resume_after = datetime.fromisoformat(result["resume_after"])
    expected_min = datetime.now(UTC) + timedelta(minutes=29)
    expected_max = datetime.now(UTC) + timedelta(minutes=31)
    assert expected_min < resume_after < expected_max


async def test_poll_download_enforces_minimum_metadata_interval():
    """Metadata state should enforce the 2-minute minimum even if LLM asks for less."""
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"status": {"progress": 0.0, "state": "metaDL"}},
    )

    node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("wait", interval=1))
    result = await node(_state())

    assert result["status"] == "downloading"
    resume_after = datetime.fromisoformat(result["resume_after"])
    expected_min = datetime.now(UTC) + timedelta(seconds=110)
    expected_max = datetime.now(UTC) + timedelta(seconds=130)
    assert expected_min < resume_after < expected_max


async def test_poll_download_enforces_minimum_stalled_interval():
    """Stalled state should enforce the 5-minute minimum even if LLM asks for less."""
    now = datetime.now(UTC)
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={
            "status": {
                "progress": 0.3,
                "state": "stalledDL",
                "download_speed": 0,
                "added_at": now - timedelta(hours=2),
                "last_speed_at": now - timedelta(hours=2),
            }
        },
    )

    node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("wait", interval=1))
    result = await node(_state())

    assert result["status"] == "downloading"
    resume_after = datetime.fromisoformat(result["resume_after"])
    expected_min = datetime.now(UTC) + timedelta(seconds=290)
    expected_max = datetime.now(UTC) + timedelta(seconds=310)
    assert expected_min < resume_after < expected_max


async def test_poll_download_uses_healthy_interval_when_llm_requests_shorter():
    """Healthy state should enforce the 30-minute minimum if LLM asks for less."""
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

    node = PollDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("wait", interval=60))
    result = await node(_state())

    assert result["status"] == "downloading"
    resume_after = datetime.fromisoformat(result["resume_after"])
    expected_min = datetime.now(UTC) + timedelta(minutes=29)
    expected_max = datetime.now(UTC) + timedelta(minutes=31)
    assert expected_min < resume_after < expected_max
