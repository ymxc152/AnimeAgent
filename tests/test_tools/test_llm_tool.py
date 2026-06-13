"""Tests for LLMTool."""

from unittest.mock import AsyncMock, MagicMock

from anime_agent.tools.llm_tool import LLMTool, LLMToolInput


async def test_llm_tool_returns_text_response():
    """LLMTool should return the LLM text response."""
    mock_response = MagicMock()
    mock_response.content = "Hello, world!"

    mock_model = MagicMock()
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    tool = LLMTool(chat_model=mock_model)
    result = await tool.invoke(LLMToolInput(prompt="Say hi"))

    assert result.success is True
    assert result.data["text"] == "Hello, world!"
    mock_model.ainvoke.assert_awaited_once()


async def test_llm_tool_uses_system_message():
    """LLMTool should pass system_msg to the chat model."""
    mock_response = MagicMock()
    mock_response.content = "OK"

    mock_model = MagicMock()
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    tool = LLMTool(chat_model=mock_model)
    result = await tool.invoke(
        LLMToolInput(prompt="Hi", system_msg="You are a helpful assistant.")
    )

    assert result.success is True
    call_args = mock_model.ainvoke.call_args[0][0]
    assert len(call_args) == 2
    assert call_args[0].type == "system"
    assert call_args[0].content == "You are a helpful assistant."
    assert call_args[1].type == "human"
    assert call_args[1].content == "Hi"


async def test_llm_tool_returns_structured_json():
    """LLMTool should return parsed JSON when json_schema is provided."""
    schema = {
        "type": "object",
        "properties": {"matched": {"type": "boolean"}, "confidence": {"type": "number"}},
        "required": ["matched", "confidence"],
    }

    mock_response = MagicMock()
    mock_response.content = '{"matched": true, "confidence": 0.95}'

    mock_model = MagicMock()
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    tool = LLMTool(chat_model=mock_model)
    result = await tool.invoke(LLMToolInput(prompt="Match this torrent", json_schema=schema))

    assert result.success is True
    assert result.data["json"] == {"matched": True, "confidence": 0.95}


async def test_llm_tool_returns_error_on_failure():
    """LLMTool should return a failed ToolOutput when the model raises."""
    mock_model = MagicMock()
    mock_model.ainvoke = AsyncMock(side_effect=Exception("API error"))

    tool = LLMTool(chat_model=mock_model)
    result = await tool.invoke(LLMToolInput(prompt="Hi"))

    assert result.success is False
    assert "API error" in result.error
