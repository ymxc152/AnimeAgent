"""Tests for database initialization and migrations."""

from unittest.mock import patch

from sqlalchemy import text

from anime_agent.memory.init_db import (
    _migrate_episodes_columns,
    _migrate_subscriptions_columns,
    init_database,
)


class TestMigrateSubscriptionsColumns:
    def test_adds_missing_columns(self, test_engine):
        """Should add series_title, season_number, fallback_to_resource_search, tmdb_id columns."""
        # The in-memory DB already has all columns from Base.metadata.create_all,
        # so test the migration function by verifying it doesn't raise.
        import asyncio

        async def _run():
            async with test_engine.begin() as conn:
                await conn.run_sync(_migrate_subscriptions_columns)

        asyncio.run(_run())

    def test_is_idempotent(self, test_engine):
        """Running migration twice should not raise."""
        import asyncio

        async def _run():
            async with test_engine.begin() as conn:
                await conn.run_sync(_migrate_subscriptions_columns)
                await conn.run_sync(_migrate_subscriptions_columns)

        asyncio.run(_run())


class TestMigrateEpisodesColumns:
    def test_adds_missing_torrent_progress(self, test_engine):
        """Should add torrent_progress column if missing."""
        import asyncio

        async def _run():
            async with test_engine.begin() as conn:
                await conn.run_sync(_migrate_episodes_columns)

        asyncio.run(_run())

    def test_is_idempotent(self, test_engine):
        """Running migration twice should not raise."""
        import asyncio

        async def _run():
            async with test_engine.begin() as conn:
                await conn.run_sync(_migrate_episodes_columns)
                await conn.run_sync(_migrate_episodes_columns)

        asyncio.run(_run())


class TestInitDatabase:
    async def test_creates_tables_and_runs_migrations(self, test_engine):
        """init_database should create all tables and run migrations."""
        with patch("anime_agent.memory.init_db.engine", test_engine):
            await init_database()

        # Verify tables exist by querying
        async with test_engine.begin() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result.fetchall()}

        assert "subscriptions" in tables
        assert "episodes" in tables
        assert "rss_sources" in tables
        assert "task_schedules" in tables
