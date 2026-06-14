"""Tests for send_download node."""

import json
from unittest.mock import AsyncMock

from anime_agent.agents.episode.nodes.send_download import SendDownloadNode
from anime_agent.tools.base import ToolOutput


def _mock_llm(action: str = "add", **params) -> AsyncMock:
    """Return a mock LLM tool that returns a single JSON action."""
    mock = AsyncMock()
    mock.invoke.return_value = ToolOutput(
        success=True,
        data={"text": json.dumps({"action": action, "reasoning": "test", **params})},
    )
    return mock


_DEFAULT_TORRENT = {
    "info_hash": "abc1",
    "title": "[Sub] Anime - 01 [1080p].mkv",
    "link": "magnet:?xt=urn:btih:abc1",
}


def _state(matched_torrent: dict | None = _DEFAULT_TORRENT) -> dict:
    return {
        "subscription_id": 42,
        "episode_number": 1,
        "matched_torrent": matched_torrent,
        "torrent_failed_hashes": [],
    }


async def test_send_download_adds_torrent():
    """send_download should add the matched torrent to qBittorrent."""
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(
        success=True, data={"hash": "abc1"}
    )

    node = SendDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("add"))
    result = await node(_state())

    assert result["torrent_hash"] == "abc1"
    assert result["status"] == "downloading"
    qb_tool.invoke.assert_awaited_once()


async def test_send_download_fails_without_matched_torrent():
    """send_download should fail if no torrent was matched."""
    node = SendDownloadNode(qb_tool=AsyncMock(), llm_tool=_mock_llm("abort"))
    result = await node(_state(matched_torrent=None))

    assert result["status"] == "failed"
    assert result["errors"]


async def test_send_download_skips_already_failed_hash():
    """send_download should not retry a failed hash."""
    state = _state()
    state["torrent_failed_hashes"] = ["abc1"]

    node = SendDownloadNode(qb_tool=AsyncMock(), llm_tool=_mock_llm("add"))
    result = await node(state)

    assert result["status"] == "failed"
    assert "already failed" in result["errors"][0]


async def test_send_download_captures_tool_error():
    """send_download should capture qBittorrent errors."""
    qb_tool = AsyncMock()
    qb_tool.invoke.return_value = ToolOutput(success=False, error="qB down")

    node = SendDownloadNode(qb_tool=qb_tool, llm_tool=_mock_llm("add"))
    result = await node(_state())

    assert result["status"] == "failed"
    assert "qB down" in result["errors"][0]
