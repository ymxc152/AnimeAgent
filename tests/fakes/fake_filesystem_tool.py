"""Filesystem fake that uses copy instead of hardlink for cross-platform tests."""

import shutil
from pathlib import Path

from anime_agent.tools.base import ToolInput, ToolOutput
from anime_agent.tools.filesystem_tool import FileSystemTool


class FakeFileSystemTool(FileSystemTool):
    """FileSystemTool variant that copies files when hardlink is requested."""

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Delegate to the real tool, but replace hardlink with copy."""
        from anime_agent.tools.filesystem_tool import FileSystemToolInput

        fs_input = FileSystemToolInput.model_validate(input_data)
        if fs_input.action == "hardlink":
            if not fs_input.src or not fs_input.dst:
                return ToolOutput(
                    success=False, error="src and dst are required for hardlink action"
                )
            src_path = Path(fs_input.src)
            dst_path = Path(fs_input.dst)
            if not src_path.exists():
                return ToolOutput(success=False, error=f"Source does not exist: {fs_input.src}")
            try:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_path), str(dst_path))
            except OSError as exc:
                return ToolOutput(success=False, error=f"Failed to copy file: {exc}")
            return ToolOutput(success=True, data={"dst": str(dst_path)})

        return await super().invoke(input_data)
