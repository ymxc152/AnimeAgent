"""Tests for search_resources node."""

from unittest.mock import AsyncMock

from anime_agent.agents.episode.nodes.search_resources import SearchResourcesNode
from anime_agent.tools.base import ToolOutput


def _state(**overrides) -> dict:
    base = {
        "subscription_id": 42,
        "episode_number": 1,
        "title_romaji": "Sousou no Frieren",
        "title_native": "葬送のフリーレン",
        "title_chinese": "葬送的芙莉莲",
        "torrent_candidates": [],
        "torrent_failed_hashes": [],
        "status": "pending",
        "errors": [],
    }
    base.update(overrides)
    return base


class TestSearchResourcesNode:
    """Test SearchResourcesNode."""

    async def test_search_returns_candidates(self):
        """Should return candidates from AnimeGardenTool."""
        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = ToolOutput(
            success=True,
            data={
                "candidates": [
                    {"info_hash": "abc1", "title": "[Sub] Frieren - 01", "source": "animes_garden"},
                    {"info_hash": "abc2", "title": "[Sub] Frieren - 02", "source": "animes_garden"},
                ],
            },
        )

        node = SearchResourcesNode(anime_garden_tool=mock_tool)
        result = await node(_state())

        assert result["status"] == "searched"
        assert len(result["torrent_candidates"]) == 2
        assert result["torrent_candidates"][0]["info_hash"] == "abc1"

    async def test_search_merges_with_existing(self):
        """Should merge new candidates with existing ones."""
        state = _state(torrent_candidates=[
            {"info_hash": "abc1", "title": "old", "source": "rss"},
        ])

        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = ToolOutput(
            success=True,
            data={
                "candidates": [
                    {"info_hash": "abc1", "title": "duplicate", "source": "animes_garden"},
                    {"info_hash": "abc2", "title": "new", "source": "animes_garden"},
                ],
            },
        )

        node = SearchResourcesNode(anime_garden_tool=mock_tool)
        result = await node(state)

        assert len(result["torrent_candidates"]) == 2
        hashes = {c["info_hash"] for c in result["torrent_candidates"]}
        assert hashes == {"abc1", "abc2"}

    async def test_search_uses_chinese_title(self):
        """Should use Chinese title as search keyword."""
        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = ToolOutput(success=True, data={"candidates": []})

        node = SearchResourcesNode(anime_garden_tool=mock_tool)
        await node(_state())

        call_args = mock_tool.invoke.call_args[0][0]
        assert call_args.search == "葬送的芙莉莲"

    async def test_search_falls_back_to_romaji(self):
        """Should fall back to romaji title when no Chinese title."""
        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = ToolOutput(success=True, data={"candidates": []})

        node = SearchResourcesNode(anime_garden_tool=mock_tool)
        await node(_state(title_chinese=None))

        call_args = mock_tool.invoke.call_args[0][0]
        assert call_args.search == "Sousou no Frieren"

    async def test_search_returns_failed_on_tool_error(self):
        """Should return failed status when tool fails."""
        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = ToolOutput(success=False, error="API down")

        node = SearchResourcesNode(anime_garden_tool=mock_tool)
        result = await node(_state())

        assert result["status"] == "failed"
        assert len(result["errors"]) > 0

    async def test_search_preserves_existing_on_failure(self):
        """Should preserve existing candidates on tool failure."""
        state = _state(torrent_candidates=[
            {"info_hash": "abc1", "title": "existing", "source": "rss"},
        ])

        mock_tool = AsyncMock()
        mock_tool.invoke.return_value = ToolOutput(success=False, error="API down")

        node = SearchResourcesNode(anime_garden_tool=mock_tool)
        result = await node(state)

        assert result["status"] == "failed"
        assert len(result["torrent_candidates"]) == 1
