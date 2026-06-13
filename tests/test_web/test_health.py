"""Tests for the health endpoint."""


async def test_health_returns_ok(client):
    """The health endpoint should report the app is running."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
