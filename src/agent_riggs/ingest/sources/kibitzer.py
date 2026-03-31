"""Kibitzer ingest source — reads .kibitzer/state.json and intercept.log."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from agent_riggs.trust.events import EventCategory, TurnEvent


class KibitzerSource:
    name = "kibitzer"

    def discover(self, project_root: Path) -> bool:
        return (project_root / ".kibitzer" / "state.json").exists()

    def read_events(self, project_root: Path, since: datetime | None) -> list[TurnEvent]:
        events: list[TurnEvent] = []
        state = self._read_state(project_root)
        session_id = state.get("session_id", "unknown")
        mode = state.get("mode")

        log_path = project_root / ".kibitzer" / "intercept.log"
        if log_path.exists():
            events.extend(self._parse_intercept_log(log_path, session_id, mode, since))

        return events

    def _read_state(self, project_root: Path) -> dict:
        state_path = project_root / ".kibitzer" / "state.json"
        if state_path.exists():
            return json.loads(state_path.read_text())
        return {}

    def _parse_intercept_log(
        self,
        log_path: Path,
        session_id: str,
        mode: str | None,
        since: datetime | None,
    ) -> list[TurnEvent]:
        events: list[TurnEvent] = []
        with log_path.open() as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                ts = self._parse_timestamp(entry.get("timestamp", ""))
                if since and ts < since:
                    continue
                events.append(
                    TurnEvent(
                        session_id=session_id,
                        turn_number=i + 1,
                        timestamp=ts,
                        tool_name=entry.get("tool"),
                        tool_success=entry.get("success"),
                        mode=mode,
                        event_category=self._classify(entry),
                        metadata=entry,
                    )
                )
        return events

    def _classify(self, entry: dict) -> EventCategory:
        if entry.get("success") is False:
            return EventCategory.FAILURE
        if entry.get("suggestion"):
            return EventCategory.SUBOPTIMAL
        if entry.get("action") == "redirect":
            return EventCategory.SUBOPTIMAL
        return EventCategory.SUCCESS

    def _parse_timestamp(self, ts_str: str) -> datetime:
        if not ts_str:
            return datetime.now(UTC)
        ts_str = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str)
