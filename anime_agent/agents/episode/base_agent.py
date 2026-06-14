"""BaseAgentNode — abstract base class for all agent-driven nodes."""

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from anime_agent.tools.base import BaseTool
from anime_agent.tools.bash_tool import BashTool, BashToolInput
from anime_agent.tools.llm_tool import LLMToolInput
from anime_agent.utils.logger import logger


class AgentAction:
    """Represents a decision made by an agent node."""

    def __init__(self, action_type: str, params: dict[str, Any] | None = None):
        self.type = action_type
        self.params = params or {}

    def __repr__(self) -> str:
        return f"AgentAction(type={self.type!r}, params={self.params!r})"


class BaseAgentNode(ABC):
    """Abstract base class for all LLM-driven agent nodes.

    Subclasses must define:
    - NODE_NAME: str — unique node identifier
    - SYSTEM_PROMPT: str — LLM system prompt
    - ACTIONS: dict[str, str] — available action space {name: description}
    - _build_prompt(context, state) -> str — build the user prompt

    The base class provides:
    - Unified __call__ interface (LangGraph compatible)
    - LLM thinking loop with configurable max iterations
    - Tool execution (bash, domain tools)
    - Structured JSON output parsing
    - Short-term memory loading
    """

    NODE_NAME: str = ""
    SYSTEM_PROMPT: str = ""
    ACTIONS: dict[str, str] = {}
    MAX_LLM_CALLS: int = 3
    TIMEOUT_SECONDS: int = 90
    # Actions that terminate the thinking loop
    TERMINAL_ACTIONS: set[str] = {"done", "skip", "abort", "select", "organize", "schedule"}

    def __init__(
        self,
        llm_tool: BaseTool | None = None,
        bash_tool: BashTool | None = None,
        session_factory: Any = None,
    ):
        if llm_tool is None:
            from anime_agent.tools.llm_tool import LLMTool

            self.llm_tool: BaseTool = LLMTool()
        else:
            self.llm_tool = llm_tool
        self.bash_tool = bash_tool or BashTool()
        self.session_factory = session_factory

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Unified entry point for LangGraph integration."""
        logger.info("{} agent starting for episode {}", self.NODE_NAME, state.get("episode_number"))

        context = await self._load_context(state)

        for iteration in range(self.MAX_LLM_CALLS):
            logger.debug(
                "{} iteration {}/{}",
                self.NODE_NAME,
                iteration + 1,
                self.MAX_LLM_CALLS,
            )

            try:
                action = await self._think(context, state)
            except Exception as exc:
                logger.error("{} LLM call failed: {}", self.NODE_NAME, exc)
                return self._error_result(f"LLM error: {exc}", state)

            logger.info("{} decided: {}", self.NODE_NAME, action)

            result = await self._act(action, state)

            if self._is_terminal(action):
                return self._build_result(action, result, state)

            context = self._extend_context(context, action, result)

        logger.warning("{} exhausted {} iterations", self.NODE_NAME, self.MAX_LLM_CALLS)
        return self._exhausted_result(state)

    async def _think(self, context: dict[str, Any], state: dict[str, Any]) -> AgentAction:
        """Call LLM to decide the next action."""
        system_msg = self._build_system_prompt()
        user_prompt = self._build_prompt(context, state)

        actions_desc = "\n".join(f"- {k}: {v}" for k, v in self.ACTIONS.items())
        json_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": list(self.ACTIONS.keys()),
                    "description": "选择一个动作",
                },
                "reasoning": {
                    "type": "string",
                    "description": "你的推理过程",
                },
            },
            "required": ["action", "reasoning"],
        }
        # Add extra fields based on action type
        json_schema["properties"]["command"] = {
            "type": "string",
            "description": "bash命令（仅当需要执行命令时）",
        }
        json_schema["properties"]["info_hash"] = {
            "type": "string",
            "description": "选中的种子 hash（仅当选择 select 时）",
        }
        json_schema["properties"]["interval"] = {
            "type": "integer",
            "description": "重试间隔秒数（仅当选择 schedule 时）",
        }
        json_schema["properties"]["target_path"] = {
            "type": "string",
            "description": "目标文件路径（仅当需要指定路径时）",
        }

        full_system = f"""{system_msg}

可用动作：
{actions_desc}

你必须输出 JSON 格式（可以包裹在 ```json 代码块中）：
{json.dumps(json_schema, ensure_ascii=False, indent=2)}
"""
        result = await self.llm_tool.invoke(
            LLMToolInput(
                prompt=user_prompt,
                system_msg=full_system,
            )
        )

        if not result.success:
            raise RuntimeError(f"LLM call failed: {result.error}")

        parsed = self._parse_llm_output(result.data.get("text", ""))
        return AgentAction(
            action_type=parsed.get("action", "abort"),
            params={k: v for k, v in parsed.items() if k not in ("action", "reasoning")},
        )

    async def _act(self, action: AgentAction, state: dict[str, Any]) -> dict[str, Any]:
        """Execute an action. Override in subclasses for custom actions."""
        if action.type == "bash":
            command = action.params.get("command", "")
            if command:
                result = await self.bash_tool.invoke(BashToolInput(command=command))
                return {
                    "success": result.success,
                    "output": result.data.get("stdout", "")[:2000]
                    if result.success
                    else result.error,
                }
        return {"success": True, "output": "No action executed"}

    def _is_terminal(self, action: AgentAction) -> bool:
        """Check if this action terminates the thinking loop."""
        return action.type in self.TERMINAL_ACTIONS

    def _build_system_prompt(self) -> str:
        """Build the full system prompt with OS info."""
        import platform

        os_type = platform.system()
        return f"""{self.SYSTEM_PROMPT}

当前系统: {os_type}
{"使用 Windows 命令 (cmd.exe)" if os_type == "Windows" else "使用 Linux 命令 (sh)"}

重要规则：
1. 输出必须是 JSON 格式
2. 禁止执行任何泄露敏感信息的命令
3. 禁止外连（curl/wget/ssh等）
4. 禁止删除系统文件
5. 优先使用只读命令诊断"""

    @abstractmethod
    def _build_prompt(self, context: dict[str, Any], state: dict[str, Any]) -> str:
        """Build the user prompt for the LLM. Must be implemented by subclasses."""
        ...

    async def _load_context(self, state: dict[str, Any]) -> dict[str, Any]:
        """Load short-term memory and context. Override to add custom context."""
        return {"memory": []}

    def _extend_context(
        self, context: dict[str, Any], action: AgentAction, result: dict[str, Any]
    ) -> dict[str, Any]:
        """Extend context after an action. Override for custom context management."""
        if "history" not in context:
            context["history"] = []
        context["history"].append({"action": action.type, "result": result.get("output", "")[:200]})
        return context

    def _build_result(
        self, action: AgentAction, result: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        """Build the final result dict. Override in subclasses for custom results."""
        return {
            "status": action.type,
        }

    def _error_result(self, error: str, state: dict[str, Any]) -> dict[str, Any]:
        """Build an error result."""
        return {
            "status": "failed",
            "errors": [f"{self.NODE_NAME} agent error: {error}"],
            "_error_handler_node": self.NODE_NAME,
        }

    def _exhausted_result(self, state: dict[str, Any]) -> dict[str, Any]:
        """Build result when max iterations are exhausted."""
        return {
            "status": "failed",
            "errors": [f"{self.NODE_NAME} agent exhausted {self.MAX_LLM_CALLS} iterations"],
            "_error_handler_node": self.NODE_NAME,
        }

    @staticmethod
    def _parse_llm_output(text: str) -> dict[str, Any]:
        """Parse LLM output, extracting JSON from possible markdown code blocks."""
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)

        try:
            parsed = json.loads(text.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            try:
                parsed = json.loads(brace_match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        return {"action": "abort", "reasoning": f"Failed to parse: {text[:200]}"}
