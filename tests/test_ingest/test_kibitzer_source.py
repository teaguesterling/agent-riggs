from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent_riggs.ingest.sources.kibitzer import KibitzerSource
from agent_riggs.trust.events import EventCategory


def _write_kibitzer_state(project: Path, state: dict) -> None:
    kib_dir = project / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    (kib_dir / "state.json").write_text(json.dumps(state))


def _write_intercept_log(project: Path, entries: list[dict]) -> None:
    kib_dir = project / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    with (kib_dir / "intercept.log").open("w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def test_discover_when_kibitzer_present(tmp_project: Path) -> None:
    _write_kibitzer_state(tmp_project, {"mode": "implement", "turn_count": 5})
    source = KibitzerSource()
    assert source.discover(tmp_project) is True


def test_discover_when_kibitzer_absent(tmp_project: Path) -> None:
    source = KibitzerSource()
    assert source.discover(tmp_project) is False


def test_read_events_from_intercept_log(tmp_project: Path) -> None:
    _write_kibitzer_state(tmp_project, {
        "mode": "implement",
        "turn_count": 3,
        "session_id": "sess-abc",
    })
    _write_intercept_log(tmp_project, [
        {
            "timestamp": "2026-03-29T10:00:00Z",
            "tool": "Bash",
            "command": "grep -rn 'def ' src/",
            "suggestion": "Use FindDefinitions",
            "action": "suggest",
        },
        {
            "timestamp": "2026-03-29T10:01:00Z",
            "tool": "Edit",
            "success": False,
            "error": "old_string not found",
        },
    ])

    source = KibitzerSource()
    events = source.read_events(tmp_project, since=None)
    assert len(events) >= 2
    categories = {e.event_category for e in events}
    assert EventCategory.SUBOPTIMAL in categories or EventCategory.FAILURE in categories


def test_read_events_respects_since(tmp_project: Path) -> None:
    _write_kibitzer_state(tmp_project, {
        "mode": "implement",
        "turn_count": 2,
        "session_id": "sess-abc",
    })
    _write_intercept_log(tmp_project, [
        {
            "timestamp": "2026-03-28T10:00:00Z",
            "tool": "Read",
            "success": True,
        },
        {
            "timestamp": "2026-03-29T10:00:00Z",
            "tool": "Edit",
            "success": True,
        },
    ])

    source = KibitzerSource()
    since = datetime(2026, 3, 29, tzinfo=timezone.utc)
    events = source.read_events(tmp_project, since=since)
    assert len(events) == 1
