"""Entry point to start the AnimeAgent web panel and scheduler."""

import asyncio

import uvicorn

from anime_agent.agents.episode.runner import EpisodeGraphRunner
from anime_agent.config import settings
from anime_agent.memory.database import SessionLocal
from anime_agent.memory.init_db import init_database
from anime_agent.services.healthcheck import HealthCheck
from anime_agent.services.scheduler import Scheduler
from anime_agent.tools import get_all_tools
from anime_agent.web import app


async def _lifespan() -> None:
    """Initialize the database, start the scheduler, and run the web server."""
    await init_database()

    scheduler = Scheduler(
        session_factory=SessionLocal,
        health_check=HealthCheck(tools=get_all_tools()),
        executor=EpisodeGraphRunner(SessionLocal),
        settings=settings,
    )
    await scheduler.start()

    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    try:
        await server.serve()
    finally:
        await scheduler.stop()


def main() -> None:
    """Run the AnimeAgent application."""
    asyncio.run(_lifespan())


if __name__ == "__main__":
    main()
