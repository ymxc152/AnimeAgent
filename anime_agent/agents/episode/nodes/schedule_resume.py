"""schedule_resume node for Episode Graph."""

from datetime import UTC, datetime, timedelta
from typing import Any

from anime_agent.config import settings
from anime_agent.utils.logger import logger


class ScheduleResumeNode:
    """Schedule the next resume time for an episode and end the graph."""

    def __init__(self, interval_seconds: int | None = None):
        self.interval_seconds = interval_seconds or settings.check_interval_seconds

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Set resume_after so the external scheduler can re-trigger the graph."""
        resume_after = (datetime.now(UTC) + timedelta(seconds=self.interval_seconds)).isoformat()

        logger.info(
            "Episode {} of subscription {} will resume after {}",
            state.get("episode_number"),
            state.get("subscription_id"),
            resume_after,
        )

        return {"resume_after": resume_after}
