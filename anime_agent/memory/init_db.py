"""Database initialization and lightweight SQLite migrations."""

from typing import Any

from sqlalchemy import inspect, text

from anime_agent.memory.database import engine
from anime_agent.memory.models import Base


def _migrate_subscriptions_columns(connection: Any) -> None:
    """Add series_title/season_number/fallback_to_resource_search columns to existing subscriptions tables."""
    inspector = inspect(connection)
    columns = {col["name"] for col in inspector.get_columns("subscriptions")}

    if "series_title" not in columns:
        connection.execute(text("ALTER TABLE subscriptions ADD COLUMN series_title VARCHAR"))
    if "season_number" not in columns:
        connection.execute(
            text("ALTER TABLE subscriptions ADD COLUMN season_number INTEGER DEFAULT 1")
        )
    if "fallback_to_resource_search" not in columns:
        connection.execute(
            text(
                "ALTER TABLE subscriptions ADD COLUMN fallback_to_resource_search BOOLEAN DEFAULT 1"
            )
        )
    if "tmdb_id" not in columns:
        connection.execute(text("ALTER TABLE subscriptions ADD COLUMN tmdb_id INTEGER"))


def _migrate_episodes_columns(connection: Any) -> None:
    """Add torrent_progress column and migrate torrent_hash data."""
    inspector = inspect(connection)
    columns = {col["name"] for col in inspector.get_columns("episodes")}

    if "torrent_progress" not in columns:
        connection.execute(
            text("ALTER TABLE episodes ADD COLUMN torrent_progress FLOAT DEFAULT 0.0")
        )

    # Migrate legacy torrent_info_hash values into torrent_hash if the latter is empty.
    if "torrent_info_hash" in columns:
        connection.execute(
            text(
                "UPDATE episodes SET torrent_hash = torrent_info_hash "
                "WHERE (torrent_hash IS NULL OR torrent_hash = '') "
                "AND (torrent_info_hash IS NOT NULL AND torrent_info_hash != '')"
            )
        )


def _cleanup_stale_error_logs(connection: Any) -> None:
    """Clear error_log for episodes that already reached a successful terminal state."""
    connection.execute(
        text(
            "UPDATE episodes SET error_log = NULL "
            "WHERE status IN ('completed', 'organized', 'organized_with_warnings', 'skipped')"
        )
    )


async def init_database() -> None:
    """Create all tables if they don't exist and apply lightweight migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_subscriptions_columns)
        await conn.run_sync(_migrate_episodes_columns)
        await conn.run_sync(_cleanup_stale_error_logs)
