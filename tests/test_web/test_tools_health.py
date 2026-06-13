"""Tests for the tool health endpoint."""


async def test_tools_health_returns_status_for_each_tool(client):
    """GET /api/tools/health should report health for all integrated tools."""
    response = await client.get("/api/tools/health")
    assert response.status_code == 200
    data = response.json()

    for tool in ("bangumi", "anilist", "tmdb", "rss", "qbittorrent", "emby"):
        assert tool in data
        assert "healthy" in data[tool]
        assert isinstance(data[tool]["healthy"], bool)
