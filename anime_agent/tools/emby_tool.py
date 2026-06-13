"""Emby tool for refreshing media libraries."""

from typing import Any

import httpx

from anime_agent.config import settings
from anime_agent.tools.base import BaseTool, ToolInput, ToolOutput


class EmbyToolInput(ToolInput):
    """Input for EmbyTool."""

    action: str  # refresh_all / refresh_library


class EmbyTool(BaseTool):
    """Interface with Emby REST API to refresh media libraries."""

    name = "emby"
    description = "Refresh Emby media libraries after files are organized."

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        host: str | None = None,
        api_key: str | None = None,
        library_name: str | None = None,
    ):
        self.client = client or httpx.AsyncClient(timeout=10.0)
        self.host = (host if host is not None else settings.emby_host).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.emby_api_key
        self.library_name = library_name if library_name is not None else settings.emby_library_name

    def _auth_params(self) -> dict[str, Any]:
        return {"api_key": self.api_key}

    async def healthcheck(self) -> ToolOutput:
        """Check Emby server reachability via the public info endpoint."""
        url = f"{self.host}/emby/System/Info/Public"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolOutput(success=False, error=f"Emby healthcheck failed: {exc}")
        return ToolOutput(success=True, data={"status": "ok"})

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Refresh all libraries or a specific library."""
        emby_input = EmbyToolInput.model_validate(input_data)

        if not self.api_key:
            return ToolOutput(success=False, error="Emby api key is required")

        if emby_input.action == "refresh_all":
            return await self._refresh_all()
        if emby_input.action == "refresh_library":
            return await self._refresh_library()

        return ToolOutput(success=False, error=f"Unknown action: {emby_input.action}")

    async def _refresh_all(self) -> ToolOutput:
        url = f"{self.host}/emby/Library/Refresh"
        try:
            response = await self.client.post(url, params=self._auth_params())
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolOutput(success=False, error=f"Emby refresh all failed: {exc}")
        return ToolOutput(success=True, data={"refreshed": True})

    async def _refresh_library(self) -> ToolOutput:
        library_id = await self._find_library_id(self.library_name)
        if library_id is None:
            return ToolOutput(
                success=False,
                error=f"Emby library '{self.library_name}' not found",
            )

        url = f"{self.host}/emby/Items/{library_id}/Refresh"
        try:
            response = await self.client.post(
                url,
                params={
                    **self._auth_params(),
                    "Recursive": "true",
                    "MetadataRefreshMode": "Default",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolOutput(success=False, error=f"Emby refresh library failed: {exc}")
        return ToolOutput(success=True, data={"refreshed": True, "library_id": library_id})

    async def _find_library_id(self, name: str) -> str | None:
        """Find library ID by name."""
        url = f"{self.host}/emby/Library/SelectableMediaFolders"
        try:
            response = await self.client.get(url, params=self._auth_params())
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        data = response.json()
        for item in data:
            if item.get("Name") == name:
                return str(item.get("Id"))
        return None
