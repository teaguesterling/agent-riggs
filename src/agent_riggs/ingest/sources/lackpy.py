"""Lackpy ingest source — reads .lackpy/traces.jsonl delegation traces.

Provenance: SELF_REPORTED. The traces file lives in the project tree and its
``success`` field is not independently verified, so it can hold or lower
trust but never raise it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from agent_riggs.ingest.sources.base import Cursor, SourceBatch, read_new_lines
from agent_riggs.trust.events import EventCategory, Provenance, TurnEvent

# Generation tiers that don't require model inference
_STRUCTURED_TIERS = frozenset({"templates", "rules"})


class LackpySource:
    name = "lackpy"

    def discover(self, project_root: Path) -> bool:
        return (project_root / ".lackpy" / "traces.jsonl").exists()

    def read_events(self, project_root: Path, cursor: Cursor | None) -> SourceBatch:
        log_path = project_root / ".lackpy" / "traces.jsonl"
        if not log_path.exists():
            return SourceBatch(cursor=dict(cursor or {}))

        offset = (cursor or {}).get("trace_lines", 0)
        lines, total = read_new_lines(log_path, offset)

        events: list[TurnEvent] = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            # One malformed line must not abort the whole ingest.
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
                    session_id=f"lackpy-{ts.strftime('%Y%m%d')}",
                    turn_number=offset + i + 1,
                    timestamp=ts,
                    tool_name="lackpy.delegate",
                    tool_success=entry.get("success", False),
                    mode=None,
                    event_category=self._classify(entry),
                    metadata=entry,
                    provenance=Provenance.SELF_REPORTED,
                    event_uid=f"lackpy:{offset + i}:{digest}",
                )
            )
        return SourceBatch(events=events, cursor={"trace_lines": total})

    def _classify(self, entry: dict) -> EventCategory:
        if not entry.get("success", False):
            return EventCategory.FAILURE
        tier = entry.get("generation_tier", "")
        if tier in _STRUCTURED_TIERS:
            return EventCategory.SUCCESS
        return EventCategory.SUBOPTIMAL

    def _parse_timestamp(self, ts_str: str) -> datetime:
        if not ts_str:
            return datetime.now(UTC)
        ts_str = str(ts_str).replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str)
