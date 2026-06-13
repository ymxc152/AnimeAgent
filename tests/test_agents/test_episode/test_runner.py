"""Tests for the Episode Graph runner/executor."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from anime_agent.agents.episode.runner import EpisodeGraphRunner
from anime_agent.agents.episode.state import EpisodeAgentState
from anime_agent.memory.models import Episode, Subscription, TaskSchedule
from anime_agent.memory.store import Store


async def test_runner_loads_state_and_invokes_graph(db_session):
    """Runner should hydrate EpisodeAgentState from DB and invoke the graph."""
    sub = Subscription(
        title_romaji="Sousou no Frieren",
        title_native="葬送のフリーレン",
        title_chinese="葬送的芙莉莲",
        rss_source_id=1,
        status="ongoing",
    )
    store = Store(db_session)
    await store.subscriptions.create(sub)

    ep = Episode(
        subscription_id=sub.id,
        episode_number=1,
        status="pending",
        torrent_candidates=json.dumps([{"title": "test"}]),
    )
    await store.episodes.create(ep)

    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        **EpisodeAgentState(
            goal_id=f"sub_{sub.id}_ep_1",
            subscription_id=sub.id,
            episode_number=1,
            rss_source_id=1,
            title_romaji="Sousou no Frieren",
            title_native="葬送のフリーレン",
            title_chinese="葬送的芙莉莲",
            bangumi_data={},
            anilist_data={},
            tmdb_data=None,
            torrent_candidates=[{"title": "test"}],
            matched_torrent=None,
            torrent_hash=None,
            torrent_name=None,
            torrent_failed_hashes=[],
            download_files=[],
            download_progress=0.0,
            classification=None,
            organized_path=None,
            organized_files=[],
            status="no_match",
            errors=["No candidates"],
            requires_human=False,
            human_input=None,
            low_confidence_count=0,
            resume_after=None,
            resource_searched=False,
        )
    }

    runner = EpisodeGraphRunner(session_factory=MagicMock(), graph=mock_graph)
    runner._session = db_session  # use real session for this test

    final = await runner.run(sub.id, 1, session=db_session)

    mock_graph.ainvoke.assert_awaited_once()
    call_state = mock_graph.ainvoke.await_args.args[0]
    assert call_state["subscription_id"] == sub.id
    assert call_state["episode_number"] == 1
    assert call_state["rss_source_id"] == 1
    assert call_state["torrent_candidates"] == [{"title": "test"}]
    assert final["status"] == "no_match"

    await db_session.refresh(ep)
    assert ep.status == "no_match"
    assert "No candidates" in ep.error_log


async def test_runner_updates_resume_after(db_session):
    """Runner should update TaskSchedule.next_run_at when graph returns resume_after."""
    sub = Subscription(
        title_romaji="Sousou no Frieren",
        status="ongoing",
        expected_airing_weekday=0,
        expected_airing_time="10:00",
        airing_timezone="Asia/Tokyo",
    )
    store = Store(db_session)
    await store.subscriptions.create(sub)

    ep = Episode(subscription_id=sub.id, episode_number=1, status="downloading")
    await store.episodes.create(ep)

    resume_at = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "status": "downloading",
        "resume_after": resume_at.isoformat(),
        "errors": [],
    }

    schedule = TaskSchedule(subscription_id=sub.id, next_run_at=datetime.now(UTC))
    await store.schedules.create(schedule)

    runner = EpisodeGraphRunner(session_factory=MagicMock(), graph=mock_graph)
    await runner.run(sub.id, 1, session=db_session)

    updated = await store.schedules.get_by_subscription(sub.id)
    assert updated.next_run_at == resume_at.replace(tzinfo=None)


async def test_runner_is_callable_as_scheduler_executor(db_session):
    """Runner instance should be usable directly as the Scheduler executor callback."""
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {"status": "completed"}

    sub = Subscription(title_romaji="Sousou no Frieren", status="ongoing")
    store = Store(db_session)
    await store.subscriptions.create(sub)
    await store.episodes.create(Episode(subscription_id=sub.id, episode_number=1, status="pending"))

    class _FakeSessionManager:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return None

    def _fake_factory():
        return _FakeSessionManager()

    runner = EpisodeGraphRunner(session_factory=_fake_factory, graph=mock_graph)

    await runner(sub.id, 1)

    mock_graph.ainvoke.assert_awaited_once()
