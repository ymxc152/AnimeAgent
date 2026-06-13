"""Tests for process_metadata node."""

import pytest

from anime_agent.agents.episode.nodes.process_metadata import ProcessMetadataNode


@pytest.fixture
def node():
    return ProcessMetadataNode()


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
    assert result["confidence"] == 1.0
    assert result["verified"] is False
