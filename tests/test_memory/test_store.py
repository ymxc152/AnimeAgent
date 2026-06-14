"""Tests for the data access layer (Store and sub-stores)."""

from datetime import datetime, timedelta

import pytest

from anime_agent.memory.models import (
    AutoSubscribeRule,
    Episode,
    RSSSource,
    Subscription,
    TaskSchedule,
    UserRequest,
)
from anime_agent.memory.store import (
    AutoSubscribeRuleStore,
    EpisodeStore,
    ErrorLogStore,
    RSSSourceStore,
    Store,
    SubscriptionStore,
    TaskScheduleStore,
    UserRequestStore,
)

# ── Helpers ─────────────────────────────────────────────────────────────


def _make_subscription(**overrides) -> Subscription:
    defaults = {
        "bangumi_id": 1001,
        "title_romaji": "Sousou no Frieren",
        "title_native": "葬送のフリーレン",
        "title_chinese": "葬送的芙莉莲",
        "status": "ongoing",
        "auto_download_enabled": True,
    }
    defaults.update(overrides)
    return Subscription(**defaults)


def _make_episode(subscription_id: int, episode_number: int = 1, **overrides) -> Episode:
    defaults = {
        "subscription_id": subscription_id,
        "episode_number": episode_number,
        "title": f"Episode {episode_number}",
        "status": "pending",
    }
    defaults.update(overrides)
    return Episode(**defaults)


def _make_rss_source(**overrides) -> RSSSource:
    defaults = {"name": "TestRSS", "url": "https://example.com/rss", "is_active": True}
    defaults.update(overrides)
    return RSSSource(**defaults)


def _make_task_schedule(subscription_id: int, **overrides) -> TaskSchedule:
    defaults = {
        "subscription_id": subscription_id,
        "next_run_at": datetime.utcnow() + timedelta(hours=1),
        "is_active": True,
    }
    defaults.update(overrides)
    return TaskSchedule(**defaults)


def _make_user_request(**overrides) -> UserRequest:
    defaults = {"request_type": "subscribe", "raw_input": "订阅葬送的芙莉莲"}
    defaults.update(overrides)
    return UserRequest(**defaults)


def _make_auto_subscribe_rule(**overrides) -> AutoSubscribeRule:
    defaults = {"name": "TestRule", "enabled": True}
    defaults.update(overrides)
    return AutoSubscribeRule(**defaults)


# ── SubscriptionStore ───────────────────────────────────────────────────


class TestSubscriptionStore:
    async def test_create_and_get_by_id(self, db_session):
        store = SubscriptionStore(db_session)
        sub = _make_subscription()
        created = await store.create(sub)

        assert created.id is not None
        fetched = await store.get_by_id(created.id)
        assert fetched is not None
        assert fetched.title_romaji == "Sousou no Frieren"

    async def test_get_by_bangumi_id(self, db_session):
        store = SubscriptionStore(db_session)
        await store.create(_make_subscription(bangumi_id=2002))

        found = await store.get_by_bangumi_id(2002)
        assert found is not None
        assert found.bangumi_id == 2002

        missing = await store.get_by_bangumi_id(9999)
        assert missing is None

    async def test_get_by_anilist_id(self, db_session):
        store = SubscriptionStore(db_session)
        await store.create(_make_subscription(bangumi_id=3001, anilist_id=3001))

        found = await store.get_by_anilist_id(3001)
        assert found is not None
        assert found.anilist_id == 3001

        missing = await store.get_by_anilist_id(9999)
        assert missing is None

    async def test_list_active(self, db_session):
        store = SubscriptionStore(db_session)
        await store.create(_make_subscription(bangumi_id=101, status="ongoing"))
        await store.create(_make_subscription(bangumi_id=102, status="completed"))
        await store.create(_make_subscription(bangumi_id=103, status="ongoing"))

        active = await store.list_active()
        assert len(active) == 2
        assert all(s.status == "ongoing" for s in active)

    async def test_list_auto_download_enabled(self, db_session):
        store = SubscriptionStore(db_session)
        await store.create(_make_subscription(bangumi_id=201, auto_download_enabled=True))
        await store.create(_make_subscription(bangumi_id=202, auto_download_enabled=False))
        await store.create(_make_subscription(bangumi_id=203, status="completed", auto_download_enabled=True))

        enabled = await store.list_auto_download_enabled()
        assert len(enabled) == 1
        assert enabled[0].bangumi_id == 201

    async def test_update(self, db_session):
        store = SubscriptionStore(db_session)
        sub = await store.create(_make_subscription())
        sub.title_chinese = "修改后的标题"
        updated = await store.update(sub)
        assert updated.title_chinese == "修改后的标题"

    async def test_toggle_auto_download(self, db_session):
        store = SubscriptionStore(db_session)
        sub = await store.create(_make_subscription())

        result = await store.toggle_auto_download(sub.id, False)
        assert result is True

        fetched = await store.get_by_id(sub.id)
        assert fetched.auto_download_enabled is False

        # Toggle non-existent subscription
        result = await store.toggle_auto_download(9999, True)
        assert result is False


# ── EpisodeStore ────────────────────────────────────────────────────────


class TestEpisodeStore:
    async def test_create_and_get_by_subscription_and_number(self, db_session):
        # Need a subscription first due to FK
        sub_store = SubscriptionStore(db_session)
        sub = await sub_store.create(_make_subscription())

        ep_store = EpisodeStore(db_session)
        ep = await ep_store.create(_make_episode(sub.id, 1))

        assert ep.id is not None
        fetched = await ep_store.get_by_subscription_and_number(sub.id, 1)
        assert fetched is not None
        assert fetched.episode_number == 1

    async def test_get_by_subscription_and_number_not_found(self, db_session):
        ep_store = EpisodeStore(db_session)
        missing = await ep_store.get_by_subscription_and_number(9999, 1)
        assert missing is None

    async def test_list_by_subscription(self, db_session):
        sub_store = SubscriptionStore(db_session)
        sub = await sub_store.create(_make_subscription())

        ep_store = EpisodeStore(db_session)
        await ep_store.create(_make_episode(sub.id, 3))
        await ep_store.create(_make_episode(sub.id, 1))
        await ep_store.create(_make_episode(sub.id, 2))

        episodes = await ep_store.list_by_subscription(sub.id)
        assert len(episodes) == 3
        assert [e.episode_number for e in episodes] == [1, 2, 3]

    async def test_list_pending(self, db_session):
        sub_store = SubscriptionStore(db_session)
        sub = await sub_store.create(_make_subscription())

        ep_store = EpisodeStore(db_session)
        await ep_store.create(_make_episode(sub.id, 1, status="pending"))
        await ep_store.create(_make_episode(sub.id, 2, status="completed"))
        await ep_store.create(_make_episode(sub.id, 3, status="pending"))

        pending = await ep_store.list_pending()
        assert len(pending) == 2

    async def test_list_by_statuses(self, db_session):
        sub_store = SubscriptionStore(db_session)
        sub = await sub_store.create(_make_subscription())

        ep_store = EpisodeStore(db_session)
        await ep_store.create(_make_episode(sub.id, 1, status="pending"))
        await ep_store.create(_make_episode(sub.id, 2, status="downloading"))
        await ep_store.create(_make_episode(sub.id, 3, status="completed"))
        await ep_store.create(_make_episode(sub.id, 4, status="failed"))

        result = await ep_store.list_by_statuses(["pending", "downloading"])
        assert len(result) == 2

    async def test_update(self, db_session):
        sub_store = SubscriptionStore(db_session)
        sub = await sub_store.create(_make_subscription())

        ep_store = EpisodeStore(db_session)
        ep = await ep_store.create(_make_episode(sub.id, 1))
        ep.status = "downloading"
        updated = await ep_store.update(ep)
        assert updated.status == "downloading"

    async def test_get_by_torrent_hash(self, db_session):
        sub_store = SubscriptionStore(db_session)
        sub = await sub_store.create(_make_subscription())

        ep_store = EpisodeStore(db_session)
        ep = await ep_store.create(
            _make_episode(sub.id, 1, torrent_hash="deadbeef")
        )

        found = await ep_store.get_by_torrent_hash("deadbeef")
        assert found is not None
        assert found.id == ep.id

        missing = await ep_store.get_by_torrent_hash("nope")
        assert missing is None

    async def test_unique_constraint_on_subscription_episode(self, db_session):
        sub_store = SubscriptionStore(db_session)
        sub = await sub_store.create(_make_subscription())

        ep_store = EpisodeStore(db_session)
        await ep_store.create(_make_episode(sub.id, 1))

        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            await ep_store.create(_make_episode(sub.id, 1))


# ── TaskScheduleStore ───────────────────────────────────────────────────


class TestTaskScheduleStore:
    async def test_create_and_get_by_subscription(self, db_session):
        sub_store = SubscriptionStore(db_session)
        sub = await sub_store.create(_make_subscription())

        sched_store = TaskScheduleStore(db_session)
        schedule = await sched_store.create(_make_task_schedule(sub.id))

        assert schedule.id is not None
        fetched = await sched_store.get_by_subscription(sub.id)
        assert fetched is not None
        assert fetched.subscription_id == sub.id

    async def test_list_due(self, db_session):
        sub_store = SubscriptionStore(db_session)
        sub1 = await sub_store.create(_make_subscription(bangumi_id=101))
        sub2 = await sub_store.create(_make_subscription(bangumi_id=102))
        sub3 = await sub_store.create(_make_subscription(bangumi_id=103))

        sched_store = TaskScheduleStore(db_session)
        now = datetime.utcnow()

        # Due: next_run_at in the past
        await sched_store.create(_make_task_schedule(sub1.id, next_run_at=now - timedelta(hours=1)))
        # Not due: next_run_at in the future
        await sched_store.create(_make_task_schedule(sub2.id, next_run_at=now + timedelta(hours=1)))
        # Not due: inactive
        await sched_store.create(_make_task_schedule(sub3.id, next_run_at=now - timedelta(hours=1), is_active=False))

        due = await sched_store.list_due(now)
        assert len(due) == 1
        assert due[0].subscription_id == sub1.id

    async def test_update_next_run(self, db_session):
        sub_store = SubscriptionStore(db_session)
        sub = await sub_store.create(_make_subscription())

        sched_store = TaskScheduleStore(db_session)
        schedule = await sched_store.create(_make_task_schedule(sub.id))

        new_time = datetime.utcnow() + timedelta(days=1)
        await sched_store.update_next_run(schedule.id, new_time)

        # Refresh and verify
        await db_session.refresh(schedule)
        assert schedule.next_run_at is not None


# ── UserRequestStore ────────────────────────────────────────────────────


class TestUserRequestStore:
    async def test_create_and_get_by_id(self, db_session):
        store = UserRequestStore(db_session)
        req = await store.create(_make_user_request())

        assert req.id is not None
        fetched = await store.get_by_id(req.id)
        assert fetched is not None
        assert fetched.raw_input == "订阅葬送的芙莉莲"

    async def test_get_by_id_not_found(self, db_session):
        store = UserRequestStore(db_session)
        missing = await store.get_by_id(9999)
        assert missing is None

    async def test_update(self, db_session):
        store = UserRequestStore(db_session)
        req = await store.create(_make_user_request())
        req.status = "completed"
        updated = await store.update(req)
        assert updated.status == "completed"


# ── RSSSourceStore ──────────────────────────────────────────────────────


class TestRSSSourceStore:
    async def test_create_and_get_by_id(self, db_session):
        store = RSSSourceStore(db_session)
        source = await store.create(_make_rss_source())

        assert source.id is not None
        fetched = await store.get_by_id(source.id)
        assert fetched is not None
        assert fetched.name == "TestRSS"

    async def test_list_all(self, db_session):
        store = RSSSourceStore(db_session)
        await store.create(_make_rss_source(name="B"))
        await store.create(_make_rss_source(name="A"))
        await store.create(_make_rss_source(name="C"))

        all_sources = await store.list_all()
        assert len(all_sources) == 3
        assert [s.name for s in all_sources] == ["A", "B", "C"]

    async def test_list_active(self, db_session):
        store = RSSSourceStore(db_session)
        await store.create(_make_rss_source(name="Active1", is_active=True))
        await store.create(_make_rss_source(name="Inactive", is_active=False))
        await store.create(_make_rss_source(name="Active2", is_active=True))

        active = await store.list_active()
        assert len(active) == 2
        assert all(s.is_active for s in active)

    async def test_update(self, db_session):
        store = RSSSourceStore(db_session)
        source = await store.create(_make_rss_source())
        source.name = "Updated"
        updated = await store.update(source)
        assert updated.name == "Updated"

    async def test_delete(self, db_session):
        store = RSSSourceStore(db_session)
        source = await store.create(_make_rss_source())
        source_id = source.id

        await store.delete(source)
        assert await store.get_by_id(source_id) is None


# ── AutoSubscribeRuleStore ──────────────────────────────────────────────


class TestAutoSubscribeRuleStore:
    async def test_create_and_get_by_id(self, db_session):
        store = AutoSubscribeRuleStore(db_session)
        rule = await store.create(_make_auto_subscribe_rule())

        assert rule.id is not None
        fetched = await store.get_by_id(rule.id)
        assert fetched is not None
        assert fetched.name == "TestRule"

    async def test_list_all(self, db_session):
        store = AutoSubscribeRuleStore(db_session)
        await store.create(_make_auto_subscribe_rule(name="Rule1"))
        await store.create(_make_auto_subscribe_rule(name="Rule2"))

        all_rules = await store.list_all()
        assert len(all_rules) == 2

    async def test_list_enabled(self, db_session):
        store = AutoSubscribeRuleStore(db_session)
        await store.create(_make_auto_subscribe_rule(name="Enabled", enabled=True))
        await store.create(_make_auto_subscribe_rule(name="Disabled", enabled=False))

        enabled = await store.list_enabled()
        assert len(enabled) == 1
        assert enabled[0].name == "Enabled"

    async def test_update(self, db_session):
        store = AutoSubscribeRuleStore(db_session)
        rule = await store.create(_make_auto_subscribe_rule())
        rule.name = "Updated"
        updated = await store.update(rule)
        assert updated.name == "Updated"

    async def test_delete(self, db_session):
        store = AutoSubscribeRuleStore(db_session)
        rule = await store.create(_make_auto_subscribe_rule())
        rule_id = rule.id

        await store.delete(rule)
        assert await store.get_by_id(rule_id) is None


# ── ErrorLogStore ───────────────────────────────────────────────────────


class TestErrorLogStore:
    async def test_create_and_list_recent(self, db_session):
        # Need subscription and episode for FK
        sub_store = SubscriptionStore(db_session)
        sub = await sub_store.create(_make_subscription())

        ep_store = EpisodeStore(db_session)
        ep = await ep_store.create(_make_episode(sub.id, 1))

        log_store = ErrorLogStore(db_session)
        log1 = await log_store.create(
            episode_id=ep.id,
            subscription_id=sub.id,
            node_name="fetch_rss",
            error_message="Connection timeout",
            resolution="retry_success",
        )
        assert log1.id is not None

        await log_store.create(
            episode_id=ep.id,
            subscription_id=sub.id,
            node_name="send_download",
            error_message="qB offline",
        )

        recent = await log_store.list_recent(ep.id, limit=5)
        assert len(recent) == 2
        # Most recent first
        assert recent[0].node_name == "send_download"

    async def test_list_recent_respects_limit(self, db_session):
        sub_store = SubscriptionStore(db_session)
        sub = await sub_store.create(_make_subscription())

        ep_store = EpisodeStore(db_session)
        ep = await ep_store.create(_make_episode(sub.id, 1))

        log_store = ErrorLogStore(db_session)
        for i in range(5):
            await log_store.create(
                episode_id=ep.id,
                subscription_id=sub.id,
                node_name=f"node_{i}",
                error_message=f"Error {i}",
            )

        recent = await log_store.list_recent(ep.id, limit=3)
        assert len(recent) == 3

    async def test_list_recent_empty(self, db_session):
        log_store = ErrorLogStore(db_session)
        recent = await log_store.list_recent(9999)
        assert recent == []


# ── Store facade ────────────────────────────────────────────────────────


class TestStoreFacade:
    async def test_facade_exposes_all_substores(self, db_session):
        store = Store(db_session)
        assert isinstance(store.subscriptions, SubscriptionStore)
        assert isinstance(store.episodes, EpisodeStore)
        assert isinstance(store.schedules, TaskScheduleStore)
        assert isinstance(store.user_requests, UserRequestStore)
        assert isinstance(store.rss_sources, RSSSourceStore)
        assert isinstance(store.auto_subscribe_rules, AutoSubscribeRuleStore)
        assert isinstance(store.error_logs, ErrorLogStore)

    async def test_async_context_manager(self, db_session):
        async with Store(db_session) as store:
            assert store is not None
            assert isinstance(store.subscriptions, SubscriptionStore)
