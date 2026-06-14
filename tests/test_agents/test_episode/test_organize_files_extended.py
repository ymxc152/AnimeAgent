"""Extended tests for OrganizeFilesNode — build_destination, derive_series_title, build_result."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from anime_agent.agents.episode.nodes.organize_files import _VIDEO_EXTENSIONS, OrganizeFilesNode


@pytest.fixture
def node():
    n = OrganizeFilesNode.__new__(OrganizeFilesNode)
    n.llm_tool = AsyncMock()
    n.bash_tool = AsyncMock()
    n.fs_tool = AsyncMock()
    n.library_path = Path("/media/library")
    n.template = "{series_title}/Season {season}/{series_title} - S{season:02d}E{episode:02d}.{ext}"
    n.NODE_NAME = "organize_files"
    n.SYSTEM_PROMPT = ""
    n.ACTIONS = {}
    n.MAX_LLM_CALLS = 3
    n.TERMINAL_ACTIONS = {"organize", "abort"}
    return n


# ── _derive_series_title ────────────────────────────────────────────────


class TestDeriveSeriesTitle:
    def test_removes_chinese_season_suffix(self):
        assert OrganizeFilesNode._derive_series_title("葬送的芙莉莲 第二季") == "葬送的芙莉莲"

    def test_removes_english_season_suffix(self):
        assert OrganizeFilesNode._derive_series_title("Frieren Season 2") == "Frieren"

    def test_removes_ordinal_season_suffix(self):
        assert OrganizeFilesNode._derive_series_title("Frieren 2nd Season") == "Frieren"

    def test_removes_s_number_suffix(self):
        assert OrganizeFilesNode._derive_series_title("Frieren S2") == "Frieren"

    def test_returns_original_when_no_suffix(self):
        assert OrganizeFilesNode._derive_series_title("葬送的芙莉莲") == "葬送的芙莉莲"

    def test_handles_empty_string(self):
        # Empty after stripping returns original
        result = OrganizeFilesNode._derive_series_title("")
        assert result == ""

    def test_removes_chinese_period_suffix(self):
        assert OrganizeFilesNode._derive_series_title("葬送的芙莉莲 第二期") == "葬送的芙莉莲"


# ── _build_destination ──────────────────────────────────────────────────


class TestBuildDestination:
    def test_builds_correct_path(self, node):
        dst = node._build_destination("Frieren", 1, 5, "mkv")
        assert "Frieren" in str(dst)
        assert "Season 1" in str(dst)
        assert "E05" in str(dst)
        assert dst.name.endswith(".mkv")

    def test_strips_leading_dot_from_ext(self, node):
        dst = node._build_destination("Frieren", 1, 1, ".mp4")
        assert dst.name.endswith(".mp4")

    def test_handles_ext_without_dot(self, node):
        dst = node._build_destination("Frieren", 1, 1, "mkv")
        assert dst.name.endswith(".mkv")

    def test_uses_library_path(self, node):
        dst = node._build_destination("Test", 1, 1, ".mkv")
        assert str(dst).startswith(str(node.library_path))


# ── _build_result ───────────────────────────────────────────────────────


class TestBuildResult:
    def test_organize_success_returns_organized_status(self, node):
        from anime_agent.agents.episode.base_agent import AgentAction
        action = AgentAction("organize")
        result = {"success": True, "organized_paths": ["/media/library/Frieren/S01E01.mkv"], "errors": []}
        state = {"episode_number": 1}

        built = node._build_result(action, result, state)
        assert built["status"] == "organized"
        assert len(built["organized_files"]) == 1

    def test_organize_success_with_warnings(self, node):
        from anime_agent.agents.episode.base_agent import AgentAction
        action = AgentAction("organize")
        result = {"success": True, "organized_paths": ["/media/library/Frieren/S01E01.mkv"], "errors": ["Some warning"]}
        state = {"episode_number": 1}

        built = node._build_result(action, result, state)
        assert built["status"] == "organized_with_warnings"

    def test_organize_failure_returns_failed(self, node):
        from anime_agent.agents.episode.base_agent import AgentAction
        action = AgentAction("organize")
        result = {"success": False, "output": "No video files found"}
        state = {"episode_number": 1}

        built = node._build_result(action, result, state)
        assert built["status"] == "failed"
        assert "No video files" in built["errors"][0]

    def test_abort_returns_failed(self, node):
        from anime_agent.agents.episode.base_agent import AgentAction
        action = AgentAction("abort")
        result = {"success": False, "output": "Cannot organize"}
        state = {"episode_number": 1}

        built = node._build_result(action, result, state)
        assert built["status"] == "failed"


# ── _act ────────────────────────────────────────────────────────────────


class TestAct:
    async def test_find_file_executes_bash(self, node):
        from anime_agent.agents.episode.base_agent import AgentAction
        node.bash_tool.invoke = AsyncMock(return_value=MagicMock(
            success=True, data={"stdout": "/path/to/file.mkv"}
        ))

        action = AgentAction("find_file", {"command": "find / -name '*.mkv'"})
        result = await node._act(action, {})
        assert result["success"] is True
        assert "file.mkv" in result["output"]

    async def test_find_file_no_command(self, node):
        from anime_agent.agents.episode.base_agent import AgentAction
        action = AgentAction("find_file", {})
        result = await node._act(action, {})
        assert result["success"] is False


# ── VIDEO_EXTENSIONS ────────────────────────────────────────────────────


class TestVideoExtensions:
    def test_common_formats_included(self):
        assert ".mkv" in _VIDEO_EXTENSIONS
        assert ".mp4" in _VIDEO_EXTENSIONS
        assert ".avi" in _VIDEO_EXTENSIONS
