"""Extended tests for FileSystemTool — list_files, symlink, edge cases."""

from pathlib import Path

from anime_agent.tools.filesystem_tool import FileSystemTool, FileSystemToolInput

# ── list_files ──────────────────────────────────────────────────────────


class TestListFiles:
    async def test_lists_files_in_directory(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.mkv").write_text("b")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "c.mp4").write_text("c")

        tool = FileSystemTool()
        result = await tool.invoke(
            FileSystemToolInput(action="list_files", src=str(tmp_path))
        )

        assert result.success is True
        files = result.data["files"]
        assert len(files) == 3
        file_names = {Path(f).name for f in files}
        assert file_names == {"a.txt", "b.mkv", "c.mp4"}

    async def test_lists_single_file(self, tmp_path):
        f = tmp_path / "single.txt"
        f.write_text("content")

        tool = FileSystemTool()
        result = await tool.invoke(
            FileSystemToolInput(action="list_files", src=str(f))
        )

        assert result.success is True
        assert len(result.data["files"]) == 1

    async def test_returns_error_for_missing_source(self, tmp_path):
        tool = FileSystemTool()
        result = await tool.invoke(
            FileSystemToolInput(action="list_files", src=str(tmp_path / "missing"))
        )

        assert result.success is False
        assert "does not exist" in result.error.lower()

    async def test_requires_src(self):
        tool = FileSystemTool()
        result = await tool.invoke(FileSystemToolInput(action="list_files"))

        assert result.success is False
        assert "src" in result.error.lower()


# ── create_dir edge cases ───────────────────────────────────────────────


class TestCreateDir:
    async def test_requires_dst(self):
        tool = FileSystemTool()
        result = await tool.invoke(FileSystemToolInput(action="create_dir"))

        assert result.success is False
        assert "dst" in result.error.lower()

    async def test_create_dir_is_idempotent(self, tmp_path):
        target = tmp_path / "existing"
        target.mkdir()

        tool = FileSystemTool()
        result = await tool.invoke(
            FileSystemToolInput(action="create_dir", dst=str(target))
        )

        assert result.success is True


# ── Unknown action ──────────────────────────────────────────────────────


class TestUnknownAction:
    async def test_returns_error_for_unknown_action(self):
        tool = FileSystemTool()
        result = await tool.invoke(FileSystemToolInput(action="nonexistent"))

        assert result.success is False
        assert "Unknown action" in result.error


# ── Transfer edge cases ─────────────────────────────────────────────────


class TestTransferEdgeCases:
    async def test_requires_both_src_and_dst(self):
        tool = FileSystemTool()
        result = await tool.invoke(FileSystemToolInput(action="copy", src="/some/path"))

        assert result.success is False
        assert "src" in result.error.lower() and "dst" in result.error.lower()

    async def test_copy_to_nested_directory(self, tmp_path):
        src = tmp_path / "source.txt"
        src.write_text("data")
        dst = tmp_path / "deep" / "nested" / "dir" / "file.txt"

        tool = FileSystemTool()
        result = await tool.invoke(
            FileSystemToolInput(action="copy", src=str(src), dst=str(dst))
        )

        assert result.success is True
        assert dst.exists()
        assert dst.read_text() == "data"


# ── Healthcheck ─────────────────────────────────────────────────────────


class TestHealthcheck:
    async def test_healthcheck_succeeds_when_path_exists(self, tmp_path):
        tool = FileSystemTool(library_path=str(tmp_path))
        result = await tool.healthcheck()

        assert result.success is True
        assert result.data["status"] == "ok"

    async def test_healthcheck_fails_when_path_missing(self):
        tool = FileSystemTool(library_path="/nonexistent/path/that/does/not/exist")
        result = await tool.healthcheck()

        assert result.success is False
        assert "does not exist" in result.error.lower()
