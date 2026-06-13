"""poll_download node for Episode Graph."""

from datetime import UTC, datetime, timedelta
from typing import Any

from anime_agent.config import settings
from anime_agent.services.torrent_health import TorrentHealth
from anime_agent.tools.base import BaseTool
from anime_agent.tools.qb_tool import QBTool, QBToolInput
from anime_agent.utils.logger import logger


class PollDownloadNode:
    """Poll qBittorrent for torrent completion and health."""

    # Adaptive resume intervals (seconds) based on health state.
    HEALTHY_INTERVAL_SECONDS = 30 * 60  # 30 min
    METADATA_INTERVAL_SECONDS = 2 * 60  # 2 min
    STALL_INTERVAL_SECONDS = 5 * 60  # 5 min
    DEFAULT_INTERVAL_SECONDS = 10 * 60  # 10 min fallback

    def __init__(self, qb_tool: BaseTool | None = None):
        self.qb_tool = qb_tool or QBTool()
        self.health = TorrentHealth()

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Check torrent download progress and recommend next action."""
        logger.info(
            "Polling download for episode {} of subscription {}",
            state.get("episode_number"),
            state.get("subscription_id"),
        )

        torrent_hash = state.get("torrent_hash")
        if not torrent_hash:
            logger.error("No torrent hash for episode {}", state.get("episode_number"))
            return {
                "status": "failed",
                "errors": ["No torrent hash to poll"],
            }

        result = await self.qb_tool.invoke(
            QBToolInput(action="get_status", torrent_hash=torrent_hash)
        )
        if not result.success:
            logger.error("Failed to poll torrent for episode {}: {}", state.get("episode_number"), result.error)
            return {
                "status": "failed",
                "errors": [f"Failed to poll torrent: {result.error}"],
            }

        status = result.data.get("status", {})
        health = self.health.evaluate(status)
        state_name = health.get("state", "unknown")
        recommend = health.get("recommend", "wait")

        logger.info(
            "Torrent health for episode {}: state={}, recommend={}",
            state.get("episode_number"),
            state_name,
            recommend,
        )

        if recommend == "process":
            content_path = status.get("content_path") or status.get("save_path")
            content_path = self._map_remote_path(content_path)
            download_files = [content_path] if content_path else []
            logger.info(
                "Download complete for episode {}: files={}",
                state.get("episode_number"),
                download_files,
            )
            return {
                "status": "downloaded",
                "download_progress": 1.0,
                "download_files": download_files,
                "torrent_name": status.get("name"),
            }

        if recommend == "switch":
            logger.warning(
                "Torrent unhealthy for episode {} ({}); switching candidate",
                state.get("episode_number"),
                health.get("reason"),
            )
            await self._delete_torrent(torrent_hash)
            failed_hashes = list(state.get("torrent_failed_hashes", []))
            if torrent_hash not in failed_hashes:
                failed_hashes.append(torrent_hash)
            return {
                "status": "retry_match",
                "torrent_failed_hashes": failed_hashes,
                "matched_torrent": None,
                "torrent_hash": None,
            }

        # recommend == "wait": schedule next poll adaptively.
        progress = status.get("progress", 0.0)
        interval = self._resume_interval(state_name)
        resume_after = (datetime.now(UTC) + timedelta(seconds=interval)).isoformat()
        logger.info(
            "Download in progress for episode {}: {:.1f}%, next poll in {}s",
            state.get("episode_number"),
            progress * 100,
            interval,
        )
        return {
            "status": "downloading",
            "download_progress": progress,
            "resume_after": resume_after,
        }

    def _resume_interval(self, state_name: str) -> int:
        """Return the polling interval for a given health state."""
        if state_name == "metadata_downloading":
            return self.METADATA_INTERVAL_SECONDS
        if state_name == "stalled":
            return self.STALL_INTERVAL_SECONDS
        if state_name == "healthy":
            return self.HEALTHY_INTERVAL_SECONDS
        # Slow / unknown: use configured default.
        return settings.check_interval_seconds or self.DEFAULT_INTERVAL_SECONDS

    def _map_remote_path(self, path: str | None) -> str | None:
        """Translate qBittorrent's remote path to a local mounted path.

        Useful when qBittorrent runs on a different machine and its download
        directory is exposed via a network share mounted locally.
        """
        if not path:
            return path
        remote_prefix = settings.qb_path_map_remote
        local_prefix = settings.qb_path_map_local
        if not remote_prefix or not local_prefix:
            return path
        # Normalize separators for comparison.
        norm_path = path.replace("/", "\\")
        norm_remote = remote_prefix.replace("/", "\\")
        if norm_path.startswith(norm_remote):
            return local_prefix + norm_path[len(norm_remote):]
        return path

    async def _delete_torrent(self, torrent_hash: str) -> None:
        """Remove a failed torrent from qBittorrent to avoid clutter."""
        try:
            delete_result = await self.qb_tool.invoke(
                QBToolInput(action="delete", torrent_hash=torrent_hash, delete_files=False)
            )
            if not delete_result.success:
                logger.warning("Failed to delete torrent {}: {}", torrent_hash, delete_result.error)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Exception while deleting torrent {}: {}", torrent_hash, exc)
