"""poll_download node for Episode Graph."""

from datetime import UTC, datetime, timedelta
from typing import Any

from anime_agent.config import settings
from anime_agent.tools.base import BaseTool
from anime_agent.tools.qb_tool import QBTool, QBToolInput
from anime_agent.utils.logger import logger


class PollDownloadNode:
    """Poll qBittorrent for torrent completion."""

    def __init__(self, qb_tool: BaseTool | None = None):
        self.qb_tool = qb_tool or QBTool()

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Check torrent download progress."""
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
        progress = status.get("progress", 0.0)
        qb_state = status.get("state", "")

        # Check for failed/stalled states
        failed_states = ("error", "missingFiles", "stalledDL")
        if qb_state in failed_states:
            logger.warning(
                "Torrent failed for episode {}: state={}, hash={}",
                state.get("episode_number"),
                qb_state,
                torrent_hash,
            )
            failed_hashes = list(state.get("torrent_failed_hashes", []))
            if torrent_hash not in failed_hashes:
                failed_hashes.append(torrent_hash)
            return {
                "status": "retry_match",
                "torrent_failed_hashes": failed_hashes,
                "matched_torrent": None,
                "torrent_hash": None,
            }

        if progress < 1.0:
            resume_after = (
                datetime.now(UTC) + timedelta(seconds=settings.check_interval_seconds)
            ).isoformat()
            logger.info(
                "Download in progress for episode {}: {:.1f}%",
                state.get("episode_number"),
                progress * 100,
            )
            return {
                "status": "downloading",
                "download_progress": progress,
                "resume_after": resume_after,
            }

        content_path = status.get("content_path") or status.get("save_path")
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
