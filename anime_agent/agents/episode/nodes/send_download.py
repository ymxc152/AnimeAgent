"""send_download node for Episode Graph."""

from typing import Any

from anime_agent.tools.base import BaseTool
from anime_agent.tools.qb_tool import QBTool, QBToolInput
from anime_agent.utils.logger import logger


class SendDownloadNode:
    """Add the matched torrent to qBittorrent."""

    def __init__(self, qb_tool: BaseTool | None = None):
        self.qb_tool = qb_tool or QBTool()

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Send torrent to qBittorrent."""
        logger.info(
            "Sending download for episode {} of subscription {}",
            state.get("episode_number"),
            state.get("subscription_id"),
        )

        matched = state.get("matched_torrent")
        if not matched:
            logger.error("No matched torrent for episode {}", state.get("episode_number"))
            return {
                "status": "failed",
                "errors": ["No matched torrent to download"],
            }

        info_hash = matched.get("info_hash")
        if info_hash and info_hash in state.get("torrent_failed_hashes", []):
            logger.error("Torrent {} already failed for episode {}", info_hash, state.get("episode_number"))
            return {
                "status": "failed",
                "errors": [f"Torrent {info_hash} already failed"],
            }

        link = matched.get("link") or matched.get("magnet_url")
        if not link:
            logger.error("No download link for episode {}", state.get("episode_number"))
            return {
                "status": "failed",
                "errors": ["Matched torrent has no download link"],
            }

        result = await self.qb_tool.invoke(QBToolInput(action="add", torrent_url=link))
        if not result.success:
            logger.error("Failed to add torrent for episode {}: {}", state.get("episode_number"), result.error)
            failed_hashes = list(state.get("torrent_failed_hashes", []))
            if info_hash:
                failed_hashes.append(info_hash)
            return {
                "status": "failed",
                "errors": [f"Failed to add torrent: {result.error}"],
                "torrent_failed_hashes": failed_hashes,
            }

        logger.info(
            "Torrent added for episode {}: hash={}",
            state.get("episode_number"),
            result.data.get("hash", info_hash),
        )
        return {
            "torrent_hash": result.data.get("hash", info_hash),
            "torrent_name": matched.get("title"),
            "status": "downloading",
        }
