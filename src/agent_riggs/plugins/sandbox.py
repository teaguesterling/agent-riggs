"""Sandbox plugin — stub."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService

SANDBOX_DDL = [
    """
    CREATE TABLE IF NOT EXISTS sandbox_profiles (
        command         VARCHAR NOT NULL,
        project         VARCHAR NOT NULL,
        updated_at      TIMESTAMPTZ NOT NULL,
        total_runs      INTEGER,
        memory_p50      BIGINT,
        memory_p95      BIGINT,
        memory_max      BIGINT,
        duration_p50    INTERVAL,
        duration_p95    INTERVAL,
        duration_max    INTERVAL,
        current_spec    JSON,
        current_grade_w VARCHAR,
        current_effects_ceiling INTEGER,
        PRIMARY KEY (command, project)
    )
    """,
]

class SandboxPlugin:
    name = "sandbox"
    def bind(self, service: RiggsService) -> None:
        self.service = service
    def schema_ddl(self) -> list[str]:
        return list(SANDBOX_DDL)
    def cli_commands(self) -> list[click.Command]:
        return []
    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
