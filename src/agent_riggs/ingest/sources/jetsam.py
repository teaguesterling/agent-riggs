"""Stub source — not yet implemented."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from agent_riggs.trust.events import TurnEvent


class JetsamSource:
    name = "jetsam"

    def discover(self, project_root: Path) -> bool:
        return False

    def read_events(self, project_root: Path, since: datetime | None) -> list[TurnEvent]:
        return []
