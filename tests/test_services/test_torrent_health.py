"""Tests for TorrentHealth."""

from datetime import UTC, datetime, timedelta

from anime_agent.services.torrent_health import TorrentHealth


def _status(
    progress: float = 0.5,
    state: str = "downloading",
    download_speed: float = 0.0,
    added_at: datetime | None = None,
    last_speed_at: datetime | None = None,
) -> dict:
    return {
        "progress": progress,
        "state": state,
        "download_speed": download_speed,
        "added_at": added_at or datetime.now(UTC),
        "last_speed_at": last_speed_at or datetime.now(UTC),
    }


def test_health_detects_completed():
    """TorrentHealth should mark uploading/pausedUP with 100% progress as completed."""
    status = _status(progress=1.0, state="uploading")

    result = TorrentHealth().evaluate(status)

    assert result["state"] == "completed"


def test_health_detects_stalled():
    """TorrentHealth should mark torrent as stalled after 1 hour of zero speed."""
    now = datetime.now(UTC)
    status = _status(
        progress=0.5,
        state="stalledDL",
        download_speed=0.0,
        last_speed_at=now - timedelta(hours=2),
    )

    result = TorrentHealth().evaluate(status, now=now)

    assert result["state"] == "stalled"


def test_health_detects_meta_dl_stuck():
    """TorrentHealth should mark metaDL state lasting over 1 hour as metadata failure."""
    now = datetime.now(UTC)
    status = _status(progress=0.0, state="metaDL", added_at=now - timedelta(hours=2))

    result = TorrentHealth().evaluate(status, now=now)

    assert result["state"] == "metadata_failed"


def test_health_detects_slow():
    """TorrentHealth should mark torrent as slow if not complete after 12 hours."""
    now = datetime.now(UTC)
    status = _status(progress=0.5, added_at=now - timedelta(hours=13))

    result = TorrentHealth().evaluate(status, now=now)

    assert result["state"] == "slow"


def test_health_returns_healthy_when_active():
    """TorrentHealth should mark active downloading torrent as healthy."""
    now = datetime.now(UTC)
    status = _status(
        progress=0.5,
        state="downloading",
        download_speed=1024000,
        last_speed_at=now - timedelta(minutes=5),
        added_at=now - timedelta(minutes=10),
    )

    result = TorrentHealth().evaluate(status, now=now)

    assert result["state"] == "healthy"
