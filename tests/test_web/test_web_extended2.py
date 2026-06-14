"""Extended web endpoint tests — retry, human_input, episode detail, RSS CRUD, logs."""


from anime_agent.memory.models import Episode, RSSSource, Subscription

# ── retry_episode ───────────────────────────────────────────────────────


async def test_retry_episode_resets_status(client, db_session):
    """POST /api/episodes/{id}/retry should reset a failed episode to pending."""
    sub = Subscription(bangumi_id=501, title_romaji="Test", total_episodes=1, local_folder_name="Test")
    db_session.add(sub)
    await db_session.flush()

    ep = Episode(
        subscription_id=sub.id,
        episode_number=1,
        status="failed",
        error_log="some error",
        torrent_failed_hashes='["abc123"]',
        low_confidence_count=3,
        torrent_candidates_attempt_count=2,
    )
    db_session.add(ep)
    await db_session.commit()

    response = await client.post(f"/api/episodes/{ep.id}/retry")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["error_log"] == ""


async def test_retry_episode_404(client):
    """POST /api/episodes/{id}/retry should return 404 for nonexistent episode."""
    response = await client.post("/api/episodes/99999/retry")
    assert response.status_code == 404


# ── submit_human_input ──────────────────────────────────────────────────


async def test_human_input_approve(client, db_session):
    """POST /api/episodes/{id}/human_input should approve a human_review episode."""
    sub = Subscription(bangumi_id=502, title_romaji="Test", total_episodes=1, local_folder_name="Test")
    db_session.add(sub)
    await db_session.flush()

    ep = Episode(subscription_id=sub.id, episode_number=1, status="human_review")
    db_session.add(ep)
    await db_session.commit()

    response = await client.post(
        f"/api/episodes/{ep.id}/human_input",
        json={"action": "approve", "torrent_link": "magnet:?xt=urn:btih:abc123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "matched"


async def test_human_input_reject(client, db_session):
    """POST /api/episodes/{id}/human_input with reject should reset to pending."""
    sub = Subscription(bangumi_id=503, title_romaji="Test", total_episodes=1, local_folder_name="Test")
    db_session.add(sub)
    await db_session.flush()

    ep = Episode(subscription_id=sub.id, episode_number=1, status="human_review")
    db_session.add(ep)
    await db_session.commit()

    response = await client.post(
        f"/api/episodes/{ep.id}/human_input",
        json={"action": "reject"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"


async def test_human_input_404(client):
    """POST /api/episodes/{id}/human_input should return 404 for nonexistent episode."""
    response = await client.post(
        "/api/episodes/99999/human_input",
        json={"action": "approve"},
    )
    assert response.status_code == 404


async def test_human_input_wrong_status(client, db_session):
    """POST /api/episodes/{id}/human_input should return 409 if not in human_review."""
    sub = Subscription(bangumi_id=504, title_romaji="Test", total_episodes=1, local_folder_name="Test")
    db_session.add(sub)
    await db_session.flush()

    ep = Episode(subscription_id=sub.id, episode_number=1, status="pending")
    db_session.add(ep)
    await db_session.commit()

    response = await client.post(
        f"/api/episodes/{ep.id}/human_input",
        json={"action": "approve"},
    )
    assert response.status_code == 409


# ── logs ────────────────────────────────────────────────────────────────


async def test_logs_returns_empty_when_no_file(client):
    """GET /api/logs should return empty list when log file doesn't exist."""
    response = await client.get("/api/logs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ── RSS sources CRUD ────────────────────────────────────────────────────


async def test_create_rss_source(client):
    """POST /api/rss-sources should create a new RSS source."""
    response = await client.post(
        "/api/rss-sources",
        json={"name": "TestRSS", "url": "https://example.com/rss"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "TestRSS"
    assert data["url"] == "https://example.com/rss"


async def test_list_rss_sources(client, db_session):
    """GET /api/rss-sources should return all RSS sources."""
    source = RSSSource(name="Test", url="https://example.com/rss", is_active=True)
    db_session.add(source)
    await db_session.commit()

    response = await client.get("/api/rss-sources")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


async def test_update_rss_source(client, db_session):
    """PATCH /api/rss-sources/{id} should update an RSS source."""
    source = RSSSource(name="Old", url="https://old.com/rss", is_active=True)
    db_session.add(source)
    await db_session.commit()

    response = await client.patch(
        f"/api/rss-sources/{source.id}",
        json={"name": "New"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New"


async def test_update_rss_source_404(client):
    """PATCH /api/rss-sources/{id} should return 404 for nonexistent source."""
    response = await client.patch(
        "/api/rss-sources/99999",
        json={"name": "New"},
    )
    assert response.status_code == 404


async def test_delete_rss_source(client, db_session):
    """DELETE /api/rss-sources/{id} should delete an RSS source."""
    source = RSSSource(name="ToDelete", url="https://del.com/rss")
    db_session.add(source)
    await db_session.commit()

    response = await client.delete(f"/api/rss-sources/{source.id}")
    assert response.status_code == 204


async def test_delete_rss_source_404(client):
    """DELETE /api/rss-sources/{id} should return 404 for nonexistent source."""
    response = await client.delete("/api/rss-sources/99999")
    assert response.status_code == 404


# ── Episode with torrent_candidates ─────────────────────────────────────


async def test_episode_detail_with_candidates(client, db_session):
    """GET /api/episodes/{id} should parse torrent_candidates JSON."""
    import json

    sub = Subscription(bangumi_id=505, title_romaji="Test", total_episodes=1, local_folder_name="Test")
    db_session.add(sub)
    await db_session.flush()

    ep = Episode(
        subscription_id=sub.id,
        episode_number=1,
        status="matched",
        torrent_candidates=json.dumps([{"info_hash": "abc", "title": "test"}]),
        torrent_failed_hashes=json.dumps(["old1"]),
    )
    db_session.add(ep)
    await db_session.commit()

    response = await client.get(f"/api/episodes/{ep.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["torrent_candidates_count"] == 1
    assert len(data["torrent_failed_hashes"]) == 1


# ── Episode with invalid JSON in candidates ─────────────────────────────


async def test_episode_detail_with_invalid_json(client, db_session):
    """GET /api/episodes/{id} should handle invalid JSON in torrent_candidates."""
    sub = Subscription(bangumi_id=506, title_romaji="Test", total_episodes=1, local_folder_name="Test")
    db_session.add(sub)
    await db_session.flush()

    ep = Episode(
        subscription_id=sub.id,
        episode_number=1,
        status="pending",
        torrent_candidates="not valid json",
    )
    db_session.add(ep)
    await db_session.commit()

    response = await client.get(f"/api/episodes/{ep.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["torrent_candidates_count"] == 0


# ── List episodes with multiple statuses ────────────────────────────────


async def test_list_episodes_with_multiple_status_filter(client, db_session):
    """GET /api/episodes?status=pending,failed should filter by multiple statuses."""
    sub = Subscription(bangumi_id=507, title_romaji="Test", total_episodes=4, local_folder_name="Test")
    db_session.add(sub)
    await db_session.flush()

    for i, status in enumerate(["pending", "completed", "failed", "downloading"], 1):
        db_session.add(Episode(subscription_id=sub.id, episode_number=i, status=status))
    await db_session.commit()

    response = await client.get("/api/episodes?status=pending,failed")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    statuses = {ep["status"] for ep in data}
    assert statuses == {"pending", "failed"}
