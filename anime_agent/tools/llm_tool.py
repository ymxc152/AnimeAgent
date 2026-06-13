"""LLM tool wrapping OpenAI / Ollama via LangChain ChatOpenAI."""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from anime_agent.config import settings
from anime_agent.tools.base import BaseTool, ToolInput, ToolOutput


class LLMToolInput(ToolInput):
    """Input for LLMTool."""

    prompt: str
    system_msg: str | None = None
    json_schema: dict[str, Any] | None = None
    temperature: float = 0.7


class LLMTool(BaseTool):
    """Call an LLM and return text or structured JSON."""

    name = "llm"
    description = "Invoke an OpenAI/Ollama-compatible LLM for decision making."

    def __init__(self, chat_model: BaseChatModel | None = None):
        self.chat_model = chat_model

    def _get_model(self) -> BaseChatModel:
        if self.chat_model is not None:
            return self.chat_model
        if settings.llm_provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required for openai provider")
            return ChatOpenAI(
                model=settings.openai_model,
                api_key=SecretStr(settings.openai_api_key),
                base_url=settings.openai_base_url,
                temperature=0.7,
            )
        # Ollama via OpenAI-compatible API
        return ChatOpenAI(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            api_key=SecretStr("ollama"),
            temperature=0.7,
        )

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Send prompt to LLM and return text or structured JSON."""
        llm_input = LLMToolInput.model_validate(input_data)
        model = self._get_model()

        messages: list[BaseMessage] = []
        if llm_input.system_msg:
            messages.append(SystemMessage(content=llm_input.system_msg))
        messages.append(HumanMessage(content=llm_input.prompt))

        try:
            response = await model.ainvoke(messages)
            raw_content = response.content

            # Normalize content to a single string for downstream processing.
            if isinstance(raw_content, str):
                content = raw_content
            elif isinstance(raw_content, list):
                content = "".join(
                    str(part) for part in raw_content
                )
            else:
                content = str(raw_content)

            # If json_schema requested, try to parse JSON from the response
            if llm_input.json_schema:
                import json
                import re
                # Try to extract JSON from markdown code blocks or raw text
                json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    # Try raw JSON
                    json_match = re.search(r"\{.*\}", content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                    else:
                        return ToolOutput(success=False, error=f"No JSON found in LLM response: {content}")

                try:
                    json_result = json.loads(json_str)
                    return ToolOutput(success=True, data={"json": json_result})
                except json.JSONDecodeError as exc:
                    return ToolOutput(success=False, error=f"Invalid JSON in LLM response: {exc}")

            return ToolOutput(success=True, data={"text": content})
        except Exception as exc:  # noqa: BLE001
            return ToolOutput(success=False, error=f"LLM call failed: {exc}")
