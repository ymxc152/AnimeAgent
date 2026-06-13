"""Completion detection for subscriptions and episode sets."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from anime_agent.memory.models import Episode, Subscription


@dataclass
class CompletionResult:
    """Result of a completion check."""

    is_completed: bool
    all_episodes_completed: bool
    reason: str


class CompletionChecker:
    """Check whether a subscription has finished airing and all episodes are downloaded."""

    FINISHED_GRACE_DAYS = 14

    def check(
        self,
        subscription: Subscription,
        episodes: list[Episode],
        external_status: str | None = None,
        last_airing_at: datetime | None = None,
    ) -> CompletionResult:
        """Determine if subscription is completed."""
        total = cast(int | None, subscription.total_episodes)
        completed_count = sum(1 for ep in episodes if ep.status == "completed")
        all_completed = bool(total is not None and completed_count >= total > 0)

        # All episodes downloaded -> completed regardless of airing status
        if all_completed:
            return CompletionResult(
                is_completed=True,
                all_episodes_completed=True,
                reason="All episodes downloaded",
            )

        # External status explicit FINISHED but not all episodes downloaded
        if external_status == "FINISHED":
            return CompletionResult(
                is_completed=False,
                all_episodes_completed=False,
                reason="Finished airing but not all episodes downloaded",
            )

        # Infer finished from last airing date + grace period
        if (
            last_airing_at
            and (datetime.now(UTC) - last_airing_at).days > self.FINISHED_GRACE_DAYS
            and total is not None
            and completed_count >= total
        ):
            return CompletionResult(
                is_completed=True,
                all_episodes_completed=True,
                reason="Last airing was >14 days ago and all episodes complete",
            )

        return CompletionResult(
            is_completed=False,
            all_episodes_completed=all_completed,
            reason="Still releasing or episodes incomplete",
        )
