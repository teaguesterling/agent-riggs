"""Lackpy ingest source — reads .lackpy/traces.jsonl delegation traces."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent_riggs.trust.events import EventCategory, TurnEvent

# Generation tiers that don't require model inference
_STRUCTURED_TIERS = frozenset({"templates", "rules"})


class LackpySource:
    name = "lackpy"

    def discover(self, project_root: Path) -> bool:
        return (project_root / ".lackpy" / "traces.jsonl").exists()

    def read_events(
        self, project_root: Path, since: datetime | None
    ) -> list[TurnEvent]:
        log_path = project_root / ".lackpy" / "traces.jsonl"
        if not log_path.exists():
            return []

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
                events.append(TurnEvent(
                    session_id=f"lackpy-{ts.strftime('%Y%m%d')}",
                    turn_number=i + 1,
                    timestamp=ts,
                    tool_name="lackpy.delegate",
                    tool_success=entry.get("success", False),
                    mode=None,
                    event_category=self._classify(entry),
                    metadata=entry,
                ))
        return events

    def _classify(self, entry: dict) -> EventCategory:
        if not entry.get("success", False):
            return EventCategory.FAILURE
        tier = entry.get("generation_tier", "")
        if tier in _STRUCTURED_TIERS:
            return EventCategory.SUCCESS
        return EventCategory.SUBOPTIMAL

    def _parse_timestamp(self, ts_str: str) -> datetime:
        if not ts_str:
            return datetime.now(timezone.utc)
        ts_str = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str)
