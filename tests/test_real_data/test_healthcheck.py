"""Real-data smoke tests for tool healthchecks."""

import pytest

from anime_agent.config import settings
from anime_agent.services.healthcheck import HealthCheck
from anime_agent.tools import get_all_tools
from anime_agent.tools.anilist_tool import AniListTool
from anime_agent.tools.bangumi_tool import BangumiTool
from anime_agent.tools.emby_tool import EmbyTool
from anime_agent.tools.qb_tool import QBTool
from anime_agent.tools.rss_tool import RSSTool
from anime_agent.tools.tmdb_tool import TMDBTool


@pytest.mark.real_data
async def test_anilist_healthcheck() -> None:
    """AniList healthcheck should succeed."""
    result = await AniListTool().healthcheck()
    assert result.success, result.error


@pytest.mark.real_data
async def test_bangumi_healthcheck() -> None:
    """Bangumi healthcheck should succeed."""
    result = await BangumiTool().healthcheck()
    assert result.success, result.error


@pytest.mark.real_data
async def test_rss_healthcheck() -> None:
    """RSS healthcheck should succeed."""
    result = await RSSTool().healthcheck()
    assert result.success, result.error


@pytest.mark.real_data
async def test_tmdb_healthcheck() -> None:
    """TMDB healthcheck should succeed when configured."""
    if not settings.tmdb_api_key and not settings.tmdb_read_access_token:
        pytest.skip("TMDB key not configured")
    result = await TMDBTool(api_key=settings.tmdb_api_key).healthcheck()
    assert result.success, result.error


@pytest.mark.real_data
async def test_qbittorrent_healthcheck() -> None:
    """qBittorrent healthcheck should succeed when configured."""
    if not settings.qb_host:
        pytest.skip("qBittorrent host not configured")
    result = await QBTool().healthcheck()
    assert result.success, result.error


@pytest.mark.real_data
async def test_emby_healthcheck() -> None:
    """Emby healthcheck should succeed when configured."""
    if not settings.emby_host or not settings.emby_api_key:
        pytest.skip("Emby host or api key not configured")
    result = await EmbyTool().healthcheck()
    assert result.success, result.error


@pytest.mark.real_data
async def test_healthcheck_aggregator() -> None:
    """HealthCheck aggregator should run all tool checks."""
    tools = get_all_tools()
    health_check = HealthCheck(tools=tools)
    report = await health_check.run()
    # The report is healthy only if all critical tools pass; none are critical here.
    assert report.healthy or report.errors
    assert len(report.checks) == len(tools)
