"""Synchronize active qBittorrent torrent progress into Episode records."""

from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from anime_agent.memory.store import Store
from anime_agent.tools.qb_tool import QBTool, QBToolInput


class QBSyncService:
    """Poll qBittorrent and update Episode download progress fields.

    The service matches qBittorrent torrents against ``Episode.torrent_hash``
    and updates status/speed/timestamps.
    Only episodes that are currently downloading or have an active torrent
    are touched; terminal states are left unchanged.
    """

    def __init__(self, session: AsyncSession, qb_tool: QBTool | None = None):
        self.session = session
        self.store = Store(session)
        self.qb_tool = qb_tool or QBTool()

    async def sync(self) -> dict[str, Any]:
        """Sync qBittorrent state to episodes and return a summary."""
        result = await self.qb_tool.invoke(QBToolInput(action="list"))
        if not result.success:
            logger.warning("qBittorrent list failed: {}", result.error)
            return {"updated": 0, "error": result.error}

        torrents = result.data.get("torrents", [])
        if not torrents:
            return {"updated": 0}

        statuses = ["downloading", "matched", "downloaded", "organized", "organizing"]
        episodes = await self.store.episodes.list_by_statuses(statuses)

        hash_to_status: dict[str, dict[str, Any]] = {}
        for torrent in torrents:
            h = str(torrent.get("hash", "")).lower()
            if h:
                hash_to_status[h] = torrent

        updated = 0
        for episode in episodes:
            ep_hash = (episode.torrent_hash or "").lower()
            if not ep_hash:
                continue
            status = hash_to_status.get(ep_hash)
            if status is None:
                continue

            episode.torrent_status = str(status.get("state", ""))  # type: ignore[assignment]
            episode.torrent_last_speed = float(status.get("download_speed", 0))  # type: ignore[assignment]
            episode.torrent_progress = float(status.get("progress", 0.0))  # type: ignore[assignment]
            episode.torrent_added_at = status.get("added_at")  # type: ignore[assignment]
            episode.torrent_checked_at = status.get("last_speed_at")  # type: ignore[assignment]
            if episode.status == "matched":
                episode.status = "downloading"  # type: ignore[assignment]
            updated += 1

        if updated:
            await self.session.commit()

        return {"updated": updated, "total_torrents": len(torrents)}
