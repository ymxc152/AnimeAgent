"""Extended tests for SendDownloadNode — _execute_add, _build_result, check_qb action."""

from unittest.mock import AsyncMock

import pytest

from anime_agent.agents.episode.base_agent import AgentAction
from anime_agent.agents.episode.nodes.send_download import SendDownloadNode
from anime_agent.tools.base import ToolOutput


@pytest.fixture
def node():
    n = SendDownloadNode.__new__(SendDownloadNode)
    n.llm_tool = AsyncMock()
    n.bash_tool = AsyncMock()
    n.qb_tool = AsyncMock()
    n.session_factory = None
    n.NODE_NAME = "send_download"
    n.SYSTEM_PROMPT = ""
    n.ACTIONS = {}
    n.MAX_LLM_CALLS = 2
    n.TERMINAL_ACTIONS = {"add", "abort"}
    return n


# ── _execute_add ────────────────────────────────────────────────────────


class TestExecuteAdd:
    async def test_adds_torrent_successfully(self, node):
        node.qb_tool.invoke = AsyncMock(return_value=ToolOutput(
            success=True, data={"hash": "abc123"}
        ))

        state = {
            "matched_torrent": {"info_hash": "abc123", "title": "Test", "link": "magnet:?xt=urn:btih:abc123"},
            "torrent_failed_hashes": [],
        }
        result = await node._execute_add(state)
        assert result["success"] is True
        assert result["hash"] == "abc123"

    async def test_returns_error_when_no_matched_torrent(self, node):
        state = {"matched_torrent": None}
        result = await node._execute_add(state)
        assert result["success"] is False
        assert "No matched torrent" in result["output"]

    async def test_returns_error_when_hash_already_failed(self, node):
        state = {
            "matched_torrent": {"info_hash": "abc123", "title": "Test", "link": "magnet:?xt=urn:btih:abc123"},
            "torrent_failed_hashes": ["abc123"],
        }
        result = await node._execute_add(state)
        assert result["success"] is False
        assert "already failed" in result["output"]

    async def test_returns_error_when_no_link(self, node):
        state = {
            "matched_torrent": {"info_hash": "abc123", "title": "Test", "link": None, "magnet_url": None},
            "torrent_failed_hashes": [],
        }
        result = await node._execute_add(state)
        assert result["success"] is False
        assert "No download link" in result["output"]

    async def test_returns_error_on_qb_failure(self, node):
        node.qb_tool.invoke = AsyncMock(return_value=ToolOutput(
            success=False, error="Connection refused"
        ))

        state = {
            "matched_torrent": {"info_hash": "abc123", "title": "Test", "link": "magnet:?xt=urn:btih:abc123"},
            "torrent_failed_hashes": [],
        }
        result = await node._execute_add(state)
        assert result["success"] is False
        assert "Connection refused" in result["output"]

    async def test_uses_magnet_url_fallback(self, node):
        node.qb_tool.invoke = AsyncMock(return_value=ToolOutput(
            success=True, data={"hash": "def456"}
        ))

        state = {
            "matched_torrent": {"info_hash": "def456", "title": "Test", "link": None, "magnet_url": "magnet:?xt=urn:btih:def456"},
            "torrent_failed_hashes": [],
        }
        result = await node._execute_add(state)
        assert result["success"] is True


# ── _build_result ───────────────────────────────────────────────────────


class TestBuildResult:
    def test_add_success_returns_downloading(self, node):
        action = AgentAction("add")
        result = {"success": True, "hash": "abc123", "output": "Torrent added"}
        state = {"matched_torrent": {"info_hash": "abc123", "title": "Test"}}

        built = node._build_result(action, result, state)
        assert built["status"] == "downloading"
        assert built["torrent_hash"] == "abc123"
        assert built["torrent_name"] == "Test"

    def test_abort_returns_failed_with_hash(self, node):
        action = AgentAction("abort")
        result = {"success": False, "output": "Cannot add"}
        state = {
            "matched_torrent": {"info_hash": "abc123"},
            "torrent_failed_hashes": [],
        }

        built = node._build_result(action, result, state)
        assert built["status"] == "failed"
        assert "abc123" in built["torrent_failed_hashes"]

    def test_abort_does_not_duplicate_hash(self, node):
        action = AgentAction("abort")
        result = {"success": False, "output": "Cannot add"}
        state = {
            "matched_torrent": {"info_hash": "abc123"},
            "torrent_failed_hashes": ["abc123"],
        }

        built = node._build_result(action, result, state)
        assert built["torrent_failed_hashes"].count("abc123") == 1

    def test_other_action_returns_retry_match(self, node):
        action = AgentAction("unknown")
        result = {"output": "Some error"}
        state = {}

        built = node._build_result(action, result, state)
        assert built["status"] == "retry_match"


# ── _act check_qb ───────────────────────────────────────────────────────


class TestActCheckQb:
    async def test_check_qb_executes_bash(self, node):
        node.bash_tool.invoke = AsyncMock(return_value=ToolOutput(
            success=True, data={"stdout": "qbittorrent.exe  1234"}
        ))

        action = AgentAction("check_qb")
        result = await node._act(action, {})
        assert result["success"] is True
        assert "qbittorrent" in result["output"].lower()
