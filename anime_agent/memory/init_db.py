"""Database initialization."""

from anime_agent.memory.database import engine
from anime_agent.memory.models import Base


async def init_database() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
