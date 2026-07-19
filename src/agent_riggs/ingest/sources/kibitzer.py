"""Kibitzer ingest source — reads .kibitzer/state.json and intercept.log.

Provenance: SELF_REPORTED. The intercept log lives in the project tree and
its ``success`` field is supplied by the scored session, so it is treated as
an unverified claim — it can hold or lower trust, never raise it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from agent_riggs.ingest.sources.base import Cursor, SourceBatch, read_new_lines
from agent_riggs.trust.events import EventCategory, Provenance, TurnEvent


class KibitzerSource:
    name = "kibitzer"

    def discover(self, project_root: Path) -> bool:
        return (project_root / ".kibitzer" / "state.json").exists()

    def read_events(self, project_root: Path, cursor: Cursor | None) -> SourceBatch:
        state = self._read_state(project_root)
        session_id = state.get("session_id", "unknown")
        mode = state.get("mode")

        offset = (cursor or {}).get("intercept_lines", 0)
        events: list[TurnEvent] = []

        log_path = project_root / ".kibitzer" / "intercept.log"
        if log_path.exists():
            events, offset = self._parse_intercept_log(log_path, session_id, mode, offset)

        return SourceBatch(events=events, cursor={"intercept_lines": offset})

    def _read_state(self, project_root: Path) -> dict:
        state_path = project_root / ".kibitzer" / "state.json"
        try:
            state = json.loads(state_path.read_text())
        except (OSError, json.JSONDecodeError):
            return {}
        return state if isinstance(state, dict) else {}

    def _parse_intercept_log(
        self,
        log_path: Path,
        session_id: str,
        mode: str | None,
        offset: int,
    ) -> tuple[list[TurnEvent], int]:
        events: list[TurnEvent] = []
        lines, total = read_new_lines(log_path, offset)
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            # One malformed (subject-controlled) line must not abort ingest.
            try:
                entry = json.loads(line)
                if not isinstance(entry, dict):
                    continue
                ts = self._parse_timestamp(entry.get("timestamp", ""))
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
            digest = hashlib.sha256(line.encode()).hexdigest()[:16]
            events.append(
                TurnEvent(
                    session_id=session_id,
                    turn_number=offset + i + 1,
                    timestamp=ts,
                    tool_name=entry.get("tool") or ("Bash" if entry.get("bash_command") else None),
                    tool_success=entry.get("success"),
                    mode=mode,
                    event_category=self._classify(entry),
                    metadata=entry,
                    provenance=Provenance.SELF_REPORTED,
                    event_uid=f"kibitzer:{offset + i}:{digest}",
                )
            )
        return events, total

    def _classify(self, entry: dict) -> EventCategory:
        if entry.get("success") is False:
            return EventCategory.FAILURE
        # An intercepted bash command with a suggested structured alternative
        # is a bypass — record it as suboptimal, not success.
        if entry.get("suggestion") or entry.get("suggested_tool"):
            return EventCategory.SUBOPTIMAL
        if entry.get("action") == "redirect":
            return EventCategory.SUBOPTIMAL
        return EventCategory.SUCCESS

    def _parse_timestamp(self, ts_str: str) -> datetime:
        if not ts_str:
            return datetime.now(UTC)
        ts_str = str(ts_str).replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str)
