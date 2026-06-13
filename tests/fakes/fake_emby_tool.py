"""In-memory fake for EmbyTool used in end-to-end tests."""

from anime_agent.tools.base import BaseTool, ToolInput, ToolOutput
from anime_agent.tools.emby_tool import EmbyToolInput


class FakeEmbyTool(BaseTool):
    """Simulate Emby library refresh without a real server."""

    name = "emby"
    description = "Fake Emby tool for testing."

    def __init__(self):
        self.refreshes: list[str] = []

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Record the refresh request."""
        emby_input = EmbyToolInput.model_validate(input_data)
        self.refreshes.append(emby_input.action)
        return ToolOutput(success=True, data={"refreshed": True, "library_id": "fake-library"})

    async def healthcheck(self) -> ToolOutput:
        """Always healthy in tests."""
        return ToolOutput(success=True, data={"status": "ok"})
