"""Tests for EpisodePlanner."""

from datetime import datetime, timedelta, timezone

from anime_agent.memory.models import Subscription
from anime_agent.services.episode_planner import EpisodePlanner


def test_planner_schedules_next_airing_weekday():
    """Planner should schedule the next run on the expected airing weekday/time."""
    sub = Subscription(
        expected_airing_weekday=2,  # Wednesday
        expected_airing_time="23:00",
        airing_timezone="Asia/Tokyo",
    )
    # Monday 2024-01-01 12:00 JST
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=9)))

    next_run = EpisodePlanner().plan_next_run(sub, now)

    assert next_run.weekday() == 2  # Wednesday
    assert next_run.hour == 23
    assert next_run.minute == 0


def test_planner_skips_to_next_week_when_time_passed():
    """Planner should jump to next week if today's airing time has passed."""
    sub = Subscription(
        expected_airing_weekday=0,  # Monday
        expected_airing_time="10:00",
        airing_timezone="Asia/Tokyo",
    )
    # Monday 2024-01-01 12:00 JST (already past 10:00)
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=9)))

    next_run = EpisodePlanner().plan_next_run(sub, now)

    assert next_run.weekday() == 0
    assert next_run.date() == datetime(2024, 1, 8).date()


def test_planner_defaults_to_daily_when_weekday_unknown():
    """Planner should schedule daily when weekday is not locked."""
    sub = Subscription(airing_timezone="Asia/Tokyo")
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=9)))

    next_run = EpisodePlanner().plan_next_run(sub, now)

    # Default check time 00:00 has passed, so schedule next day
    assert next_run.date() == (now + timedelta(days=1)).date()
    assert next_run.hour == 0


def test_planner_staggers_catch_up_episodes():
    """Planner should stagger multiple catch-up episodes."""
    sub = Subscription(airing_timezone="Asia/Tokyo")
    base_time = datetime(2024, 1, 1, 0, 0, tzinfo=timezone(timedelta(hours=9)))

    runs = EpisodePlanner().stagger_episodes(sub, count=3, base_time=base_time)

    assert len(runs) == 3
    assert runs[0] == base_time
    assert runs[1] == base_time + timedelta(minutes=15)
    assert runs[2] == base_time + timedelta(minutes=30)
