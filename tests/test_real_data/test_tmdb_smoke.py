"""Real-data smoke test for TMDBTool."""

import pytest

from anime_agent.config import settings
from anime_agent.tools.tmdb_tool import TMDBTool


@pytest.mark.real_data
async def test_tmdb_healthcheck_with_configured_key() -> None:
    """TMDBTool healthcheck should succeed when a key is configured."""
    if not settings.tmdb_api_key and not settings.tmdb_read_access_token:
        pytest.skip("TMDB key not configured")

    tool = TMDBTool(api_key=settings.tmdb_api_key)
    result = await tool.healthcheck()
    assert result.success, result.error
