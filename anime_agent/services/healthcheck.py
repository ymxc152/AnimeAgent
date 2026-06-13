"""Pre-flight health check aggregator for external tools."""

from dataclasses import dataclass, field

from anime_agent.tools.base import BaseTool, ToolOutput


@dataclass
class HealthReport:
    """Aggregated result of checking all registered tools."""

    healthy: bool
    checks: dict[str, ToolOutput] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class HealthCheck:
    """Run health checks across tools and produce a pre-flight report."""

    def __init__(
        self,
        tools: list[BaseTool],
        critical_tools: list[str] | None = None,
    ):
        self.tools = tools
        self.critical_tools = set(critical_tools or [])

    async def run(self) -> HealthReport:
        """Execute healthcheck on each tool and aggregate results."""
        if not self.tools:
            return HealthReport(
                healthy=False,
                errors=["No tools registered for health check"],
            )

        checks: dict[str, ToolOutput] = {}
        errors: list[str] = []

        for tool in self.tools:
            result = await tool.healthcheck()
            checks[tool.name] = result
            if not result.success and tool.name in self.critical_tools:
                errors.append(f"{tool.name}: {result.error}")

        return HealthReport(
            healthy=len(errors) == 0,
            checks=checks,
            errors=errors,
        )
