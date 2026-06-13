"""Shared test fixtures."""

import os

# Reset external service configuration to predictable defaults for unit tests.
# The real .env may contain production credentials; these values keep mock tests isolated.
# Keep production credentials out of unit tests by resetting service URLs to local defaults.
# TMDB/Emby/qBittorrent credentials are intentionally left as-is from .env; tests that need
# to verify "no credentials" behavior should monkeypatch the settings object directly.
os.environ["EMBY_HOST"] = "http://localhost:8096"
os.environ["QB_HOST"] = "http://localhost:8080"
os.environ["RSS_DEFAULT_URL"] = ""
os.environ["OPENAI_API_KEY"] = ""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from anime_agent.config import settings
from anime_agent.memory.models import Base
from anime_agent.web import app, get_db

# Override .env values with predictable local defaults for unit tests.
settings.emby_host = "http://localhost:8096"
settings.emby_api_key = ""
settings.qb_host = "http://localhost:8080"
settings.qb_username = ""
settings.qb_password = ""
settings.rss_default_url = ""
settings.openai_api_key = ""


@pytest_asyncio.fixture
async def test_engine():
    """Create an in-memory SQLite engine with fresh tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Yield a database session bound to the in-memory engine."""
    session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    """Yield an HTTP client that talks to the FastAPI app with a test DB."""
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
