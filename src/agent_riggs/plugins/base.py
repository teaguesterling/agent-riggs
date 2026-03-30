"""Plugin protocol for agent_riggs service layer."""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

import click

from agent_riggs.service import RiggsService


@runtime_checkable
class ServicePlugin(Protocol):
    """Protocol that all agent_riggs plugins implement."""

    name: str

    def bind(self, service: RiggsService) -> None:
        """Receive service reference for cross-plugin access."""
        ...

    def cli_commands(self) -> list[click.Command]:
        """Commands this plugin contributes to the CLI."""
        ...

    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        """(uri, handler) pairs for MCP resources."""
        ...

    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        """(name, handler) pairs for MCP tools."""
        ...

    def schema_ddl(self) -> list[str]:
        """DDL statements for tables this plugin owns."""
        ...
