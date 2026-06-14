"""Extended tests for DiscoveryService — run, duplicate check, season inference."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anime_agent.config import Settings
from anime_agent.services.discovery import DiscoveryService


@pytest.fixture
def mock_resolver():
    resolver = MagicMock()
    resolver.get_seasonal = AsyncMock()
    resolver.should_fallback_to_resource_search.return_value = False
    return resolver


@pytest.fixture
def mock_filter():
    f = MagicMock()
    f.apply.return_value = MagicMock(allowed=True)
    return f


@pytest.fixture
def mock_planner():
    p = MagicMock()
    p.plan_next_run.return_value = datetime.now(UTC)
    return p


@pytest.fixture
def service(db_session: AsyncSession, mock_resolver, mock_filter, mock_planner) -> DiscoveryService:
    return DiscoveryService(
        session=db_session,
        resolver=mock_resolver,
        filter_service=mock_filter,
        planner=mock_planner,
        settings=Settings(),
    )


# ── _current_season ─────────────────────────────────────────────────────


class TestCurrentSeason:
    def test_january_is_winter(self, service):
        with patch("anime_agent.services.discovery.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 15, tzinfo=UTC)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            year, season = service._current_season()
            assert season == "WINTER"
            assert year == 2026

    def test_april_is_spring(self, service):
        with patch("anime_agent.services.discovery.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 10, tzinfo=UTC)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            year, season = service._current_season()
            assert season == "SPRING"

    def test_july_is_summer(self, service):
        with patch("anime_agent.services.discovery.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 7, 20, tzinfo=UTC)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            year, season = service._current_season()
            assert season == "SUMMER"

    def test_october_is_fall(self, service):
        with patch("anime_agent.services.discovery.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 10, 5, tzinfo=UTC)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            year, season = service._current_season()
            assert season == "FALL"


# ── _infer_weekday ──────────────────────────────────────────────────────


class TestInferWeekday:
    def test_returns_weekday_for_valid_date(self, service):
        # 2026-01-05 is a Monday (weekday=0)
        assert service._infer_weekday("2026-01-05") == 0

    def test_returns_none_for_empty_string(self, service):
        assert service._infer_weekday("") is None

    def test_returns_none_for_none(self, service):
        assert service._infer_weekday(None) is None

    def test_returns_none_for_invalid_format(self, service):
        assert service._infer_weekday("not-a-date") is None


# ── _is_duplicate ───────────────────────────────────────────────────────


class TestIsDuplicate:
    async def test_returns_true_when_bangumi_id_exists(self, service, db_session):
        from anime_agent.memory.models import Subscription
        sub = Subscription(bangumi_id=999, title_romaji="Existing", status="ongoing")
        db_session.add(sub)
        await db_session.commit()

        result = await service._is_duplicate({"bangumi_id": 999, "anilist_id": None})
        assert result is True

    async def test_returns_true_when_anilist_id_exists(self, service, db_session):
        from anime_agent.memory.models import Subscription
        sub = Subscription(bangumi_id=888, anilist_id=888, title_romaji="Existing", status="ongoing")
        db_session.add(sub)
        await db_session.commit()

        result = await service._is_duplicate({"bangumi_id": None, "anilist_id": 888})
        assert result is True

    async def test_returns_false_when_no_ids_match(self, service):
        result = await service._is_duplicate({"bangumi_id": None, "anilist_id": None})
        assert result is False

    async def test_returns_false_for_new_ids(self, service):
        result = await service._is_duplicate({"bangumi_id": 99999, "anilist_id": 99999})
        assert result is False


# ── run ─────────────────────────────────────────────────────────────────


class TestDiscoveryRun:
    async def test_returns_error_when_resolver_fails(self, service, mock_resolver):
        mock_resolver.get_seasonal.return_value = MagicMock(success=False, error="API down")

        result = await service.run()
        assert result["created"] == 0
        assert result["error"] == "API down"

    async def test_filters_out_content_filtered_anime(self, service, mock_resolver, mock_filter):
        mock_resolver.get_seasonal.return_value = MagicMock(
            success=True,
            data={"candidates": [{"title_romaji": "OVA Special"}]},
        )
        mock_filter.apply.return_value = MagicMock(allowed=False)

        result = await service.run()
        assert result["filtered"] == 1
        assert result["created"] == 0

    async def test_skips_duplicates(self, service, mock_resolver, db_session):
        from anime_agent.memory.models import Subscription
        sub = Subscription(bangumi_id=500, title_romaji="Existing", status="ongoing")
        db_session.add(sub)
        await db_session.commit()

        mock_resolver.get_seasonal.return_value = MagicMock(
            success=True,
            data={"candidates": [{"bangumi_id": 500, "title_romaji": "Existing"}]},
        )

        result = await service.run()
        assert result["created"] == 0

    async def test_creates_subscription_for_new_anime(self, service, mock_resolver):
        mock_resolver.get_seasonal.return_value = MagicMock(
            success=True,
            data={
                "candidates": [
                    {
                        "bangumi_id": 777,
                        "anilist_id": 777,
                        "title_romaji": "New Anime",
                        "title_native": "新アニメ",
                        "title_chinese": "新动漫",
                        "season_year": 2026,
                        "season": "SPRING",
                        "total_episodes": 12,
                        "air_date": "2026-04-01",
                    }
                ]
            },
        )
        service.settings.filter_auto_subscribe_new_season = True

        result = await service.run()
        assert result["created"] == 1

        # Verify subscription was created
        sub = await service.store.subscriptions.get_by_bangumi_id(777)
        assert sub is not None
        assert sub.title_romaji == "New Anime"

    async def test_returns_empty_for_no_candidates(self, service, mock_resolver):
        mock_resolver.get_seasonal.return_value = MagicMock(
            success=True,
            data={"candidates": []},
        )

        result = await service.run()
        assert result["created"] == 0
        assert result["total"] == 0
