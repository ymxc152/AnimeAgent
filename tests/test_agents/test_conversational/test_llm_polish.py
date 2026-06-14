"""Tests for LLM polish layer in conversational reply."""

from unittest.mock import AsyncMock, MagicMock

from anime_agent.agents.conversational.reply import llm_polish
from anime_agent.tools.base import ToolOutput


async def test_llm_polish_returns_polished_text():
    """LLM polish should return LLM-generated text when available."""
    llm_tool = MagicMock()
    llm_tool.invoke = AsyncMock(
        return_value=ToolOutput(success=True, data={"text": "你正在追1部番剧。"})
    )

    result = await llm_polish(
        llm_tool,
        user_input="我在追哪些？",
        structured_reply="你当前在追的番剧：\n- 《Test》：1/12 集已完成",
        data=[{"title": "Test", "total_episodes": 12, "completed": 1}],
    )

    assert result == "你正在追1部番剧。"
    llm_tool.invoke.assert_called_once()


async def test_llm_polish_falls_back_on_error():
    """LLM polish should fall back to structured reply on LLM error."""
    llm_tool = MagicMock()
    llm_tool.invoke = AsyncMock(side_effect=Exception("LLM unavailable"))

    structured = "你当前在追的番剧：\n- 《Test》：1/12 集已完成"
    result = await llm_polish(
        llm_tool,
        user_input="我在追哪些？",
        structured_reply=structured,
        data=[{"title": "Test"}],
    )

    assert result == structured


async def test_llm_polish_falls_back_on_empty_response():
    """LLM polish should fall back when LLM returns empty text."""
    llm_tool = MagicMock()
    llm_tool.invoke = AsyncMock(return_value=ToolOutput(success=True, data={"text": ""}))

    structured = "模板回复"
    result = await llm_polish(
        llm_tool,
        user_input="测试",
        structured_reply=structured,
        data=None,
    )

    assert result == structured


async def test_llm_polish_includes_history():
    """LLM polish should include conversation history in the prompt."""
    llm_tool = MagicMock()
    llm_tool.invoke = AsyncMock(return_value=ToolOutput(success=True, data={"text": "回复"}))

    history = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！"},
    ]

    await llm_polish(
        llm_tool,
        user_input="我在追哪些？",
        structured_reply="列表...",
        data=[],
        history=history,
    )

    call_args = llm_tool.invoke.call_args[0][0]
    assert "你好" in call_args.prompt
    assert "你好！" in call_args.prompt
