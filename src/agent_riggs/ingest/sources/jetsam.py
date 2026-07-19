"""Jetsam ingest source — reads .jetsam/plans/*.json workflow plans."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from agent_riggs.ingest.sources.base import Cursor, SourceBatch
from agent_riggs.trust.events import EventCategory, TurnEvent


class JetsamSource:
    name = "jetsam"

    def discover(self, project_root: Path) -> bool:
        return (project_root / ".jetsam" / "plans").is_dir()

    def read_events(self, project_root: Path, cursor: Cursor | None) -> SourceBatch:
        plans_dir = project_root / ".jetsam" / "plans"
        seen = set((cursor or {}).get("seen_plans", []))

        plans: list[dict] = []
        for plan_path in sorted(plans_dir.glob("*.json")):
            if plan_path.stem in seen:
                continue
            try:
                plan = json.loads(plan_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            plan.setdefault("plan_id", plan_path.stem)
            plans.append(plan)

        plans.sort(key=lambda p: p.get("created_at") or 0)
        events: list[TurnEvent] = []
        for i, plan in enumerate(plans):
            ts = self._parse_created_at(plan.get("created_at"))
            verb = plan.get("verb") or "unknown"
            warnings = plan.get("warnings") or []
            events.append(
                TurnEvent(
                    session_id=f"jetsam-{ts.strftime('%Y%m%d')}",
                    turn_number=i + 1,
                    timestamp=ts,
                    tool_name=f"jetsam.{verb}",
                    tool_success=True,
                    mode=None,
                    event_category=EventCategory.SUCCESS,
                    metadata={
                        "plan_id": plan.get("plan_id"),
                        "verb": verb,
                        "steps": [s.get("action") for s in plan.get("steps", [])],
                        "warnings": warnings,
                        "repo_root": plan.get("repo_root"),
                        "source": "jetsam",
                    },
                )
            )
            seen.add(str(plan.get("plan_id")))

        return SourceBatch(events=events, cursor={"seen_plans": sorted(seen)})

    def _parse_created_at(self, created_at: float | None) -> datetime:
        if created_at is None:
            return datetime.now(UTC)
        return datetime.fromtimestamp(created_at, tz=UTC)
