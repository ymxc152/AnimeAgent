"""Episode scheduling logic based on airing weekday and timezone."""

from datetime import UTC, datetime, time, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from anime_agent.memory.models import Subscription


class EpisodePlanner:
    """Plan the next check/run time for a subscription or episode."""

    DEFAULT_CHECK_TIME = "00:00"
    DEFAULT_TIMEZONE = "Asia/Tokyo"
    CATCH_UP_INTERVAL_MINUTES = 15

    def plan_next_run(self, subscription: Subscription, now: datetime | None = None) -> datetime:
        """Calculate the next run time for a subscription check."""
        now = now or datetime.now(UTC)
        tz = self._get_timezone(subscription)
        now_in_tz = now.astimezone(tz)

        weekday = cast(int | None, subscription.expected_airing_weekday)
        air_time_str = (
            cast(str | None, subscription.expected_airing_time) or self.DEFAULT_CHECK_TIME
        )

        if weekday is None:
            # No weekday locked: schedule daily at default check time
            air_time = self._parse_time(air_time_str)
            next_run = datetime.combine(now_in_tz.date(), air_time, tzinfo=tz)
            if next_run <= now_in_tz:
                next_run += timedelta(days=1)
            return next_run

        air_time = self._parse_time(air_time_str)
        days_ahead = (weekday - now_in_tz.weekday()) % 7
        next_date = now_in_tz.date() + timedelta(days=days_ahead)
        next_run = datetime.combine(next_date, air_time, tzinfo=tz)

        if next_run <= now_in_tz:
            next_run += timedelta(days=7)

        return next_run

    def stagger_episodes(
        self, subscription: Subscription, count: int, base_time: datetime | None = None
    ) -> list[datetime]:
        """Generate staggered run times for catch-up episodes."""
        base = base_time or datetime.now(UTC)
        return [base + timedelta(minutes=self.CATCH_UP_INTERVAL_MINUTES * i) for i in range(count)]

    def _get_timezone(self, subscription: Subscription) -> ZoneInfo:
        tz_name = cast(str | None, subscription.airing_timezone) or self.DEFAULT_TIMEZONE
        try:
            return ZoneInfo(tz_name)
        except Exception:  # noqa: BLE001
            return ZoneInfo(self.DEFAULT_TIMEZONE)

    def _parse_time(self, time_str: str) -> time:
        """Parse 'HH:MM' into a time object."""
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(time_str, fmt).time()
            except ValueError:
                continue
        return datetime.strptime(self.DEFAULT_CHECK_TIME, "%H:%M").time()
