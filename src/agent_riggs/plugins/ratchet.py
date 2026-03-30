"""Ratchet plugin — stub."""
from __future__ import annotations
from typing import Any, Callable, TYPE_CHECKING
import click

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService

RATCHET_DDL = [
    """
    CREATE TABLE IF NOT EXISTS ratchet_decisions (
        decision_id     BIGINT PRIMARY KEY,
        decided_at      TIMESTAMPTZ NOT NULL,
        candidate_type  VARCHAR NOT NULL,
        candidate_key   VARCHAR NOT NULL,
        decision        VARCHAR NOT NULL,
        reason          VARCHAR,
        evidence        JSON,
        config_change   JSON
    )
    """,
]

class RatchetPlugin:
    name = "ratchet"
    def bind(self, service: RiggsService) -> None:
        self.service = service
    def schema_ddl(self) -> list[str]:
        return list(RATCHET_DDL)
    def cli_commands(self) -> list[click.Command]:
        return []
    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
