"""Tests for the pre-flight health check aggregator."""

from unittest.mock import AsyncMock

from anime_agent.services.healthcheck import HealthCheck
from anime_agent.tools.base import BaseTool, ToolOutput


class _FakeTool(BaseTool):
    name = "fake_tool"

    async def invoke(self, input_data):
        return ToolOutput(success=True)


async def test_healthcheck_passes_when_all_tools_healthy():
    """Aggregator reports healthy when every tool healthcheck succeeds."""
    tool = _FakeTool()
    tool.healthcheck = AsyncMock(return_value=ToolOutput(success=True, data={"status": "ok"}))

    checker = HealthCheck(tools=[tool])
    report = await checker.run()

    assert report.healthy is True
    assert report.checks["fake_tool"].success is True


async def test_healthcheck_fails_when_critical_tool_unhealthy():
    """Aggregator reports unhealthy when a critical tool fails its healthcheck."""
    healthy = _FakeTool()
    healthy.name = "healthy"
    healthy.healthcheck = AsyncMock(
        return_value=ToolOutput(success=True, data={"status": "ok"})
    )

    critical = _FakeTool()
    critical.name = "critical"
    critical.healthcheck = AsyncMock(
        return_value=ToolOutput(success=False, error="connection refused")
    )

    checker = HealthCheck(tools=[healthy, critical], critical_tools=["critical"])
    report = await checker.run()

    assert report.healthy is False
    assert "critical" in report.errors[0]


async def test_healthcheck_ignores_optional_tool_failures():
    """Optional tool failures do not make the overall report unhealthy."""
    optional = _FakeTool()
    optional.name = "optional"
    optional.healthcheck = AsyncMock(
        return_value=ToolOutput(success=False, error="optional down")
    )

    checker = HealthCheck(tools=[optional], critical_tools=[])
    report = await checker.run()

    assert report.healthy is True
    assert report.checks["optional"].success is False


async def test_healthcheck_requires_at_least_one_tool():
    """Running healthcheck with no tools is considered unhealthy."""
    checker = HealthCheck(tools=[])
    report = await checker.run()

    assert report.healthy is False
    assert "no tools" in report.errors[0].lower()
