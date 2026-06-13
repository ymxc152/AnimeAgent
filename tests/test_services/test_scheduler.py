"""Tests for the APScheduler-based task scheduler."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from anime_agent.memory.models import Episode, Subscription, TaskSchedule
from anime_agent.memory.store import Store
from anime_agent.services.episode_planner import EpisodePlanner
from anime_agent.services.healthcheck import HealthCheck
from anime_agent.services.scheduler import PreFlightHealthCheckError, Scheduler
from anime_agent.tools.base import BaseTool, ToolOutput


class _HealthyTool(BaseTool):
    name = "healthy"

    async def invoke(self, input_data):
        return ToolOutput(success=True)

    async def healthcheck(self):
        return ToolOutput(success=True, data={"status": "ok"})


class _SickTool(BaseTool):
    name = "sick"

    async def invoke(self, input_data):
        return ToolOutput(success=True)

    async def healthcheck(self):
        return ToolOutput(success=False, error="sick")


def _make_scheduler(
    db_session,
    healthy: bool = True,
    executor: AsyncMock | None = None,
    check_interval: int = 60,
) -> Scheduler:
    health_check = HealthCheck(
        tools=[_HealthyTool()],
        critical_tools=["healthy"] if healthy else [],
    )
    if not healthy:
        health_check = HealthCheck(
            tools=[_SickTool()],
            critical_tools=["sick"],
        )

    return Scheduler(
        session_factory=MagicMock(return_value=MagicMock()),
        health_check=health_check,
        planner=EpisodePlanner(),
        executor=executor or AsyncMock(),
        settings=MagicMock(check_interval_seconds=check_interval, discovery_cron="0 0 * * 1"),
    )


async def test_bootstrap_creates_schedule_for_active_subscription(db_session):
    """Scheduler should create a TaskSchedule for every active subscription."""
    sub = Subscription(
        title_romaji="Sousou no Frieren",
        expected_airing_weekday=0,
        expected_airing_time="10:00",
        airing_timezone="Asia/Tokyo",
        status="ongoing",
    )
    store = Store(db_session)
    await store.subscriptions.create(sub)

    scheduler = Scheduler(
        session_factory=MagicMock(),
        health_check=HealthCheck(tools=[]),
        planner=EpisodePlanner(),
    )
    # Manually wire the session so we do not need a factory for this test.
    scheduler._session = db_session  # type: ignore[attr-defined]

    await scheduler.bootstrap_schedules(session=db_session)

    schedule = await store.schedules.get_by_subscription(sub.id)
    assert schedule is not None
    assert schedule.next_run_at is not None
    assert schedule.is_active is True


async def test_bootstrap_skips_existing_schedules(db_session):
    """Scheduler should not overwrite existing TaskSchedule rows."""
    sub = Subscription(
        title_romaji="Sousou no Frieren",
        expected_airing_weekday=0,
        expected_airing_time="10:00",
        airing_timezone="Asia/Tokyo",
        status="ongoing",
    )
    store = Store(db_session)
    await store.subscriptions.create(sub)

    existing = TaskSchedule(
        subscription_id=sub.id,
        next_run_at=datetime(2030, 1, 1),
    )
    await store.schedules.create(existing)

    scheduler = Scheduler(
        session_factory=MagicMock(),
        health_check=HealthCheck(tools=[]),
        planner=EpisodePlanner(),
    )
    await scheduler.bootstrap_schedules(session=db_session)

    schedule = await store.schedules.get_by_subscription(sub.id)
    assert schedule.next_run_at == datetime(2030, 1, 1)


async def test_tick_executes_pending_episodes_for_due_schedules(db_session):
    """Tick should invoke the executor for each pending episode of a due subscription."""
    sub = Subscription(
        title_romaji="Sousou no Frieren",
        expected_airing_weekday=0,
        expected_airing_time="10:00",
        airing_timezone="Asia/Tokyo",
        status="ongoing",
    )
    store = Store(db_session)
    await store.subscriptions.create(sub)

    ep1 = Episode(subscription_id=sub.id, episode_number=1, status="pending")
    ep2 = Episode(subscription_id=sub.id, episode_number=2, status="pending")
    await store.episodes.create(ep1)
    await store.episodes.create(ep2)

    schedule = TaskSchedule(
        subscription_id=sub.id,
        next_run_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    await store.schedules.create(schedule)

    executor = AsyncMock()
    scheduler = Scheduler(
        session_factory=MagicMock(),
        health_check=HealthCheck(tools=[]),
        planner=EpisodePlanner(),
        executor=executor,
    )

    await scheduler.tick(session=db_session)

    executor.assert_awaited()
    calls = {call.args for call in executor.await_args_list}
    assert (sub.id, 1) in calls
    assert (sub.id, 2) in calls


async def test_tick_reschedules_subscription_after_execution(db_session):
    """Tick should update next_run_at after processing a due subscription."""
    sub = Subscription(
        title_romaji="Sousou no Frieren",
        expected_airing_weekday=0,
        expected_airing_time="10:00",
        airing_timezone="Asia/Tokyo",
        status="ongoing",
    )
    store = Store(db_session)
    await store.subscriptions.create(sub)

    schedule = TaskSchedule(
        subscription_id=sub.id,
        next_run_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    await store.schedules.create(schedule)

    scheduler = Scheduler(
        session_factory=MagicMock(),
        health_check=HealthCheck(tools=[]),
        planner=EpisodePlanner(),
        executor=AsyncMock(),
    )

    await scheduler.tick(session=db_session)

    updated = await store.schedules.get_by_subscription(sub.id)
    assert updated.last_run_at is not None
    assert updated.next_run_at > datetime.now(UTC)


async def test_start_blocks_when_preflight_health_check_fails():
    """start() should raise when the pre-flight health check is unhealthy."""
    scheduler = _make_scheduler(MagicMock(), healthy=False)

    with pytest.raises(PreFlightHealthCheckError):
        await scheduler.start()


async def test_tick_uses_resume_after_when_executor_returns_it(db_session):
    """Tick should set next_run_at to the earliest resume_after returned by the executor."""
    sub = Subscription(
        title_romaji="Sousou no Frieren",
        expected_airing_weekday=0,
        expected_airing_time="10:00",
        airing_timezone="Asia/Tokyo",
        status="ongoing",
    )
    store = Store(db_session)
    await store.subscriptions.create(sub)

    ep = Episode(subscription_id=sub.id, episode_number=1, status="pending")
    await store.episodes.create(ep)

    schedule = TaskSchedule(
        subscription_id=sub.id,
        next_run_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    await store.schedules.create(schedule)

    resume_at = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)
    executor = AsyncMock(return_value={"resume_after": resume_at.isoformat()})
    scheduler = Scheduler(
        session_factory=MagicMock(),
        health_check=HealthCheck(tools=[]),
        planner=EpisodePlanner(),
        executor=executor,
    )

    await scheduler.tick(session=db_session)

    updated = await store.schedules.get_by_subscription(sub.id)
    assert updated.next_run_at == resume_at.replace(tzinfo=None)


async def test_start_passes_preflight_and_registers_jobs():
    """start() should pass pre-flight and register tick + discovery jobs."""
    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()

    scheduler = _make_scheduler(MagicMock(), healthy=True)
    scheduler._scheduler = mock_scheduler  # type: ignore[attr-defined]
    scheduler.bootstrap_schedules = AsyncMock()

    await scheduler.start()

    scheduler.bootstrap_schedules.assert_awaited_once()
    assert mock_scheduler.add_job.call_count == 2
    mock_scheduler.start.assert_called_once()
