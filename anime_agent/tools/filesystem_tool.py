"""Filesystem tool for hardlinking, moving, copying, and creating directories."""

import shutil
from pathlib import Path

from anime_agent.config import settings
from anime_agent.tools.base import BaseTool, ToolInput, ToolOutput


class FileSystemToolInput(ToolInput):
    """Input for FileSystemTool."""

    action: str  # create_dir / list_files / hardlink / move / copy / symlink
    src: str | None = None
    dst: str | None = None


class FileSystemTool(BaseTool):
    """Perform filesystem operations for organizing downloaded media."""

    name = "filesystem"
    description = "Create directories and link/move/copy files for media organization."

    def __init__(self, library_path: str | None = None):
        self.library_path = library_path or settings.media_library_path

    async def healthcheck(self) -> ToolOutput:
        """Check that the configured media library path exists."""
        path = Path(self.library_path)
        if not path.exists():
            return ToolOutput(
                success=False,
                error=f"Media library path does not exist: {self.library_path}",
            )
        return ToolOutput(success=True, data={"status": "ok", "path": str(path)})

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Execute the requested filesystem action."""
        fs_input = FileSystemToolInput.model_validate(input_data)

        if fs_input.action == "create_dir":
            return await self._create_dir(fs_input)
        if fs_input.action == "list_files":
            return await self._list_files(fs_input)
        if fs_input.action in ("hardlink", "move", "copy", "symlink"):
            return await self._transfer(fs_input)

        return ToolOutput(success=False, error=f"Unknown action: {fs_input.action}")

    async def _create_dir(self, fs_input: FileSystemToolInput) -> ToolOutput:
        if not fs_input.dst:
            return ToolOutput(success=False, error="dst is required for create_dir")

        try:
            Path(fs_input.dst).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return ToolOutput(success=False, error=f"Failed to create directory: {exc}")

        return ToolOutput(success=True, data={"created": fs_input.dst})

    async def _list_files(self, fs_input: FileSystemToolInput) -> ToolOutput:
        if not fs_input.src:
            return ToolOutput(success=False, error="src is required for list_files")

        src_path = Path(fs_input.src)
        if not src_path.exists():
            return ToolOutput(success=False, error=f"Source does not exist: {fs_input.src}")

        try:
            if src_path.is_file():
                files = [str(src_path)]
            else:
                files = [str(p) for p in src_path.rglob("*") if p.is_file()]
        except OSError as exc:
            return ToolOutput(success=False, error=f"Failed to list files: {exc}")

        return ToolOutput(success=True, data={"files": files})

    async def _transfer(self, fs_input: FileSystemToolInput) -> ToolOutput:
        if not fs_input.src or not fs_input.dst:
            return ToolOutput(success=False, error="src and dst are required for transfer actions")

        src_path = Path(fs_input.src)
        dst_path = Path(fs_input.dst)

        if not src_path.exists():
            return ToolOutput(success=False, error=f"Source does not exist: {fs_input.src}")

        try:
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            if fs_input.action == "hardlink":
                dst_path.hardlink_to(src_path)
            elif fs_input.action == "symlink":
                dst_path.symlink_to(src_path)
            elif fs_input.action == "move":
                shutil.move(str(src_path), str(dst_path))
            elif fs_input.action == "copy":
                shutil.copy2(str(src_path), str(dst_path))
        except OSError as exc:
            return ToolOutput(success=False, error=f"Failed to {fs_input.action} file: {exc}")

        return ToolOutput(success=True, data={"dst": str(dst_path)})
