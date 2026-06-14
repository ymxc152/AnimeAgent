"""Tests for the handle_error node."""

from anime_agent.agents.episode.nodes.handle_error import HandleErrorNode


class TestHandleErrorNode:
    async def test_marks_status_as_failed(self):
        """HandleErrorNode should always set status to failed."""
        state = {
            "episode_number": 1,
            "subscription_id": 1,
            "status": "downloading",
            "errors": ["qBittorrent connection failed"],
        }
        node = HandleErrorNode()
        result = await node(state)

        assert result["status"] == "failed"

    async def test_preserves_existing_errors(self):
        """HandleErrorNode should pass through existing errors."""
        errors = ["Error 1", "Error 2"]
        state = {
            "episode_number": 1,
            "subscription_id": 1,
            "status": "failed",
            "errors": errors,
        }
        node = HandleErrorNode()
        result = await node(state)

        assert result["errors"] == errors

    async def test_overrides_non_failed_status(self):
        """HandleErrorNode should force status to failed even if state says otherwise."""
        state = {
            "episode_number": 5,
            "subscription_id": 42,
            "status": "matched",
            "errors": ["unexpected error"],
        }
        node = HandleErrorNode()
        result = await node(state)

        assert result["status"] == "failed"

    async def test_handles_empty_errors(self):
        """HandleErrorNode should handle empty errors list gracefully."""
        state = {
            "episode_number": 1,
            "subscription_id": 1,
            "status": "pending",
            "errors": [],
        }
        node = HandleErrorNode()
        result = await node(state)

        assert result["status"] == "failed"
        assert result["errors"] == []

    async def test_handles_missing_errors_key(self):
        """HandleErrorNode should handle missing errors key."""
        state = {
            "episode_number": 1,
            "subscription_id": 1,
            "status": "pending",
        }
        node = HandleErrorNode()
        result = await node(state)

        assert result["status"] == "failed"
        assert result["errors"] == []
