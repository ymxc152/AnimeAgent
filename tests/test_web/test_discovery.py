"""Tests for discovery endpoints using real AniList data."""

import pytest


@pytest.mark.real_data
async def test_discovery_season_returns_anime_list(client):
    """GET /api/discovery/season should return real seasonal anime from AniList."""
    response = await client.get("/api/discovery/season?year=2024&season=fall")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) > 0

    anime = data[0]
    assert "anilist_id" in anime
    assert "title_romaji" in anime
    assert "format" in anime
    assert "total_episodes" in anime


async def test_discovery_subscribe_creates_subscription_and_episodes(client):
    """POST /api/discovery/subscribe should create a subscription and its episodes."""
    payload = {
        "title_romaji": "Sousou no Frieren",
        "title_chinese": "葬送的芙莉莲",
        "total_episodes": 3,
        "season_year": 2023,
        "season": "FALL",
    }

    response = await client.post("/api/discovery/subscribe", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["title_romaji"] == "Sousou no Frieren"
    assert data["source"] == "auto_discover"

    episodes_response = await client.get(f"/api/episodes?subscription_id={data['id']}")
    episodes = episodes_response.json()
    assert len(episodes) == 3
    assert {ep["episode_number"] for ep in episodes} == {1, 2, 3}
