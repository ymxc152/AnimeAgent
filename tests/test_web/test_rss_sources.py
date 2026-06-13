"""Tests for RSS source API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_rss_source(client: AsyncClient) -> None:
    """POST /api/rss-sources should create and return a new RSS source."""
    payload = {"name": "Anime Garden", "url": "https://api.animes.garden/feed.xml"}
    response = await client.post("/api/rss-sources", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["url"] == payload["url"]
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_list_rss_sources(client: AsyncClient) -> None:
    """GET /api/rss-sources should return all RSS sources ordered by name."""
    await client.post(
        "/api/rss-sources",
        json={"name": "Beta Feed", "url": "https://example.com/beta"},
    )
    await client.post(
        "/api/rss-sources",
        json={"name": "Alpha Feed", "url": "https://example.com/alpha"},
    )

    response = await client.get("/api/rss-sources")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Alpha Feed"
    assert data[1]["name"] == "Beta Feed"


@pytest.mark.asyncio
async def test_update_rss_source(client: AsyncClient) -> None:
    """PATCH /api/rss-sources/{id} should update the source."""
    create_resp = await client.post(
        "/api/rss-sources",
        json={"name": "Old Name", "url": "https://example.com/old"},
    )
    source_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/rss-sources/{source_id}",
        json={"name": "New Name", "is_active": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["is_active"] is False
    assert data["url"] == "https://example.com/old"


@pytest.mark.asyncio
async def test_delete_rss_source(client: AsyncClient) -> None:
    """DELETE /api/rss-sources/{id} should remove the source."""
    create_resp = await client.post(
        "/api/rss-sources",
        json={"name": "To Delete", "url": "https://example.com/delete"},
    )
    source_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/rss-sources/{source_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get("/api/rss-sources")
    assert get_resp.status_code == 200
    assert not any(s["id"] == source_id for s in get_resp.json())


@pytest.mark.asyncio
async def test_update_missing_rss_source_returns_404(client: AsyncClient) -> None:
    """PATCH for a non-existent RSS source should return 404."""
    response = await client.patch("/api/rss-sources/9999", json={"name": "x"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_missing_rss_source_returns_404(client: AsyncClient) -> None:
    """DELETE for a non-existent RSS source should return 404."""
    response = await client.delete("/api/rss-sources/9999")
    assert response.status_code == 404
