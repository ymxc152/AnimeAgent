"""Tests for QBSyncService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from anime_agent.memory.models import Episode, Subscription
from anime_agent.memory.store import Store
from anime_agent.services.qb_sync_service import QBSyncService
from anime_agent.tools.base import ToolOutput


async def test_sync_updates_downloading_episode(db_session):
    """QBSyncService should update episode fields from a matching qBittorrent torrent."""
    store = Store(db_session)
    sub = Subscription(title_romaji="Test", status="ongoing")
    await store.subscriptions.create(sub)

    ep = Episode(
        subscription_id=sub.id,
        episode_number=1,
        status="downloading",
        content_type="TV",
        torrent_hash="abc123",
    )
    db_session.add(ep)
    await db_session.commit()

    now = datetime.now(UTC)
    qb_tool = MagicMock()
    qb_tool.invoke = AsyncMock(
        return_value=ToolOutput(
            success=True,
            data={
                "torrents": [
                    {
                        "hash": "abc123",
                        "state": "downloading",
                        "download_speed": 1024,
                        "progress": 0.65,
                        "added_at": now,
                        "last_speed_at": now,
                    }
                ]
            },
        )
    )

    service = QBSyncService(db_session, qb_tool=qb_tool)
    summary = await service.sync()

    assert summary["updated"] == 1
    refreshed = await db_session.get(Episode, ep.id)
    assert refreshed.torrent_status == "downloading"
    assert refreshed.torrent_last_speed == 1024
    assert refreshed.torrent_progress == 0.65
    assert refreshed.torrent_added_at == now


async def test_sync_ignores_episode_without_hash(db_session):
    """Episodes without a torrent hash should be skipped."""
    store = Store(db_session)
    sub = Subscription(title_romaji="Test", status="ongoing")
    await store.subscriptions.create(sub)

    ep = Episode(
        subscription_id=sub.id,
        episode_number=1,
        status="downloading",
        content_type="TV",
    )
    db_session.add(ep)
    await db_session.commit()

    qb_tool = MagicMock()
    qb_tool.invoke = AsyncMock(return_value=ToolOutput(success=True, data={"torrents": []}))

    service = QBSyncService(db_session, qb_tool=qb_tool)
    summary = await service.sync()

    assert summary["updated"] == 0


async def test_sync_handles_qb_failure(db_session):
    """A failing qBittorrent list should return an error summary without raising."""
    qb_tool = MagicMock()
    qb_tool.invoke = AsyncMock(return_value=ToolOutput(success=False, error="qb offline"))

    service = QBSyncService(db_session, qb_tool=qb_tool)
    summary = await service.sync()

    assert summary["updated"] == 0
    assert "qb offline" in summary["error"]
