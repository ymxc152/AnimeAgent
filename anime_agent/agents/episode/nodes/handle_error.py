"""handle_error node for Episode Graph."""

from typing import Any

from anime_agent.utils.logger import logger


class HandleErrorNode:
    """Log and finalize a failed Episode Graph run."""

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Mark the episode as failed and persist the error reason."""
        errors = state.get("errors", [])
        status = state.get("status", "failed")

        if status != "failed":
            status = "failed"

        logger.error(
            "Episode {} of subscription {} failed: {}",
            state.get("episode_number"),
            state.get("subscription_id"),
            errors,
        )

        return {
            "status": status,
            "errors": errors,
        }
