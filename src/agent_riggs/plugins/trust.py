"""Trust plugin — wires trust engine into the service layer."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService

TRUST_DDL = [
    """
    CREATE TABLE IF NOT EXISTS turns (
        turn_id         BIGINT PRIMARY KEY,
        session_id      VARCHAR NOT NULL,
        project         VARCHAR NOT NULL,
        turn_number     INTEGER NOT NULL,
        timestamp       TIMESTAMPTZ NOT NULL,
        tool_name       VARCHAR,
        tool_success    BOOLEAN,
        mode            VARCHAR,
        trust_score     DOUBLE,
        trust_1         DOUBLE,
        trust_5         DOUBLE,
        trust_15        DOUBLE,
        event_category  VARCHAR,
        metadata        JSON
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS failure_stream (
        failure_id       BIGINT PRIMARY KEY,
        turn_id          BIGINT,
        session_id       VARCHAR NOT NULL,
        project          VARCHAR NOT NULL,
        occurred_at      TIMESTAMPTZ NOT NULL,
        failure_category VARCHAR NOT NULL,
        tool_name        VARCHAR,
        mode             VARCHAR,
        trust_at_failure DOUBLE,
        detail           JSON
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS session_summaries (
        session_id      VARCHAR PRIMARY KEY,
        project         VARCHAR NOT NULL,
        started_at      TIMESTAMPTZ,
        ended_at        TIMESTAMPTZ,
        duration        INTERVAL,
        total_turns     INTEGER,
        total_failures  INTEGER,
        failure_rate    DOUBLE,
        trust_start     DOUBLE,
        trust_end       DOUBLE,
        trust_delta     DOUBLE,
        modes_used      VARCHAR[],
        mode_switches   INTEGER,
        computation_channel_fraction DOUBLE,
        structured_tool_fraction     DOUBLE
    )
    """,
]

_FAILURE_CATEGORIES = frozenset({
    "failure", "path_denial", "edit_failure", "repeated_failure",
    "timeout", "mode_forced", "sandbox_violation", "trust_drop",
})


class TrustPlugin:
    name = "trust"

    def bind(self, service: RiggsService) -> None:
        self.service = service
        self.store = service.store
        self.config = service.config.trust

    def schema_ddl(self) -> list[str]:
        return list(TRUST_DDL)

    def cli_commands(self) -> list[click.Command]:
        return []

    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return [("riggs://trust", self._trust_resource)]

    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return [("RiggsTrust", self._trust_tool)]

    def current(self) -> dict[str, Any]:
        """Get the most recent trust scores for the current project."""
        row = self.store.execute(
            """
            SELECT trust_1, trust_5, trust_15, session_id, turn_number
            FROM turns
            WHERE project = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            [self._project_name()],
        ).fetchone()
        if row is None:
            return {"trust_1": 1.0, "trust_5": 1.0, "trust_15": 1.0, "has_data": False}
        return {
            "trust_1": row[0],
            "trust_5": row[1],
            "trust_15": row[2],
            "session_id": row[3],
            "turn_number": row[4],
            "has_data": True,
        }

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get trust score history."""
        rows = self.store.execute(
            """
            SELECT trust_1, trust_5, trust_15, session_id, turn_number, timestamp
            FROM turns
            WHERE project = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            [self._project_name(), limit],
        ).fetchall()
        return [
            {
                "trust_1": r[0], "trust_5": r[1], "trust_15": r[2],
                "session_id": r[3], "turn_number": r[4], "timestamp": r[5],
            }
            for r in rows
        ]

    def _project_name(self) -> str:
        return self.service.project_root.name

    def _trust_resource(self) -> str:
        data = self.current()
        if not data["has_data"]:
            return "No trust data yet. Run `agent-riggs ingest` after a session."
        return (
            f"trust: {data['trust_1']:.2f} / {data['trust_5']:.2f} / {data['trust_15']:.2f}\n"
            f"       now    session  baseline"
        )

    def _trust_tool(self, window: int | None = None) -> dict[str, Any]:
        if window:
            return {"current": self.current(), "history": self.history(limit=window)}
        return {"current": self.current()}
