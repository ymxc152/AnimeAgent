"""Tests for organize_files node."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

from anime_agent.agents.episode.nodes.organize_files import OrganizeFilesNode
from anime_agent.tools.base import ToolOutput


def _mock_llm(action: str = "organize", **params) -> AsyncMock:
    """Return a mock LLM tool that returns a single JSON action."""
    mock = AsyncMock()
    mock.invoke.return_value = ToolOutput(
        success=True,
        data={"text": json.dumps({"action": action, "reasoning": "test", **params})},
    )
    return mock


_DEFAULT_FILES = ["/downloads/Test Anime - 01.mkv"]


def _state(download_files: list[str] | None = _DEFAULT_FILES) -> dict:
    return {
        "subscription_id": 42,
        "episode_number": 1,
        "title_romaji": "Test Anime",
        "title_native": "テストアニメ",
        "title_chinese": "测试动画",
        "download_files": download_files,
    }


def _fs_tool_for_success() -> AsyncMock:
    """Return a filesystem tool mock that succeeds for list/create/hardlink."""
    fs_tool = AsyncMock()

    async def side_effect(input_data):
        action = input_data.action
        if action == "list_files":
            return ToolOutput(
                success=True,
                data={"files": [input_data.src]},
            )
        if action == "create_dir":
            Path(input_data.dst).mkdir(parents=True, exist_ok=True)
            return ToolOutput(success=True, data={"created": input_data.dst})
        if action == "hardlink":
            Path(input_data.dst).parent.mkdir(parents=True, exist_ok=True)
            Path(input_data.dst).write_text("linked")
            return ToolOutput(success=True, data={"dst": input_data.dst})
        return ToolOutput(success=False, error="Unknown action")

    fs_tool.invoke.side_effect = side_effect
    return fs_tool


async def test_organize_files_creates_hardlinks(tmp_path: Path):
    """organize_files should create directories and hardlink video files."""
    library = tmp_path / "library"
    fs_tool = _fs_tool_for_success()

    node = OrganizeFilesNode(
        fs_tool=fs_tool,
        library_path=str(library),
        template="{title} S{season:02d}E{episode:02d}.{ext}",
        llm_tool=_mock_llm(),
    )
    result = await node(_state())

    assert result["status"] == "organized"
    assert result["organized_files"]
    assert str(library) in result["organized_path"]


async def test_organize_files_fails_without_download_files():
    """organize_files should fail when no files were downloaded."""
    fs_tool = AsyncMock()
    node = OrganizeFilesNode(
        fs_tool=fs_tool,
        llm_tool=_mock_llm(),
    )
    result = await node(_state(download_files=[]))

    assert result["status"] == "failed"
    assert "No video files found" in result["errors"][0]


async def test_organize_files_skips_non_video_files(tmp_path: Path):
    """organize_files should only organize video files."""
    library = tmp_path / "library"
    fs_tool = AsyncMock()

    async def side_effect(input_data):
        if input_data.action == "list_files":
            return ToolOutput(
                success=True,
                data={"files": ["/downloads/readme.txt", "/downloads/video.mp4"]},
            )
        if input_data.action == "create_dir":
            return ToolOutput(success=True, data={"created": input_data.dst})
        if input_data.action == "hardlink":
            return ToolOutput(success=True, data={"dst": input_data.dst})
        return ToolOutput(success=False, error="Unknown action")

    fs_tool.invoke.side_effect = side_effect

    node = OrganizeFilesNode(
        fs_tool=fs_tool,
        library_path=str(library),
        template="{title} S{season:02d}E{episode:02d}.{ext}",
        llm_tool=_mock_llm(),
    )
    result = await node(_state())

    assert result["status"] == "organized"
    assert len(result["organized_files"]) == 1
    assert result["organized_files"][0].endswith(".mp4")


async def test_organize_files_fails_when_list_files_errors():
    """organize_files should fail if listing files fails (skipped paths yield no video files)."""
    fs_tool = AsyncMock()
    fs_tool.invoke.return_value = ToolOutput(success=False, error="Permission denied")

    node = OrganizeFilesNode(fs_tool=fs_tool, llm_tool=_mock_llm())
    result = await node(_state())

    assert result["status"] == "failed"
    assert "No video files found" in result["errors"][0]


async def test_organize_files_fails_when_no_video_files_found():
    """organize_files should fail when no video files are present."""
    fs_tool = AsyncMock()
    fs_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"files": ["/downloads/poster.jpg"]},
    )

    node = OrganizeFilesNode(fs_tool=fs_tool, llm_tool=_mock_llm())
    result = await node(_state())

    assert result["status"] == "failed"
    assert "No video files found" in result["errors"][0]


async def test_organize_files_strips_season_from_series_folder(tmp_path: Path):
    """The top-level folder should use the series title without season suffixes."""
    library = tmp_path / "library"
    fs_tool = _fs_tool_for_success()

    node = OrganizeFilesNode(
        fs_tool=fs_tool,
        library_path=str(library),
        llm_tool=_mock_llm(),
    )
    state = {
        "subscription_id": 1,
        "episode_number": 9,
        "title_chinese": "复制品的我也会谈恋爱。 第二季",
        "title_romaji": "Fukusei-gaeri no Koibito. Season 2",
        "title_native": "",
        "download_files": ["/downloads/ep09.mkv"],
        "season": 2,
    }
    result = await node(state)

    assert result["status"] == "organized"
    assert result["organized_files"]
    organized = result["organized_files"][0]
    assert "复制品的我也会谈恋爱。" in organized
    assert "第二季" not in organized.replace("复制品的我也会谈恋爱。", "")


def test_derive_series_title_strips_common_season_suffixes():
    """_derive_series_title should remove season/sequel markers."""
    node = OrganizeFilesNode(fs_tool=AsyncMock(), llm_tool=_mock_llm())
    assert node._derive_series_title("测试动画 第二季") == "测试动画"
    assert node._derive_series_title("Test Anime Season 2") == "Test Anime"
    assert node._derive_series_title("Test Anime 2nd Season") == "Test Anime"
    assert node._derive_series_title("Test Anime S2") == "Test Anime"
    assert node._derive_series_title("测试动画 第2期") == "测试动画"
    assert node._derive_series_title("测试动画") == "测试动画"
