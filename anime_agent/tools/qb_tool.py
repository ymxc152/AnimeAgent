"""qBittorrent tool for adding, polling, and deleting torrents."""

import asyncio
import re
from datetime import UTC, datetime
from typing import Any, cast

from qbittorrentapi import Client

from anime_agent.config import settings
from anime_agent.tools.base import BaseTool, ToolInput, ToolOutput


class QBToolInput(ToolInput):
    """Input for QBTool."""

    action: str  # add / get_status / delete
    torrent_url: str | None = None
    torrent_hash: str | None = None
    save_path: str | None = None
    delete_files: bool = False


class QBTool(BaseTool):
    """Interface with qBittorrent Web API."""

    name = "qbittorrent"
    description = "Add, poll, and delete torrents in qBittorrent."

    def __init__(self, client: Client | None = None):
        self.client = client

    def _get_client(self) -> Client:
        if self.client is not None:
            return self.client
        kwargs: dict[str, Any] = {"host": settings.qb_host}
        if settings.qb_username:
            kwargs["username"] = settings.qb_username
        if settings.qb_password:
            kwargs["password"] = settings.qb_password
        return Client(**kwargs)

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Execute the requested qBittorrent action."""
        qb_input = cast(QBToolInput, input_data)
        client = self._get_client()

        if qb_input.action == "add":
            return await self._add_torrent(client, qb_input)
        if qb_input.action == "get_status":
            return await self._get_status(client, qb_input)
        if qb_input.action == "delete":
            return await self._delete_torrent(client, qb_input)
        if qb_input.action == "list":
            return await self._list(client)

        return ToolOutput(success=False, error=f"Unknown action: {qb_input.action}")

    async def healthcheck(self) -> ToolOutput:
        """Check qBittorrent connectivity by fetching the app version."""
        client = self._get_client()
        try:
            version: str = await asyncio.to_thread(lambda: client.app.version)
        except Exception as exc:  # noqa: BLE001
            return ToolOutput(success=False, error=f"qBittorrent healthcheck failed: {exc}")
        return ToolOutput(success=True, data={"status": "ok", "version": version})

    async def _add_torrent(self, client: Client, input_data: QBToolInput) -> ToolOutput:
        if not input_data.torrent_url:
            return ToolOutput(success=False, error="torrent_url is required for add action")

        try:
            await asyncio.to_thread(
                client.torrents_add,
                urls=input_data.torrent_url,
                save_path=input_data.save_path or settings.qb_save_path,
                tags="anime-agent",
            )
        except Exception as exc:  # noqa: BLE001
            return ToolOutput(success=False, error=f"Failed to add torrent: {exc}")

        info_hash = _extract_hash_from_url(input_data.torrent_url)
        return ToolOutput(success=True, data={"hash": info_hash})

    async def _get_status(self, client: Client, input_data: QBToolInput) -> ToolOutput:
        if not input_data.torrent_hash:
            return ToolOutput(success=False, error="torrent_hash is required for get_status action")

        qb_hash = input_data.torrent_hash.upper()
        try:
            torrents = await asyncio.to_thread(client.torrents_info, torrent_hashes=qb_hash)
        except Exception as exc:  # noqa: BLE001
            return ToolOutput(success=False, error=f"Failed to get torrent status: {exc}")

        if not torrents:
            return ToolOutput(success=False, error=f"Torrent {input_data.torrent_hash} not found")

        torrent = torrents[0]
        now = datetime.now(UTC)
        added_on = _get_value(torrent, "added_on")
        added_at = _unix_to_utc(added_on) if added_on else now
        dlspeed = _get_value(torrent, "dlspeed") or 0
        last_activity = _get_value(torrent, "last_activity")
        if dlspeed > 0:
            last_speed_at = now
        elif last_activity:
            last_speed_at = _unix_to_utc(last_activity)
        else:
            last_speed_at = added_at

        status = {
            "hash": str(_get_value(torrent, "hash")).lower(),
            "name": _get_value(torrent, "name"),
            "progress": _get_value(torrent, "progress"),
            "state": _get_value(torrent, "state"),
            "download_speed": dlspeed,
            "size": _get_value(torrent, "size"),
            "save_path": _get_value(torrent, "save_path"),
            "content_path": _get_value(torrent, "content_path"),
            "added_at": added_at,
            "last_speed_at": last_speed_at,
        }
        return ToolOutput(success=True, data={"status": status})

    async def _delete_torrent(self, client: Client, input_data: QBToolInput) -> ToolOutput:
        if not input_data.torrent_hash:
            return ToolOutput(success=False, error="torrent_hash is required for delete action")

        qb_hash = input_data.torrent_hash.upper()
        try:
            await asyncio.to_thread(
                client.torrents_delete,
                torrent_hashes=qb_hash,
                delete_files=input_data.delete_files,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolOutput(success=False, error=f"Failed to delete torrent: {exc}")

        return ToolOutput(success=True, data={"deleted": True})

    async def _list(self, client: Client) -> ToolOutput:
        """List all torrents tagged with ``anime-agent`` from qBittorrent."""
        try:
            torrents = await asyncio.to_thread(client.torrents_info, tag="anime-agent")
        except Exception as exc:  # noqa: BLE001
            return ToolOutput(success=False, error=f"Failed to list torrents: {exc}")

        now = datetime.now(UTC)
        statuses = []
        for torrent in torrents:
            added_on = _get_value(torrent, "added_on")
            added_at = _unix_to_utc(added_on) if added_on else now
            dlspeed = _get_value(torrent, "dlspeed") or 0
            last_activity = _get_value(torrent, "last_activity")
            if dlspeed > 0:
                last_speed_at = now
            elif last_activity:
                last_speed_at = _unix_to_utc(last_activity)
            else:
                last_speed_at = added_at

            statuses.append(
                {
                    "hash": str(_get_value(torrent, "hash")).lower(),
                    "name": _get_value(torrent, "name"),
                    "progress": _get_value(torrent, "progress"),
                    "state": _get_value(torrent, "state"),
                    "download_speed": dlspeed,
                    "size": _get_value(torrent, "size"),
                    "save_path": _get_value(torrent, "save_path"),
                    "content_path": _get_value(torrent, "content_path"),
                    "added_at": added_at,
                    "last_speed_at": last_speed_at,
                }
            )
        return ToolOutput(success=True, data={"torrents": statuses})


def _get_value(obj: Any, key: str) -> Any:
    """Get a value from a dict or attribute-access object."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _unix_to_utc(timestamp: int | float) -> datetime:
    """Convert a Unix timestamp to a timezone-aware UTC datetime."""
    return datetime.fromtimestamp(float(timestamp), tz=UTC)


def _extract_hash_from_url(url: str) -> str | None:
    """Extract a normalized hex info hash from a magnet or torrent URL."""
    magnet_match = re.search(r"btih:([a-zA-Z0-9]+)", url)
    if not magnet_match:
        return None
    raw = magnet_match.group(1).upper()
    if len(raw) == 40:
        return raw.lower()
    if len(raw) == 32:
        try:
            import base64

            return base64.b32decode(raw).hex()
        except ValueError:
            return raw.lower()
    return raw.lower()
