"""Tests for ErrorHandlerNode — Agent-driven error recovery."""

import json
from unittest.mock import AsyncMock, MagicMock

from anime_agent.agents.episode.error_handler import ErrorHandlerNode
from anime_agent.tools.base import ToolOutput


def _mock_llm_response(action: str = "abort", reasoning: str = "test", command: str = "") -> AsyncMock:
    mock = AsyncMock()
    payload = {"action": action, "reasoning": reasoning}
    if command:
        payload["command"] = command
    mock.invoke.return_value = ToolOutput(
        success=True,
        data={"text": json.dumps(payload)},
    )
    return mock


def _base_state(failed_node: str = "fetch_rss") -> dict:
    return {
        "subscription_id": 1,
        "episode_number": 1,
        "_error_handler_node": failed_node,
        "errors": ["Connection timeout"],
        "status": "failed",
    }


# ── Core behavior ───────────────────────────────────────────────────────


class TestErrorHandlerNode:
    async def test_abort_returns_failed(self):
        """Should return failed status when LLM chooses abort."""
        handler = ErrorHandlerNode(llm_tool=_mock_llm_response("abort", "Cannot fix"))
        result = await handler(_base_state())

        assert result["status"] == "failed"
        assert "abort" in result["errors"][0].lower()

    async def test_skip_returns_skipped(self):
        """Should return skipped status when LLM chooses skip."""
        handler = ErrorHandlerNode(llm_tool=_mock_llm_response("skip", "Not critical"))
        result = await handler(_base_state())

        assert result["status"] == "skipped"
        assert result["_error_handler_resolved"] is True
        assert "warnings" in result

    async def test_retry_returns_retry_node(self):
        """Should return retry_<node> status when LLM chooses retry."""
        handler = ErrorHandlerNode(llm_tool=_mock_llm_response("retry", "Try again"))
        result = await handler(_base_state("send_download"))

        assert result["status"] == "retry_send_download"
        assert result["_error_handler_resolved"] is True

    async def test_bash_action_executes_command(self):
        """Should execute bash command and loop for next action."""
        mock_bash = AsyncMock()
        mock_bash.invoke.return_value = ToolOutput(success=True, data={"stdout": "ok"})

        mock_llm = AsyncMock()
        mock_llm.invoke.side_effect = [
            ToolOutput(success=True, data={"text": json.dumps({"action": "bash", "reasoning": "diag", "command": "echo ok"})}),
            ToolOutput(success=True, data={"text": json.dumps({"action": "retry", "reasoning": "fixed"})}),
        ]

        handler = ErrorHandlerNode(llm_tool=mock_llm, bash_tool=mock_bash)
        result = await handler(_base_state())

        assert result["status"] == "retry_fetch_rss"
        assert mock_bash.invoke.call_count == 1

    async def test_bash_empty_command_continues(self):
        """Should continue to next iteration when bash action has no command."""
        mock_llm = AsyncMock()
        mock_llm.invoke.side_effect = [
            ToolOutput(success=True, data={"text": json.dumps({"action": "bash", "reasoning": "diag"})}),
            ToolOutput(success=True, data={"text": json.dumps({"action": "abort", "reasoning": "gave up"})}),
        ]

        handler = ErrorHandlerNode(llm_tool=mock_llm)
        result = await handler(_base_state())

        assert result["status"] == "failed"
        assert mock_llm.invoke.call_count == 2

    async def test_bash_failure_updates_last_error(self):
        """Should use bash output as new error context for next LLM call."""
        mock_bash = AsyncMock()
        mock_bash.invoke.return_value = ToolOutput(success=False, error="Permission denied")

        captured_prompts = []

        async def capture_invoke(params):
            prompt = params["prompt"] if isinstance(params, dict) else getattr(params, "prompt", "")
            captured_prompts.append(prompt)
            if len(captured_prompts) == 1:
                return ToolOutput(success=True, data={"text": json.dumps({"action": "bash", "reasoning": "try", "command": "ls /"})})
            return ToolOutput(success=True, data={"text": json.dumps({"action": "abort", "reasoning": "cannot fix"})})

        mock_llm = AsyncMock()
        mock_llm.invoke.side_effect = capture_invoke

        handler = ErrorHandlerNode(llm_tool=mock_llm, bash_tool=mock_bash)
        await handler(_base_state())

        # Second prompt should contain the bash error
        assert len(captured_prompts) == 2
        assert "Permission denied" in captured_prompts[1]


# ── Exhaustion ──────────────────────────────────────────────────────────


class TestErrorHandlerExhaustion:
    async def test_exhausts_max_iterations(self):
        """Should return failed when all iterations used up on bash."""
        mock_bash = AsyncMock()
        mock_bash.invoke.return_value = ToolOutput(success=True, data={"stdout": "still broken"})

        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = ToolOutput(
            success=True,
            data={"text": json.dumps({"action": "bash", "reasoning": "try again", "command": "echo test"})},
        )

        handler = ErrorHandlerNode(llm_tool=mock_llm, bash_tool=mock_bash)
        handler.MAX_ITERATIONS = 3
        result = await handler(_base_state())

        assert result["status"] == "failed"
        assert "exhausted" in result["errors"][0].lower()
        assert mock_llm.invoke.call_count == 3


# ── LLM failure ─────────────────────────────────────────────────────────


class TestErrorHandlerLLMFailure:
    async def test_returns_failed_on_llm_error(self):
        """Should return failed when LLM call raises exception."""
        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = ToolOutput(success=False, error="API timeout")

        handler = ErrorHandlerNode(llm_tool=mock_llm)
        result = await handler(_base_state())

        assert result["status"] == "failed"
        assert "LLM error" in result["errors"][0]


# ── Memory loading ──────────────────────────────────────────────────────


class TestErrorHandlerMemory:
    async def test_loads_memory_from_store(self):
        """Should load recent error logs as context."""
        mock_log = MagicMock()
        mock_log.node_name = "fetch_rss"
        mock_log.error_message = "Previous timeout"
        mock_log.resolution = "retry_success"
        mock_log.created_at = None

        mock_store = MagicMock()
        mock_store.error_logs.list_recent = AsyncMock(return_value=[mock_log])

        mock_session = MagicMock()

        import contextlib

        @contextlib.asynccontextmanager
        async def _factory():
            yield mock_session

        mock_llm = _mock_llm_response("abort", "done")

        from unittest.mock import patch

        # Store is imported inside _load_memory, so patch the source module
        with patch("anime_agent.memory.store.Store", return_value=mock_store):
            handler = ErrorHandlerNode(llm_tool=mock_llm, session_factory=_factory)
            await handler(_base_state())

        mock_store.error_logs.list_recent.assert_called_once()

    async def test_handles_memory_load_failure(self):
        """Should continue even if memory loading fails."""
        import contextlib

        @contextlib.asynccontextmanager
        async def _factory():
            raise RuntimeError("DB connection failed")
            yield  # pragma: no cover

        handler = ErrorHandlerNode(
            llm_tool=_mock_llm_response("abort", "ok"),
            session_factory=_factory,
        )
        # Should not raise
        result = await handler(_base_state())
        assert result["status"] == "failed"


# ── _parse_llm_output ───────────────────────────────────────────────────


class TestParseLLMOutput:
    def test_parses_plain_json(self):
        result = ErrorHandlerNode._parse_llm_output('{"action": "abort", "reasoning": "ok"}')
        assert result["action"] == "abort"

    def test_parses_json_in_code_block(self):
        text = '```json\n{"action": "skip", "reasoning": "test"}\n```'
        result = ErrorHandlerNode._parse_llm_output(text)
        assert result["action"] == "skip"

    def test_falls_back_to_brace_search(self):
        text = 'Analysis done. {"action": "retry", "reasoning": "try again"}'
        result = ErrorHandlerNode._parse_llm_output(text)
        assert result["action"] == "retry"

    def test_returns_abort_on_unparseable(self):
        result = ErrorHandlerNode._parse_llm_output("I don't know what to do")
        assert result["action"] == "abort"
