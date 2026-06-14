"""Tests for database engine and session management."""

from sqlalchemy.ext.asyncio import AsyncSession

from anime_agent.memory.database import get_db


class TestGetDb:
    async def test_yields_session(self):
        """get_db should yield an async session."""
        gen = get_db()
        session = await gen.__anext__()
        assert session is not None
        assert isinstance(session, AsyncSession)
        # Clean up the generator
        await gen.aclose()

    async def test_session_can_execute_query(self):
        """get_db session should be able to execute queries."""
        gen = get_db()
        session = await gen.__anext__()
        result = await session.execute(
            __import__("sqlalchemy").text("SELECT 1")
        )
        assert result.scalar() == 1
        await gen.aclose()
