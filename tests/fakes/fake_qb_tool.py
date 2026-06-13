"""In-memory fake for QBTool used in end-to-end tests."""

from pathlib import Path
from typing import Any

from anime_agent.tools.base import BaseTool, ToolInput, ToolOutput
from anime_agent.tools.qb_tool import QBToolInput


class FakeQBTool(BaseTool):
    """Simulate qBittorrent add/get_status/delete without a real client."""

    name = "qbittorrent"
    description = "Fake qBittorrent tool for testing."

    def __init__(self, complete_after_calls: int = 1, download_root: Path | None = None):
        self.torrents: dict[str, dict[str, Any]] = {}
        self.complete_after_calls = complete_after_calls
        self.poll_counts: dict[str, int] = {}
        self.download_root = download_root

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Handle add/get_status/delete actions."""
        qb_input = QBToolInput.model_validate(input_data)

        if qb_input.action == "add":
            return await self._add(qb_input)
        if qb_input.action == "get_status":
            return await self._get_status(qb_input)
        if qb_input.action == "delete":
            return await self._delete(qb_input)

        return ToolOutput(success=False, error=f"Unknown action: {qb_input.action}")

    async def healthcheck(self) -> ToolOutput:
        """Always healthy in tests."""
        return ToolOutput(success=True, data={"status": "ok", "version": "fake"})

    async def _add(self, input_data: QBToolInput) -> ToolOutput:
        url = input_data.torrent_url or ""
        info_hash = self._extract_hash(url)
        if not info_hash:
            return ToolOutput(success=False, error="Could not extract info hash")

        save_path = input_data.save_path or "/fake/downloads"
        content_path = save_path
        if self.download_root is not None:
            content_path = str(self.download_root / f"{info_hash}.mkv")
            Path(content_path).parent.mkdir(parents=True, exist_ok=True)
            Path(content_path).write_bytes(b"fake video content")

        self.torrents[info_hash] = {
            "hash": info_hash,
            "name": url,
            "progress": 0.0,
            "state": "downloading",
            "dlspeed": 0,
            "size": 0,
            "save_path": save_path,
            "content_path": content_path,
        }
        self.poll_counts[info_hash] = 0
        return ToolOutput(success=True, data={"hash": info_hash})

    async def _get_status(self, input_data: QBToolInput) -> ToolOutput:
        info_hash = (input_data.torrent_hash or "").lower()
        if info_hash not in self.torrents:
            return ToolOutput(success=False, error=f"Torrent {info_hash} not found")

        self.poll_counts[info_hash] += 1
        torrent = self.torrents[info_hash]
        if self.poll_counts[info_hash] >= self.complete_after_calls:
            torrent["progress"] = 1.0
            torrent["state"] = "completed"

        status = {
            "hash": torrent["hash"],
            "name": torrent["name"],
            "progress": torrent["progress"],
            "state": torrent["state"],
            "download_speed": torrent["dlspeed"],
            "size": torrent["size"],
            "save_path": torrent["save_path"],
            "content_path": torrent["content_path"],
        }
        return ToolOutput(success=True, data={"status": status})

    async def _delete(self, input_data: QBToolInput) -> ToolOutput:
        info_hash = (input_data.torrent_hash or "").lower()
        self.torrents.pop(info_hash, None)
        return ToolOutput(success=True, data={"deleted": True})

    @staticmethod
    def _extract_hash(url: str) -> str | None:
        """Extract a 40-character hex or 32-character base32 hash from a magnet URL."""
        import base64
        import re

        match = re.search(r"btih:([a-zA-Z0-9]+)", url, re.IGNORECASE)
        if not match:
            return None
        raw = match.group(1).upper()
        if len(raw) == 40:
            return raw.lower()
        if len(raw) == 32:
            try:
                decoded = base64.b32decode(raw)
                return decoded.hex()
            except ValueError:
                return raw.lower()
        return raw.lower()
