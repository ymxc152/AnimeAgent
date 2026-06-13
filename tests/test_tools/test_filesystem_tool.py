"""Tests for FileSystemTool."""

import os
from pathlib import Path

from anime_agent.tools.filesystem_tool import FileSystemTool, FileSystemToolInput


async def test_filesystem_tool_creates_directory(tmp_path: Path):
    """FileSystemTool should create a directory tree."""
    target = tmp_path / "new" / "folder"

    tool = FileSystemTool()
    result = await tool.invoke(
        FileSystemToolInput(action="create_dir", dst=str(target))
    )

    assert result.success is True
    assert target.exists()
    assert target.is_dir()


async def test_filesystem_tool_hardlinks_file(tmp_path: Path):
    """FileSystemTool should create a hard link."""
    src = tmp_path / "source.txt"
    src.write_text("hello")
    dst = tmp_path / "link.txt"

    tool = FileSystemTool()
    result = await tool.invoke(
        FileSystemToolInput(action="hardlink", src=str(src), dst=str(dst))
    )

    assert result.success is True
    assert dst.exists()
    assert dst.read_text() == "hello"
    if os.name != "nt":
        assert dst.stat().st_ino == src.stat().st_ino


async def test_filesystem_tool_moves_file(tmp_path: Path):
    """FileSystemTool should move a file."""
    src = tmp_path / "source.txt"
    src.write_text("hello")
    dst = tmp_path / "moved.txt"

    tool = FileSystemTool()
    result = await tool.invoke(
        FileSystemToolInput(action="move", src=str(src), dst=str(dst))
    )

    assert result.success is True
    assert dst.exists()
    assert dst.read_text() == "hello"
    assert not src.exists()


async def test_filesystem_tool_copies_file(tmp_path: Path):
    """FileSystemTool should copy a file."""
    src = tmp_path / "source.txt"
    src.write_text("hello")
    dst = tmp_path / "copied.txt"

    tool = FileSystemTool()
    result = await tool.invoke(
        FileSystemToolInput(action="copy", src=str(src), dst=str(dst))
    )

    assert result.success is True
    assert dst.exists()
    assert dst.read_text() == "hello"
    assert src.exists()


async def test_filesystem_tool_returns_error_when_source_missing(tmp_path: Path):
    """FileSystemTool should fail when the source file does not exist."""
    src = tmp_path / "missing.txt"
    dst = tmp_path / "dst.txt"

    tool = FileSystemTool()
    result = await tool.invoke(
        FileSystemToolInput(action="copy", src=str(src), dst=str(dst))
    )

    assert result.success is False
    assert "does not exist" in result.error.lower()


async def test_filesystem_tool_requires_src_for_link_and_move():
    """FileSystemTool should fail when src is missing for copy/move/hardlink."""
    tool = FileSystemTool()
    result = await tool.invoke(FileSystemToolInput(action="copy", dst="/tmp/dst"))

    assert result.success is False
    assert "src" in result.error.lower()
