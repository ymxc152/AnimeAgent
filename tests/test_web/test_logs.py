"""Tests for the logs endpoint."""


async def test_logs_returns_list_of_lines(client):
    """GET /api/logs should return recent log lines."""
    response = await client.get("/api/logs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
