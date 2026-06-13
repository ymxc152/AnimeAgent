"""Database initialization and lightweight SQLite migrations."""

from typing import Any

from sqlalchemy import inspect, text

from anime_agent.memory.database import engine
from anime_agent.memory.models import Base


def _migrate_subscriptions_columns(connection: Any) -> None:
    """Add series_title/season_number columns to existing subscriptions tables."""
    inspector = inspect(connection)
    columns = {col["name"] for col in inspector.get_columns("subscriptions")}

    if "series_title" not in columns:
        connection.execute(text("ALTER TABLE subscriptions ADD COLUMN series_title VARCHAR"))
    if "season_number" not in columns:
        connection.execute(text("ALTER TABLE subscriptions ADD COLUMN season_number INTEGER DEFAULT 1"))


async def init_database() -> None:
    """Create all tables if they don't exist and apply lightweight migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_subscriptions_columns)
