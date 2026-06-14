"""Extended tests for PollDownloadNode — _build_result, _load_context, _map_remote_path."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from anime_agent.agents.episode.base_agent import AgentAction
from anime_agent.agents.episode.nodes.poll_download import PollDownloadNode
from anime_agent.tools.base import ToolOutput


@pytest.fixture
def node():
    n = PollDownloadNode.__new__(PollDownloadNode)
    n.llm_tool = AsyncMock()
    n.bash_tool = AsyncMock()
    n.qb_tool = AsyncMock()
    n.health = MagicMock()
    n.NODE_NAME = "poll_download"
    n.SYSTEM_PROMPT = ""
    n.ACTIONS = {}
    n.MAX_LLM_CALLS = 2
    n.TERMINAL_ACTIONS = {"done", "wait", "switch", "search_alt", "abort"}
    return n


# ── _load_context ───────────────────────────────────────────────────────


class TestLoadContext:
    async def test_returns_error_when_no_hash(self, node):
        state = {"torrent_hash": None}
        ctx = await node._load_context(state)
        assert ctx["health_eval"]["state"] == "error"
        assert ctx["health_eval"]["recommend"] == "switch"

    async def test_returns_error_on_qb_failure(self, node):
        node.qb_tool.invoke = AsyncMock(return_value=ToolOutput(
            success=False, error="qB offline"
        ))
        state = {"torrent_hash": "abc123"}
        ctx = await node._load_context(state)
        assert ctx["health_eval"]["state"] == "error"
        assert "qB offline" in ctx["health_eval"]["reason"]

    async def test_loads_status_and_health(self, node):
        node.qb_tool.invoke = AsyncMock(return_value=ToolOutput(
            success=True,
            data={"status": {"progress": 0.5, "download_speed": 1024}},
        ))
        node.health.evaluate.return_value = {"state": "downloading", "recommend": "wait"}

        state = {"torrent_hash": "abc123"}
        ctx = await node._load_context(state)
        assert ctx["qb_status"]["progress"] == 0.5
        assert ctx["health_eval"]["state"] == "downloading"


# ── _build_result ───────────────────────────────────────────────────────


class TestBuildResult:
    def test_done_returns_downloaded(self, node):
        action = AgentAction("done")
        state = {
            "_poll_context": {
                "qb_status": {"content_path": "/downloads/anime.mkv", "name": "test.mkv"},
            },
        }
        # _map_remote_path returns the path unchanged when no mapping configured
        result = node._build_result(action, {}, state)
        assert result["status"] == "downloaded"
        assert result["download_progress"] == 1.0
        assert len(result["download_files"]) == 1

    def test_switch_returns_retry_match(self, node):
        action = AgentAction("switch")
        state = {
            "torrent_hash": "abc123",
            "torrent_failed_hashes": [],
            "_poll_context": {"qb_status": {}},
        }
        result = node._build_result(action, {}, state)
        assert result["status"] == "retry_match"
        assert "abc123" in result["torrent_failed_hashes"]
        assert result["matched_torrent"] is None

    def test_switch_does_not_duplicate_hash(self, node):
        action = AgentAction("switch")
        state = {
            "torrent_hash": "abc123",
            "torrent_failed_hashes": ["abc123"],
            "_poll_context": {"qb_status": {}},
        }
        result = node._build_result(action, {}, state)
        assert result["torrent_failed_hashes"].count("abc123") == 1

    def test_wait_returns_downloading_with_resume(self, node):
        action = AgentAction("wait", {"interval": 300})
        state = {"_poll_context": {"qb_status": {"progress": 0.5}}}
        result = node._build_result(action, {}, state)
        assert result["status"] == "downloading"
        assert result["download_progress"] == 0.5
        assert "resume_after" in result

    def test_search_alt_returns_retry_match(self, node):
        action = AgentAction("search_alt")
        state = {
            "torrent_hash": "abc123",
            "torrent_failed_hashes": [],
            "_poll_context": {"qb_status": {}},
        }
        result = node._build_result(action, {}, state)
        assert result["status"] == "retry_match"

    def test_unknown_action_returns_downloading_with_default_interval(self, node):
        action = AgentAction("something_else")
        state = {"_poll_context": {"qb_status": {"progress": 0.3}}}
        result = node._build_result(action, {}, state)
        assert result["status"] == "downloading"


# ── _map_remote_path ────────────────────────────────────────────────────


class TestMapRemotePath:
    def test_returns_none_for_none_input(self, node):
        assert node._map_remote_path(None) is None

    def test_returns_path_unchanged_when_no_mapping(self, node):
        import anime_agent.config as cfg
        original_remote = cfg.settings.qb_path_map_remote
        original_local = cfg.settings.qb_path_map_local
        try:
            cfg.settings.qb_path_map_remote = ""
            cfg.settings.qb_path_map_local = ""
            assert node._map_remote_path("/downloads/test.mkv") == "/downloads/test.mkv"
        finally:
            cfg.settings.qb_path_map_remote = original_remote
            cfg.settings.qb_path_map_local = original_local

    def test_maps_remote_to_local(self, node):
        import anime_agent.config as cfg
        original_remote = cfg.settings.qb_path_map_remote
        original_local = cfg.settings.qb_path_map_local
        try:
            cfg.settings.qb_path_map_remote = "/remote/downloads"
            cfg.settings.qb_path_map_local = "/local/media"
            result = node._map_remote_path("/remote/downloads/anime/test.mkv")
            # The implementation normalizes to backslashes then concatenates,
            # so the result may have mixed separators on Windows
            assert "anime" in result
            assert "test.mkv" in result
            assert result.startswith("/local/media")
        finally:
            cfg.settings.qb_path_map_remote = original_remote
            cfg.settings.qb_path_map_local = original_local

    def test_returns_path_unchanged_when_no_prefix_match(self, node):
        import anime_agent.config as cfg
        original_remote = cfg.settings.qb_path_map_remote
        original_local = cfg.settings.qb_path_map_local
        try:
            cfg.settings.qb_path_map_remote = "/remote/downloads"
            cfg.settings.qb_path_map_local = "/local/media"
            result = node._map_remote_path("/other/path/test.mkv")
            assert result == "/other/path/test.mkv"
        finally:
            cfg.settings.qb_path_map_remote = original_remote
            cfg.settings.qb_path_map_local = original_local


# ── _act ────────────────────────────────────────────────────────────────


class TestAct:
    async def test_switch_deletes_torrent(self, node):
        node.qb_tool.invoke = AsyncMock(return_value=ToolOutput(success=True, data={}))
        action = AgentAction("switch")
        state = {"torrent_hash": "abc123"}
        result = await node._act(action, state)
        assert result["success"] is True

    async def test_switch_no_hash(self, node):
        action = AgentAction("switch")
        state = {"torrent_hash": None}
        result = await node._act(action, state)
        assert result["success"] is True

    async def test_check_system_executes_bash(self, node):
        node.bash_tool.invoke = AsyncMock(return_value=ToolOutput(
            success=True, data={"stdout": "Filesystem  1K-blocks"}
        ))
        action = AgentAction("check_system")
        result = await node._act(action, {})
        assert result["success"] is True
