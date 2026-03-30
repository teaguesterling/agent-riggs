"""Metrics plugin — stub."""
from __future__ import annotations
from typing import Any, Callable, TYPE_CHECKING
import click

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService

class MetricsPlugin:
    name = "metrics"
    def bind(self, service: RiggsService) -> None:
        self.service = service
    def schema_ddl(self) -> list[str]:
        return []
    def cli_commands(self) -> list[click.Command]:
        return []
    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
