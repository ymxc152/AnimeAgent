"""organize_files node — LLM-driven agent for file organization."""

import re
from pathlib import Path
from typing import Any

from anime_agent.agents.episode.agent_prompts import (
    ORGANIZE_FILES_ACTIONS,
    ORGANIZE_FILES_SYSTEM,
)
from anime_agent.agents.episode.base_agent import BaseAgentNode
from anime_agent.config import settings
from anime_agent.tools.base import BaseTool
from anime_agent.tools.filesystem_tool import FileSystemTool, FileSystemToolInput

_VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm"}

_SEASON_SUFFIX_PATTERNS = [
    r"\s*第\s*[一二三四五六七八九十\d]+\s*季\s*$",
    r"\s*第\s*[一二三四五六七八九十\d]+\s*期\s*$",
    r"\s+season\s*\d+\s*$",
    r"\s+\d+(?:st|nd|rd|th)\s+season\s*$",
    r"\s+(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+season\s*$",
    r"\s+s\d+\s*$",
    r"\s+\d+\s*期\s*$",
]


class OrganizeFilesNode(BaseAgentNode):
    """LLM-driven file organization agent.

    Instead of just trying hardlink then copy, the agent can use Bash to
    diagnose path issues, find real file locations, and handle edge cases.
    """

    NODE_NAME = "organize_files"
    SYSTEM_PROMPT = ORGANIZE_FILES_SYSTEM
    ACTIONS = ORGANIZE_FILES_ACTIONS
    MAX_LLM_CALLS = 3
    TERMINAL_ACTIONS = {"organize", "abort"}

    def __init__(
        self,
        fs_tool: BaseTool | None = None,
        library_path: str | None = None,
        template: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.fs_tool = fs_tool or FileSystemTool()
        self.library_path = Path(library_path or settings.media_library_path)
        self.template = template or settings.organize_template

    def _build_prompt(self, context: dict[str, Any], state: dict[str, Any]) -> str:
        download_files = state.get("download_files", [])
        title = (
            state.get("title_chinese")
            or state.get("title_romaji")
            or state.get("title_native")
            or "Unknown"
        )
        series_title = state.get("series_title") or self._derive_series_title(title)
        episode = state.get("episode_number", 0)
        season = state.get("season", 1)

        # Check what exists
        path_status = []
        for p in download_files:
            exists = Path(p).exists() if p else False
            is_dir = Path(p).is_dir() if p else False
            path_status.append(f"  {'✅' if exists else '❌'} {p} (exists={exists}, dir={is_dir})")

        dst = self._build_destination(series_title, season, episode, ".mp4")
        dst_exists = dst.parent.exists()

        history = context.get("history", [])
        history_text = ""
        if history:
            history_text = "\n之前的操作：\n" + "\n".join(
                f"- {h['action']}: {h['result'][:150]}" for h in history
            )

        return (
            f"目标：整理第 {season} 季第 {episode} 集\n"
            f"系列标题：{series_title}\n"
            f"源文件路径：\n" + "\n".join(path_status) + f"\n"
            f"目标目录：{dst.parent} (exists={dst_exists})\n"
            f"目标文件名：{dst.name}\n"
            f"{history_text}\n\n"
            f"请决定如何整理。"
        )

    async def _act(self, action: Any, state: dict[str, Any]) -> dict[str, Any]:
        if action.type == "find_file":
            # Execute bash command to find the real file
            command = action.params.get("command", "")
            if command:
                result = await self.bash_tool.invoke(
                    {"command": command}  # BashToolInput
                )
                return {
                    "success": result.success,
                    "output": result.data.get("stdout", "")[:2000] if result.success else result.error,
                }
            return {"success": False, "output": "No command provided"}

        if action.type == "organize":
            # Execute the file organization directly
            return await self._execute_organize(state)

        return await super()._act(action, state)

    async def _execute_organize(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the actual file organization (hardlink/copy)."""
        download_files = state.get("download_files", [])
        title = (
            state.get("title_chinese")
            or state.get("title_romaji")
            or state.get("title_native")
            or "Unknown"
        )
        series_title = state.get("series_title") or self._derive_series_title(title)
        episode = state.get("episode_number", 0)
        season = state.get("season", 1)

        video_files: list[Path] = []
        for raw_path in download_files:
            listed = await self.fs_tool.invoke(
                FileSystemToolInput(action="list_files", src=raw_path)
            )
            if not listed.success:
                continue
            for file_path in listed.data.get("files", []):
                path = Path(file_path)
                if path.suffix.lower() in _VIDEO_EXTENSIONS:
                    video_files.append(path)

        if not video_files:
            return {"success": False, "output": "No video files found"}

        organized_paths: list[str] = []
        errors: list[str] = []
        for src_path in video_files:
            dst = self._build_destination(series_title, season, episode, src_path.suffix)

            created = await self.fs_tool.invoke(
                FileSystemToolInput(action="create_dir", dst=str(dst.parent))
            )
            if not created.success:
                errors.append(f"Failed to create dir: {created.error}")
                continue

            linked = await self.fs_tool.invoke(
                FileSystemToolInput(action="hardlink", src=str(src_path), dst=str(dst))
            )
            if not linked.success:
                copied = await self.fs_tool.invoke(
                    FileSystemToolInput(action="copy", src=str(src_path), dst=str(dst))
                )
                if not copied.success:
                    errors.append(f"Failed to organize {src_path}: {copied.error}")
                    continue

            organized_paths.append(str(dst))

        if errors and not organized_paths:
            return {"success": False, "output": "; ".join(errors)}

        return {
            "success": True,
            "output": f"Organized {len(organized_paths)} files",
            "organized_paths": organized_paths,
            "errors": errors,
        }

    def _build_result(self, action: Any, result: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        if action.type == "organize" and result.get("success"):
            organized_paths = result.get("organized_paths", [])
            errors = result.get("errors", [])
            return {
                "organized_path": str(Path(organized_paths[0]).parent) if organized_paths else None,
                "organized_files": organized_paths,
                "status": "organized" if not errors else "organized_with_warnings",
                "errors": errors,
            }
        # abort or organize failed
        return {
            "status": "failed",
            "errors": [f"Organize agent: {result.get('output', 'Unknown error')}"],
        }

    def _build_destination(self, series_title: str, season: int, episode: int, ext: str) -> Path:
        filename = self.template.format(
            title=series_title,
            series_title=series_title,
            season=season,
            episode=episode,
            ext=ext.lstrip("."),
        )
        return self.library_path / filename

    @staticmethod
    def _derive_series_title(title: str) -> str:
        series_title = title
        for pattern in _SEASON_SUFFIX_PATTERNS:
            series_title = re.sub(pattern, "", series_title, flags=re.IGNORECASE)
        return series_title.strip() or title.strip()
