"""Tests for the human_review node."""

from anime_agent.agents.episode.nodes.human_review import HumanReviewNode


class TestHumanReviewNode:
    async def test_returns_human_review_when_no_input(self):
        """HumanReviewNode should set requires_human=True when no human_input."""
        state = {
            "episode_number": 1,
            "subscription_id": 1,
            "human_input": None,
        }
        node = HumanReviewNode()
        result = await node(state)

        assert result["status"] == "human_review"
        assert result["requires_human"] is True

    async def test_returns_matched_when_human_input_received(self):
        """HumanReviewNode should set status=matched when human_input is present."""
        state = {
            "episode_number": 1,
            "subscription_id": 1,
            "human_input": "approved",
        }
        node = HumanReviewNode()
        result = await node(state)

        assert result["status"] == "matched"
        assert result["requires_human"] is False

    async def test_returns_matched_on_any_truthy_input(self):
        """HumanReviewNode should accept any truthy human_input."""
        state = {
            "episode_number": 1,
            "subscription_id": 1,
            "human_input": "use hash abc123",
        }
        node = HumanReviewNode()
        result = await node(state)

        assert result["status"] == "matched"
        assert result["requires_human"] is False

    async def test_returns_human_review_on_empty_string(self):
        """HumanReviewNode should treat empty string as no input."""
        state = {
            "episode_number": 1,
            "subscription_id": 1,
            "human_input": "",
        }
        node = HumanReviewNode()
        result = await node(state)

        assert result["status"] == "human_review"
        assert result["requires_human"] is True
