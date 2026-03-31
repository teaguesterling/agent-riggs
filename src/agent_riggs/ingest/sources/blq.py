"""blq ingest source — reads .bird/blq.duckdb build/test execution data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from agent_riggs.trust.events import EventCategory, TurnEvent


class BlqSource:
    name = "blq"

    def discover(self, project_root: Path) -> bool:
        return (project_root / ".bird" / "blq.duckdb").exists()

    def read_events(
        self, project_root: Path, since: datetime | None
    ) -> list[TurnEvent]:
        db_path = project_root / ".bird" / "blq.duckdb"
        if not db_path.exists():
            return []

        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            return self._query_invocations(conn, since)
        finally:
            conn.close()

    def _query_invocations(
        self, conn: duckdb.DuckDBPyConnection, since: datetime | None
    ) -> list[TurnEvent]:
        query = """
            SELECT
                id, session_id, timestamp, cmd, executable,
                exit_code, duration_ms, source_name
            FROM invocations
            WHERE 1=1
        """
        params: list = []
        if since:
            query += " AND timestamp >= ?"
            params.append(since)
        query += " ORDER BY timestamp ASC"

        rows = conn.execute(query, params).fetchall()
        events: list[TurnEvent] = []
        for i, row in enumerate(rows):
            inv_id, session_id, ts, cmd, executable, exit_code, duration_ms, source_name = row
            category = self._classify(exit_code)
            events.append(TurnEvent(
                session_id=session_id or f"blq-{ts.strftime('%Y%m%d') if ts else 'unknown'}",
                turn_number=i + 1,
                timestamp=ts if ts else datetime.now(timezone.utc),
                tool_name=f"blq.{source_name or executable or 'run'}",
                tool_success=exit_code == 0 if exit_code is not None else None,
                mode=None,
                event_category=category,
                metadata={
                    "cmd": cmd,
                    "exit_code": exit_code,
                    "duration_ms": duration_ms,
                    "source": "blq",
                    "invocation_id": str(inv_id),
                },
            ))
        return events

    def _classify(self, exit_code: int | None) -> EventCategory:
        if exit_code is None:
            return EventCategory.FAILURE
        if exit_code == 0:
            return EventCategory.SUCCESS
        return EventCategory.FAILURE
