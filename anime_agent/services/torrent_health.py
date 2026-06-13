"""Torrent health monitoring for stall / metadata / slow detection."""

from datetime import UTC, datetime
from typing import Any


class TorrentHealth:
    """Evaluate qBittorrent torrent status and recommend next action."""

    STALL_THRESHOLD_SECONDS = 60 * 60  # 1 hour
    METADATA_THRESHOLD_SECONDS = 60 * 60  # 1 hour
    SLOW_THRESHOLD_SECONDS = 12 * 60 * 60  # 12 hours

    def evaluate(self, status: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        """Return health state and recommendation for a torrent."""
        now = now or datetime.now(UTC)
        progress = status.get("progress", 0.0)
        state = status.get("state", "")
        download_speed = status.get("download_speed", 0.0)
        added_at = status.get("added_at") or now
        last_speed_at = status.get("last_speed_at") or now

        # Completed: progress is 100% and we are not still downloading metadata.
        # qBittorrent may report 100% progress in states like "checkingUP",
        # "checkingDL", or a transient "downloading" during recheck.
        if progress >= 1.0 and state not in ("metaDL", "error", "missingFiles"):
            return {"state": "completed", "reason": "Download finished", "recommend": "process"}

        # Hard failures: error / missing files should switch immediately.
        if state in ("error", "missingFiles"):
            return {
                "state": "failed",
                "reason": f"qBittorrent reports state={state}",
                "recommend": "switch",
            }

        # Metadata stuck
        if state == "metaDL":
            if (now - added_at).total_seconds() > self.METADATA_THRESHOLD_SECONDS:
                return {
                    "state": "metadata_failed",
                    "reason": "Metadata download stuck >1h",
                    "recommend": "switch",
                }
            return {
                "state": "metadata_downloading",
                "reason": "Fetching metadata",
                "recommend": "wait",
            }

        # Stalled (zero speed for threshold)
        if (
            download_speed == 0
            and state in ("stalledDL", "downloading")
            and (now - last_speed_at).total_seconds() > self.STALL_THRESHOLD_SECONDS
        ):
            return {
                "state": "stalled",
                "reason": "No download speed for >1h",
                "recommend": "switch",
            }

        # Slow overall
        if progress < 1.0 and (now - added_at).total_seconds() > self.SLOW_THRESHOLD_SECONDS:
            return {
                "state": "slow",
                "reason": "Download not complete after 12h",
                "recommend": "switch",
            }

        return {"state": "healthy", "reason": "Downloading normally", "recommend": "wait"}
