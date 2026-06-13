"""Tests for frontend static file serving."""


async def test_root_serves_frontend_index(client):
    """GET / should serve the single-page application entry point."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "AnimeAgent" in response.text
