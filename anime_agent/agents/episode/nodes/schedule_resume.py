"""schedule_resume node for Episode Graph."""

from datetime import UTC, datetime, timedelta
from typing import Any

from anime_agent.config import settings
from anime_agent.utils.logger import logger


class ScheduleResumeNode:
    """Schedule the next resume time for an episode and end the graph."""

    def __init__(
        self,
        interval_seconds: int | None = None,
        rss_wait_seconds: int | None = None,
    ):
        self.interval_seconds = interval_seconds or settings.check_interval_seconds
        self.rss_wait_seconds = rss_wait_seconds or settings.rss_wait_interval_seconds

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Set resume_after so the external scheduler can re-trigger the graph.

        PollDownloadNode already computes an adaptive resume_after for active
        downloads; preserve it when present.  For RSS-waiting states use a
        longer interval to avoid hammering RSS feeds.
        """
        prior_status = state.get("status", "")

        # Active downloads already carry an adaptive resume_after from
        # PollDownloadNode; do not overwrite it.
        existing_resume_after = state.get("resume_after")
        if existing_resume_after and prior_status == "downloading":
            logger.info(
                "Preserving adaptive resume_after for episode {} of subscription {}",
                state.get("episode_number"),
                state.get("subscription_id"),
            )
            return {"resume_after": existing_resume_after}

        if prior_status in ("waiting_for_rss", "no_match"):
            interval = self.rss_wait_seconds
        else:
            interval = self.interval_seconds

        resume_after = (datetime.now(UTC) + timedelta(seconds=interval)).isoformat()

        logger.info(
            "Episode {} of subscription {} will resume after {} (status={}, interval={}s)",
            state.get("episode_number"),
            state.get("subscription_id"),
            resume_after,
            prior_status,
            interval,
        )

        return {"resume_after": resume_after}
