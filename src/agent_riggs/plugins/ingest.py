"""Ingest plugin — wires ingest pipeline into the service layer."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

import click

from agent_riggs.ingest.pipeline import IngestResult, ingest
from agent_riggs.ingest.sources.blq import BlqSource
from agent_riggs.ingest.sources.fledgling import FledglingSource
from agent_riggs.ingest.sources.kibitzer import KibitzerSource
from agent_riggs.ingest.sources.lackpy import LackpySource

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService


class IngestPlugin:
    name = "ingest"

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

    def run(self, since: datetime | None = None) -> IngestResult:
        sources = self._discover_sources()
        return ingest(
            store=self.service.store,
            project_root=self.service.project_root,
            sources=sources,
            trust_config=self.service.config.trust,
            since=since,
        )

    def _discover_sources(self) -> list[Any]:
        return [BlqSource(), FledglingSource(), KibitzerSource(), LackpySource()]
