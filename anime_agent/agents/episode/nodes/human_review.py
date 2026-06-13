"""human_review node for Episode Graph."""

from typing import Any

from anime_agent.utils.logger import logger


class HumanReviewNode:
    """Pause the graph and wait for human input on a low-confidence match."""

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Either wait for human input or resume after receiving it."""
        human_input = state.get("human_input")

        if human_input:
            logger.info(
                "Human input received for episode {} of subscription {}: continuing",
                state.get("episode_number"),
                state.get("subscription_id"),
            )
            return {
                "status": "matched",
                "requires_human": False,
            }

        logger.info(
            "Episode {} of subscription {} requires human review",
            state.get("episode_number"),
            state.get("subscription_id"),
        )

        return {
            "status": "human_review",
            "requires_human": True,
        }
