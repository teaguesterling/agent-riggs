"""Source protocol for ingest pipeline."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

from agent_riggs.trust.events import TurnEvent


class Source(Protocol):
    """A data source that produces TurnEvents from a sibling tool."""

    name: str

    def discover(self, project_root: Path) -> bool: ...
    def read_events(self, project_root: Path, since: datetime | None) -> list[TurnEvent]: ...
