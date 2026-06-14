"""Tests for BaseAgentNode — abstract base class for agent-driven nodes."""

import json
from typing import Any
from unittest.mock import AsyncMock

from anime_agent.agents.episode.base_agent import AgentAction, BaseAgentNode
from anime_agent.tools.base import ToolOutput

# ── Concrete test subclass ──────────────────────────────────────────────


class ConcreteAgentNode(BaseAgentNode):
    """Minimal concrete implementation for testing the base class."""

    NODE_NAME = "test_agent"
    SYSTEM_PROMPT = "You are a test agent."
    ACTIONS = {"done": "Finish", "bash": "Run command", "skip": "Skip"}
    MAX_LLM_CALLS = 3

    def _build_prompt(self, context: dict[str, Any], state: dict[str, Any]) -> str:
        return f"Test prompt for episode {state.get('episode_number')}"


def _mock_llm(action: str = "done", **extra) -> AsyncMock:
    mock = AsyncMock()
    mock.invoke.return_value = ToolOutput(
        success=True,
        data={"text": json.dumps({"action": action, "reasoning": "test", **extra})},
    )
    return mock


def _base_state() -> dict:
    return {
        "subscription_id": 1,
        "episode_number": 1,
        "status": "pending",
        "errors": [],
    }


# ── AgentAction ─────────────────────────────────────────────────────────


class TestAgentAction:
    def test_defaults_params_to_empty_dict(self):
        action = AgentAction("done")
        assert action.type == "done"
        assert action.params == {}

    def test_stores_params(self):
        action = AgentAction("bash", {"command": "ls"})
        assert action.type == "bash"
        assert action.params["command"] == "ls"

    def test_repr(self):
        action = AgentAction("done")
        assert "done" in repr(action)


# ── BaseAgentNode.__call__ ──────────────────────────────────────────────


class TestBaseAgentNodeCall:
    async def test_returns_status_on_terminal_action(self):
        """Should return result immediately when LLM returns a terminal action."""
        node = ConcreteAgentNode(llm_tool=_mock_llm("done"))
        result = await node(_base_state())
        assert result["status"] == "done"

    async def test_loops_until_terminal_action(self):
        """Should loop when LLM returns non-terminal actions, then stop on terminal."""
        mock = AsyncMock()
        # First call: bash (non-terminal), second: done (terminal)
        mock.invoke.side_effect = [
            ToolOutput(success=True, data={"text": json.dumps({"action": "bash", "reasoning": "diag", "command": "echo ok"})}),
            ToolOutput(success=True, data={"text": json.dumps({"action": "done", "reasoning": "fixed"})}),
        ]
        node = ConcreteAgentNode(llm_tool=mock)
        node.bash_tool = AsyncMock()
        node.bash_tool.invoke.return_value = ToolOutput(success=True, data={"stdout": "ok"})

        result = await node(_base_state())
        assert result["status"] == "done"
        assert mock.invoke.call_count == 2

    async def test_exhausts_max_iterations(self):
        """Should return failed when max iterations exhausted with non-terminal actions."""
        mock = AsyncMock()
        mock.invoke.return_value = ToolOutput(
            success=True,
            data={"text": json.dumps({"action": "bash", "reasoning": "try again", "command": "echo ok"})},
        )
        node = ConcreteAgentNode(llm_tool=mock)
        node.MAX_LLM_CALLS = 2
        node.bash_tool = AsyncMock()
        node.bash_tool.invoke.return_value = ToolOutput(success=True, data={"stdout": "ok"})

        result = await node(_base_state())
        assert result["status"] == "failed"
        assert "exhausted" in result["errors"][0].lower()

    async def test_returns_error_on_llm_failure(self):
        """Should return error result when LLM call raises."""
        mock = AsyncMock()
        mock.invoke.return_value = ToolOutput(success=False, error="LLM down")

        node = ConcreteAgentNode(llm_tool=mock)
        result = await node(_base_state())

        assert result["status"] == "failed"
        assert "LLM error" in result["errors"][0]


# ── BaseAgentNode._act ──────────────────────────────────────────────────


class TestBaseAgentNodeAct:
    async def test_bash_action_executes_command(self):
        """Should execute bash command and return output."""
        mock_bash = AsyncMock()
        mock_bash.invoke.return_value = ToolOutput(success=True, data={"stdout": "file.txt"})

        node = ConcreteAgentNode(llm_tool=_mock_llm())
        node.bash_tool = mock_bash

        action = AgentAction("bash", {"command": "ls"})
        result = await node._act(action, _base_state())

        assert result["success"] is True
        assert "file.txt" in result["output"]

    async def test_bash_action_with_no_command(self):
        """Should handle bash action with empty command."""
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        action = AgentAction("bash", {})
        result = await node._act(action, _base_state())
        assert result["success"] is True
        assert "No action" in result["output"]

    async def test_unknown_action_returns_noop(self):
        """Should return success for unknown action types."""
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        action = AgentAction("unknown_action")
        result = await node._act(action, _base_state())
        assert result["success"] is True


# ── BaseAgentNode._is_terminal ──────────────────────────────────────────


class TestBaseAgentNodeIsTerminal:
    def test_done_is_terminal(self):
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        assert node._is_terminal(AgentAction("done")) is True

    def test_skip_is_terminal(self):
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        assert node._is_terminal(AgentAction("skip")) is True

    def test_bash_is_not_terminal(self):
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        assert node._is_terminal(AgentAction("bash")) is False


# ── BaseAgentNode._parse_llm_output ────────────────────────────────────


class TestParseLLMOutput:
    def test_parses_plain_json(self):
        result = BaseAgentNode._parse_llm_output('{"action": "done", "reasoning": "ok"}')
        assert result["action"] == "done"

    def test_parses_json_in_code_block(self):
        text = '```json\n{"action": "skip", "reasoning": "test"}\n```'
        result = BaseAgentNode._parse_llm_output(text)
        assert result["action"] == "skip"

    def test_parses_json_in_untyped_code_block(self):
        text = '```\n{"action": "done", "reasoning": "ok"}\n```'
        result = BaseAgentNode._parse_llm_output(text)
        assert result["action"] == "done"

    def test_falls_back_to_brace_search(self):
        text = 'Here is my answer: {"action": "abort", "reasoning": "no data"} done.'
        result = BaseAgentNode._parse_llm_output(text)
        assert result["action"] == "abort"

    def test_returns_abort_on_unparseable(self):
        result = BaseAgentNode._parse_llm_output("I don't understand")
        assert result["action"] == "abort"
        assert "Failed to parse" in result["reasoning"]


# ── BaseAgentNode context management ────────────────────────────────────


class TestContextManagement:
    async def test_load_context_returns_memory(self):
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        ctx = await node._load_context(_base_state())
        assert "memory" in ctx

    def test_extend_context_appends_history(self):
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        ctx = {"memory": []}
        action = AgentAction("bash", {"command": "ls"})
        result = {"output": "file.txt"}

        ctx = node._extend_context(ctx, action, result)
        assert len(ctx["history"]) == 1
        assert ctx["history"][0]["action"] == "bash"

    def test_extend_context_creates_history_key(self):
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        ctx = {}
        node._extend_context(ctx, AgentAction("done"), {"output": ""})
        assert "history" in ctx


# ── BaseAgentNode result builders ───────────────────────────────────────


class TestResultBuilders:
    def test_build_result_returns_status(self):
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        result = node._build_result(AgentAction("done"), {}, _base_state())
        assert result["status"] == "done"

    def test_error_result(self):
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        result = node._error_result("something broke", _base_state())
        assert result["status"] == "failed"
        assert "something broke" in result["errors"][0]

    def test_exhausted_result(self):
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        result = node._exhausted_result(_base_state())
        assert result["status"] == "failed"
        assert "exhausted" in result["errors"][0].lower()


# ── BaseAgentNode._build_system_prompt ──────────────────────────────────


class TestBuildSystemPrompt:
    def test_includes_node_system_prompt(self):
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        prompt = node._build_system_prompt()
        assert "test agent" in prompt.lower()

    def test_includes_os_info(self):
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        prompt = node._build_system_prompt()
        assert "当前系统" in prompt

    def test_includes_rules(self):
        node = ConcreteAgentNode(llm_tool=_mock_llm())
        prompt = node._build_system_prompt()
        assert "JSON" in prompt
