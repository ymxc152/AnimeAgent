"""ErrorHandler node — generic Agent-driven error recovery for Episode Graph."""

import json
import re
from typing import Any

from anime_agent.agents.episode.error_prompts import NODE_PROMPTS, SYSTEM_SUFFIX
from anime_agent.tools.base import BaseTool
from anime_agent.tools.bash_tool import BashTool, BashToolInput
from anime_agent.tools.llm_tool import LLMToolInput
from anime_agent.utils.logger import logger

# Short-term memory: max error logs to include as context.
_MEMORY_LIMIT = 5


class ErrorHandlerNode:
    """Generic Agent error handler that uses LLM to diagnose and fix failures.

    When a node fails, this handler:
    1. Loads short-term memory (recent error logs for this episode)
    2. Builds a context-aware prompt with the failed node's specific guidance
    3. Asks LLM to choose an action: bash (execute repair), retry, skip, or abort
    4. Executes the chosen action, loops until resolved or exhausted
    """

    MAX_ITERATIONS = 5
    TIMEOUT_SECONDS = 180  # 3 minutes total

    def __init__(
        self,
        llm_tool: BaseTool | None = None,
        bash_tool: BaseTool | None = None,
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
        """Handle error recovery for the failed node."""
        failed_node = state.get("_error_handler_node", "unknown")
        errors = state.get("errors", [])
        # errors may contain HumanMessage objects or strings
        raw_error = errors[-1] if errors else "Unknown error"
        last_error = str(raw_error) if not isinstance(raw_error, str) else raw_error
        episode_id = state.get("subscription_id", 0)

        logger.info(
            "ErrorHandler activated for node={}, episode={}, error={}",
            failed_node,
            state.get("episode_number"),
            last_error[:200],
        )

        # Load short-term memory
        memory = await self._load_memory(episode_id)

        # Build prompt
        node_prompt = NODE_PROMPTS.get(failed_node, NODE_PROMPTS["__generic__"])
        bash_history: list[dict[str, Any]] = []

        for iteration in range(self.MAX_ITERATIONS):
            logger.info(
                "ErrorHandler iteration {}/{} for node={}",
                iteration + 1,
                self.MAX_ITERATIONS,
                failed_node,
            )

            try:
                action = await self._ask_llm(
                    node_prompt=node_prompt,
                    failed_node=failed_node,
                    last_error=last_error,
                    bash_history=bash_history,
                    memory=memory,
                )
            except Exception as exc:
                logger.error("LLM call failed in ErrorHandler: {}", exc)
                return {
                    "status": "failed",
                    "errors": [f"ErrorHandler LLM error: {exc}"],
                }

            action_type = action.get("action", "abort")
            reasoning = action.get("reasoning", "")

            logger.info(
                "ErrorHandler decided: action={}, reasoning={}",
                action_type,
                reasoning[:200],
            )

            if action_type == "bash":
                command = action.get("command", "")
                if not command:
                    logger.warning("LLM returned bash action without command")
                    bash_history.append({"command": "(empty)", "output": "No command provided"})
                    continue

                result = await self.bash_tool.invoke(BashToolInput(command=command))
                output = result.data.get("stdout", "") if result.success else result.error
                bash_history.append({
                    "command": command,
                    "output": output[:500],
                    "success": result.success,
                })
                last_error = output

            elif action_type == "retry":
                logger.info("ErrorHandler: retrying node={}", failed_node)
                return {
                    "status": f"retry_{failed_node}",
                    "_error_handler_resolved": True,
                }

            elif action_type == "skip":
                logger.info("ErrorHandler: skipping node={}", failed_node)
                return {
                    "status": "skipped",
                    "_error_handler_resolved": True,
                    "warnings": [f"ErrorHandler skipped {failed_node}: {reasoning}"],
                }

            elif action_type == "abort":
                logger.warning("ErrorHandler: abort for node={}: {}", failed_node, reasoning)
                return {
                    "status": "failed",
                    "errors": [f"ErrorHandler abort ({failed_node}): {reasoning}"],
                }

        # Exhausted all iterations
        logger.warning(
            "ErrorHandler exhausted {} attempts for node={}",
            self.MAX_ITERATIONS,
            failed_node,
        )
        return {
            "status": "failed",
            "errors": [
                f"ErrorHandler exhausted {self.MAX_ITERATIONS} attempts for {failed_node}. "
                f"Last error: {last_error[:200]}"
            ],
        }

    async def _ask_llm(
        self,
        node_prompt: str,
        failed_node: str,
        last_error: str,
        bash_history: list[dict[str, Any]],
        memory: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Ask LLM for the next error-handling action."""
        system_msg = node_prompt + "\n\n" + SYSTEM_SUFFIX

        history_text = ""
        if bash_history:
            history_text = "\n已执行的命令:\n"
            for i, h in enumerate(bash_history, 1):
                history_text += f"{i}. 命令: {h['command']}\n   结果: {h['output'][:200]}\n"

        memory_text = ""
        if memory:
            memory_text = "\n历史错误记忆:\n"
            for m in memory:
                memory_text += f"- [{m.get('node_name', '?')}] {m.get('error_message', '')[:100]} -> {m.get('resolution', '?')}\n"

        prompt = (
            f"节点 `{failed_node}` 执行失败。\n\n"
            f"当前错误:\n{last_error[:500]}\n"
            f"{history_text}"
            f"{memory_text}\n"
            f"请分析错误原因并选择下一步操作。输出 JSON 格式。"
        )

        result = await self.llm_tool.invoke(
            LLMToolInput(
                prompt=prompt,
                system_msg=system_msg,
                json_schema={
                    "type": "object",
                    "properties": {
                        "reasoning": {"type": "string", "description": "你的分析"},
                        "action": {"type": "string", "enum": ["bash", "retry", "skip", "abort"]},
                        "command": {"type": "string", "description": "bash命令（仅action=bash时）"},
                    },
                    "required": ["reasoning", "action"],
                },
            )
        )

        if not result.success:
            raise RuntimeError(f"LLM call failed: {result.error}")

        return self._parse_llm_output(result.data.get("text", ""))

    @staticmethod
    def _parse_llm_output(text: str) -> dict[str, Any]:
        """Parse LLM output, extracting JSON from possible markdown code blocks."""
        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)

        # Try parsing as JSON directly
        try:
            parsed = json.loads(text.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in text
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            try:
                parsed = json.loads(brace_match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Fallback: return abort with the raw text as reasoning
        return {
            "reasoning": f"Failed to parse LLM output: {text[:200]}",
            "action": "abort",
        }

    async def _load_memory(self, episode_id: int) -> list[dict[str, Any]]:
        """Load recent error logs for short-term memory."""
        if not self.session_factory or not episode_id:
            return []
        try:
            from anime_agent.memory.store import Store
            async with self.session_factory() as session:
                store = Store(session)
                logs = await store.error_logs.list_recent(episode_id, limit=_MEMORY_LIMIT)
                return [
                    {
                        "node_name": log.node_name,
                        "error_message": log.error_message,
                        "resolution": log.resolution,
                        "created_at": log.created_at.isoformat() if log.created_at else None,
                    }
                    for log in logs
                ]
        except Exception as exc:
            logger.warning("Failed to load error memory: {}", exc)
            return []
