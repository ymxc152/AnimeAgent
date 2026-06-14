"""Tests for process_metadata node."""

from unittest.mock import AsyncMock, patch

import pytest

from anime_agent.agents.episode.nodes.process_metadata import ProcessMetadataNode
from anime_agent.tools.base import ToolOutput


@pytest.fixture
def node():
    return ProcessMetadataNode(tmdb_tool=AsyncMock())


async def test_process_metadata_defaults_to_tv(node):
    result = await node({"episode_number": 1, "subscription_id": 1})
    assert result["content_type"] == "TV"
    assert result["status"] == "metadata_processed"


async def test_process_metadata_uses_state_format(node):
    result = await node({"episode_number": 1, "subscription_id": 1, "format": "Movie"})
    assert result["content_type"] == "Movie"


async def test_process_metadata_preserves_existing_content_type(node):
    result = await node({
        "episode_number": 1,
        "subscription_id": 1,
        "content_type": "OVA",
        "format": "Movie",
    })
    assert result["content_type"] == "OVA"


async def test_process_metadata_sets_defaults(node):
    result = await node({"episode_number": 1, "subscription_id": 1})
    assert result["tmdb_id"] is None
    assert result["confidence"] == 0.0
    assert result["verified"] is False


async def test_process_metadata_verifies_when_tmdb_matches(node):
    node.tmdb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"season": {"episodes": [{"episode_number": 5, "name": "Ep 5"}]}},
    )

    result = await node({
        "episode_number": 5,
        "subscription_id": 1,
        "tmdb_id": 123,
        "season": 1,
    })

    assert result["verified"] is True
    assert result["confidence"] == 1.0
    node.tmdb_tool.invoke.assert_awaited_once()


async def test_process_metadata_not_verified_when_tmdb_mismatches(node):
    node.tmdb_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"season": {"episodes": [{"episode_number": 4, "name": "Ep 4"}]}},
    )

    result = await node({
        "episode_number": 5,
        "subscription_id": 1,
        "tmdb_id": 123,
        "season": 1,
    })

    assert result["verified"] is False
    assert result["confidence"] == 0.0


async def test_process_metadata_skips_tmdb_without_api_key():
    fake_settings = type("Settings", (), {"tmdb_api_key": None})()
    with patch("anime_agent.agents.episode.nodes.process_metadata.settings", fake_settings):
        tmdb_tool = AsyncMock()
        node = ProcessMetadataNode(tmdb_tool=tmdb_tool)

        result = await node({
            "episode_number": 5,
            "subscription_id": 1,
            "tmdb_id": 123,
            "season": 1,
        })

    assert result["verified"] is False
    tmdb_tool.invoke.assert_not_awaited()


async def test_process_metadata_skips_tmdb_without_tmdb_id(node):
    result = await node({
        "episode_number": 5,
        "subscription_id": 1,
        "tmdb_id": None,
        "season": 1,
    })

    assert result["verified"] is False
    node.tmdb_tool.invoke.assert_not_awaited()


async def test_process_metadata_graceful_when_tmdb_fails(node):
    node.tmdb_tool.invoke.return_value = ToolOutput(
        success=False,
        error="API error",
    )

    result = await node({
        "episode_number": 5,
        "subscription_id": 1,
        "tmdb_id": 123,
        "season": 1,
    })

    assert result["verified"] is False
    assert result["status"] == "metadata_processed"
