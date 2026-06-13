"""Tests for auto-subscribe rule endpoints."""

from anime_agent.memory.models import AutoSubscribeRule


async def test_create_and_list_auto_subscribe_rules(client, db_session):
    """POST and GET /api/auto-subscribe-rules should work."""
    response = await client.post(
        "/api/auto-subscribe-rules",
        json={
            "name": "Fantasy Auto",
            "include_genres": "Fantasy",
            "exclude_formats": "MOVIE",
            "use_llm": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Fantasy Auto"
    assert data["use_llm"] is True

    response = await client.get("/api/auto-subscribe-rules")
    assert response.status_code == 200
    rules = response.json()
    assert len(rules) == 1
    assert rules[0]["include_genres"] == "Fantasy"


async def test_update_auto_subscribe_rule(client, db_session):
    """PATCH /api/auto-subscribe-rules/{id} should update fields."""
    rule = AutoSubscribeRule(name="Old", enabled=True)
    db_session.add(rule)
    await db_session.commit()

    response = await client.patch(
        f"/api/auto-subscribe-rules/{rule.id}",
        json={"name": "New", "enabled": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New"
    assert data["enabled"] is False


async def test_delete_auto_subscribe_rule(client, db_session):
    """DELETE /api/auto-subscribe-rules/{id} should remove the rule."""
    rule = AutoSubscribeRule(name="To Delete", enabled=True)
    db_session.add(rule)
    await db_session.commit()

    response = await client.delete(f"/api/auto-subscribe-rules/{rule.id}")
    assert response.status_code == 204

    response = await client.get("/api/auto-subscribe-rules")
    assert response.json() == []


async def test_discovery_season_supports_search(client):
    """GET /api/discovery/season should accept a search parameter."""
    response = await client.get("/api/discovery/season?year=2024&season=WINTER&search=test")
    assert response.status_code == 200
    # The actual result depends on external API availability; just verify it doesn't crash.
    assert isinstance(response.json(), list)
