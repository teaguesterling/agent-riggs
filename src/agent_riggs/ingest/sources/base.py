"""Source protocol for ingest pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from agent_riggs.trust.events import TurnEvent

# A cursor is a source-specific, JSON-serializable high-water mark. The
# pipeline persists it per (project, source) in the ingest_state table and
# hands it back on the next run so sources only read new data.
Cursor = dict[str, Any]


@dataclass
class SourceBatch:
    """Events read from a source plus the cursor to resume from next time."""

    events: list[TurnEvent] = field(default_factory=list)
    cursor: Cursor = field(default_factory=dict)


class Source(Protocol):
    """A data source that produces TurnEvents from a sibling tool."""

    name: str

    def discover(self, project_root: Path) -> bool: ...
    def read_events(self, project_root: Path, cursor: Cursor | None) -> SourceBatch: ...


def read_new_lines(path: Path, offset: int) -> tuple[list[str], int]:
    """Read lines from an append-only file, skipping the first `offset` lines.

    Returns (new_lines, total_line_count). If the file shrank below the
    offset (rotation/truncation), re-reads from the start rather than
    silently dropping data.
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if offset > len(lines):
        offset = 0
    return lines[offset:], len(lines)
