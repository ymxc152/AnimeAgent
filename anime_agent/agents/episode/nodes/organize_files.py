"""organize_files node for Episode Graph."""

from pathlib import Path
from typing import Any

from anime_agent.config import settings
from anime_agent.tools.base import BaseTool
from anime_agent.tools.filesystem_tool import FileSystemTool, FileSystemToolInput

_VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm"}


class OrganizeFilesNode:
    """Organize downloaded video files into the media library."""

    def __init__(
        self,
        fs_tool: BaseTool | None = None,
        library_path: str | None = None,
        template: str | None = None,
    ):
        self.fs_tool = fs_tool or FileSystemTool()
        self.library_path = Path(library_path or settings.media_library_path)
        self.template = template or settings.organize_template

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Hardlink downloaded files into the configured library structure."""
        download_files = state.get("download_files", [])
        if not download_files:
            return {
                "status": "failed",
                "errors": ["No downloaded files to organize"],
            }

        title = (
            state.get("title_chinese")
            or state.get("title_romaji")
            or state.get("title_native")
            or "Unknown"
        )
        episode = state.get("episode_number", 0)
        season = state.get("season", 1)

        video_files: list[Path] = []
        for raw_path in download_files:
            listed = await self.fs_tool.invoke(
                FileSystemToolInput(action="list_files", src=raw_path)
            )
            if not listed.success:
                return {
                    "status": "failed",
                    "errors": [f"Failed to list files for {raw_path}: {listed.error}"],
                }
            for file_path in listed.data.get("files", []):
                path = Path(file_path)
                if path.suffix.lower() in _VIDEO_EXTENSIONS:
                    video_files.append(path)

        if not video_files:
            return {
                "status": "failed",
                "errors": ["No video files found in download"],
            }

        organized_paths: list[str] = []
        errors: list[str] = []
        for src_path in video_files:
            dst = self._build_destination(title, season, episode, src_path.suffix)

            created = await self.fs_tool.invoke(
                FileSystemToolInput(action="create_dir", dst=str(dst.parent))
            )
            if not created.success:
                errors.append(f"Failed to create directory {dst.parent}: {created.error}")
                continue

            linked = await self.fs_tool.invoke(
                FileSystemToolInput(action="hardlink", src=str(src_path), dst=str(dst))
            )
            if not linked.success:
                # Hardlinks cannot cross volumes; fall back to a copy so the
                # episode still ends up in the library even when the download
                # folder and media library are on different shares.
                copied = await self.fs_tool.invoke(
                    FileSystemToolInput(action="copy", src=str(src_path), dst=str(dst))
                )
                if not copied.success:
                    errors.append(f"Failed to organize {src_path}: {copied.error}")
                    continue

            organized_paths.append(str(dst))

        if errors and not organized_paths:
            return {"status": "failed", "errors": errors}

        result: dict[str, Any] = {
            "organized_path": str(Path(organized_paths[0]).parent) if organized_paths else None,
            "organized_files": organized_paths,
            "status": "organized" if not errors else "organized_with_warnings",
        }
        if errors:
            result["errors"] = errors
        return result

    def _build_destination(self, title: str, season: int, episode: int, ext: str) -> Path:
        """Build the destination path from the configured template."""
        filename = self.template.format(
            title=title,
            season=season,
            episode=episode,
            ext=ext.lstrip("."),
        )
        return self.library_path / filename
