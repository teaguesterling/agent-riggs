"""Briefing plugin — session and project briefings."""
from __future__ import annotations
from typing import Any, Callable, TYPE_CHECKING
import click
from agent_riggs.briefing.session import SessionBriefing, generate_briefing

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService


class BriefingPlugin:
    name = "briefing"

    def bind(self, service: "RiggsService") -> None:
        self.service = service

    def schema_ddl(self) -> list[str]:
        return []

    def cli_commands(self) -> list[click.Command]:
        return []

    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return [("riggs://briefing", self._briefing_resource)]

    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return []

    def brief(self) -> SessionBriefing:
        return generate_briefing(self.service.store, self.service.project_root.name, self.service.config)

    def _briefing_resource(self) -> str:
        return self.brief().format()
