"""Base Tool interface."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolInput(BaseModel):
    """Base class for all tool inputs."""

    pass


class ToolOutput(BaseModel):
    """Base class for all tool outputs."""

    success: bool
    data: dict[str, Any] = {}
    error: str = ""


class BaseTool(ABC):
    """Abstract base class for all external system tools."""

    name: str = "base_tool"
    description: str = ""

    @abstractmethod
    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Execute the tool. Pure IO, no business logic."""
        pass

    async def healthcheck(self) -> ToolOutput:
        """Check if the external service is reachable."""
        return ToolOutput(success=True, data={"status": "unknown"})
