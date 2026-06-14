"""Extended tests for LLMTool — model selection, JSON parsing, content normalization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anime_agent.tools.llm_tool import LLMTool, LLMToolInput

# ── Model selection ─────────────────────────────────────────────────────


class TestGetModel:
    def test_returns_preconfigured_model(self):
        mock_model = MagicMock()
        tool = LLMTool(chat_model=mock_model)
        assert tool._get_model() is mock_model

    def test_raises_when_openai_key_missing(self):
        tool = LLMTool()
        with patch("anime_agent.tools.llm_tool.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.openai_api_key = ""
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                tool._get_model()

    def test_creates_openai_model(self):
        tool = LLMTool()
        with patch("anime_agent.tools.llm_tool.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.openai_api_key = "sk-test123"
            mock_settings.openai_model = "gpt-4"
            mock_settings.openai_base_url = None
            model = tool._get_model()
            assert model is not None

    def test_creates_ollama_model(self):
        tool = LLMTool()
        with patch("anime_agent.tools.llm_tool.settings") as mock_settings:
            mock_settings.llm_provider = "ollama"
            mock_settings.ollama_model = "llama3"
            mock_settings.ollama_base_url = "http://localhost:11434/v1"
            model = tool._get_model()
            assert model is not None


# ── invoke ──────────────────────────────────────────────────────────────


class TestLLMToolInvoke:
    async def test_returns_text_response(self):
        mock_response = MagicMock()
        mock_response.content = "Hello, world!"

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response

        tool = LLMTool(chat_model=mock_model)
        result = await tool.invoke(LLMToolInput(prompt="Hi"))

        assert result.success is True
        assert result.data["text"] == "Hello, world!"

    async def test_handles_list_content(self):
        mock_response = MagicMock()
        mock_response.content = ["Hello", " ", "world"]

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response

        tool = LLMTool(chat_model=mock_model)
        result = await tool.invoke(LLMToolInput(prompt="Hi"))

        assert result.success is True
        assert result.data["text"] == "Hello world"

    async def test_handles_non_string_content(self):
        mock_response = MagicMock()
        mock_response.content = 42

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response

        tool = LLMTool(chat_model=mock_model)
        result = await tool.invoke(LLMToolInput(prompt="Hi"))

        assert result.success is True
        assert result.data["text"] == "42"

    async def test_includes_system_message(self):
        mock_response = MagicMock()
        mock_response.content = "OK"

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response

        tool = LLMTool(chat_model=mock_model)
        await tool.invoke(LLMToolInput(prompt="Hi", system_msg="You are helpful"))

        call_args = mock_model.ainvoke.call_args[0][0]
        assert len(call_args) == 2
        assert call_args[0].content == "You are helpful"
        assert call_args[1].content == "Hi"

    async def test_handles_llm_exception(self):
        mock_model = AsyncMock()
        mock_model.ainvoke.side_effect = Exception("API error")

        tool = LLMTool(chat_model=mock_model)
        result = await tool.invoke(LLMToolInput(prompt="Hi"))

        assert result.success is False
        assert "API error" in result.error


# ── JSON parsing ────────────────────────────────────────────────────────


class TestLLMToolJSON:
    async def test_parses_json_from_code_block(self):
        mock_response = MagicMock()
        mock_response.content = '```json\n{"action": "done", "reasoning": "ok"}\n```'

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response

        tool = LLMTool(chat_model=mock_model)
        result = await tool.invoke(LLMToolInput(prompt="Hi", json_schema={"type": "object"}))

        assert result.success is True
        assert result.data["json"]["action"] == "done"

    async def test_parses_raw_json(self):
        mock_response = MagicMock()
        mock_response.content = '{"action": "skip", "reasoning": "test"}'

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response

        tool = LLMTool(chat_model=mock_model)
        result = await tool.invoke(LLMToolInput(prompt="Hi", json_schema={"type": "object"}))

        assert result.success is True
        assert result.data["json"]["action"] == "skip"

    async def test_returns_error_when_no_json_found(self):
        mock_response = MagicMock()
        mock_response.content = "I don't have JSON for you."

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response

        tool = LLMTool(chat_model=mock_model)
        result = await tool.invoke(LLMToolInput(prompt="Hi", json_schema={"type": "object"}))

        assert result.success is False
        assert "No JSON found" in result.error

    async def test_returns_error_on_invalid_json(self):
        mock_response = MagicMock()
        mock_response.content = '```json\n{invalid json}\n```'

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response

        tool = LLMTool(chat_model=mock_model)
        result = await tool.invoke(LLMToolInput(prompt="Hi", json_schema={"type": "object"}))

        assert result.success is False
        assert "Invalid JSON" in result.error


# ── Healthcheck ─────────────────────────────────────────────────────────


class TestLLMToolHealthcheck:
    async def test_healthcheck_returns_ok(self):
        tool = LLMTool()
        result = await tool.healthcheck()
        assert result.success is True
