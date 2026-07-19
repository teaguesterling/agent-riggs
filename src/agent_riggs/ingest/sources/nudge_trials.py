"""Kibitzer nudge-trial ingest — reads ~/.kibitzer/nudge_trials.jsonl.

Each line is one A/B trial logged by kibitzer's interceptor:
    {"plugin": ..., "arm": "nudge"|"control"|"suppressed",
     "heed": bool|null, "turns_to_heed": int|null, "session": ..., "ts": float}

Trials are the *causal* evidence the ratchet needs: the nudge arm measures
whether a suggestion actually changes behavior; the control arm measures the
base rate. These rows land in the `nudge_trials` store table (not `turns`) —
they are experiment observations, not agent turns.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agent_riggs.ingest.sources.base import Cursor, read_new_lines


@dataclass(frozen=True)
class NudgeTrial:
    plugin: str
    arm: str
    heed: bool | None
    turns_to_heed: int | None
    session_id: str | None
    ts: datetime


class NudgeTrialsSource:
    name = "kibitzer_trials"

    def __init__(self, trials_path: Path | None = None) -> None:
        self.trials_path = trials_path or Path.home() / ".kibitzer" / "nudge_trials.jsonl"

    def discover(self, project_root: Path) -> bool:
        return self.trials_path.exists()

    def read_trials(self, cursor: Cursor | None) -> tuple[list[NudgeTrial], Cursor]:
        offset = (cursor or {}).get("trial_lines", 0)
        lines, total = read_new_lines(self.trials_path, offset)

        trials: list[NudgeTrial] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            plugin = entry.get("plugin")
            arm = entry.get("arm")
            if not plugin or not arm:
                continue
            trials.append(
                NudgeTrial(
                    plugin=plugin,
                    arm=arm,
                    heed=entry.get("heed"),
                    turns_to_heed=entry.get("turns_to_heed"),
                    session_id=entry.get("session"),
                    ts=self._parse_ts(entry.get("ts")),
                )
            )
        return trials, {"trial_lines": total}

    def _parse_ts(self, ts: float | None) -> datetime:
        if ts is None:
            return datetime.now(UTC)
        return datetime.fromtimestamp(ts, tz=UTC)
