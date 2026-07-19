from __future__ import annotations

import json
from pathlib import Path

from agent_riggs.ingest.sources.kibitzer import KibitzerSource
from agent_riggs.trust.events import EventCategory


def _write_kibitzer_state(project: Path, state: dict) -> None:
    kib_dir = project / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    (kib_dir / "state.json").write_text(json.dumps(state))


def _write_intercept_log(project: Path, entries: list[dict], append: bool = False) -> None:
    kib_dir = project / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    mode = "a" if append else "w"
    with (kib_dir / "intercept.log").open(mode) as f:
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
    _write_kibitzer_state(
        tmp_project,
        {
            "mode": "implement",
            "turn_count": 3,
            "session_id": "sess-abc",
        },
    )
    _write_intercept_log(
        tmp_project,
        [
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
        ],
    )

    source = KibitzerSource()
    batch = source.read_events(tmp_project, cursor=None)
    assert len(batch.events) == 2
    categories = {e.event_category for e in batch.events}
    assert EventCategory.SUBOPTIMAL in categories
    assert EventCategory.FAILURE in categories


def test_intercepted_bash_command_is_suboptimal(tmp_project: Path) -> None:
    """Real intercept.log entries (bash_command + suggested_tool) are bypasses."""
    _write_kibitzer_state(tmp_project, {"mode": "free", "session_id": "sess-1"})
    _write_intercept_log(
        tmp_project,
        [
            {
                "bash_command": "git push origin main",
                "suggested_tool": "jetsam sync",
                "reason": "Syncs with remote",
                "plugin": "jetsam",
            }
        ],
    )
    batch = KibitzerSource().read_events(tmp_project, cursor=None)
    assert len(batch.events) == 1
    assert batch.events[0].event_category == EventCategory.SUBOPTIMAL
    assert batch.events[0].tool_name == "Bash"


def test_cursor_makes_reads_incremental(tmp_project: Path) -> None:
    _write_kibitzer_state(tmp_project, {"mode": "free", "session_id": "sess-1"})
    _write_intercept_log(
        tmp_project,
        [
            {"timestamp": "2026-03-28T10:00:00Z", "tool": "Read", "success": True},
            {"timestamp": "2026-03-29T10:00:00Z", "tool": "Edit", "success": True},
        ],
    )

    source = KibitzerSource()
    first = source.read_events(tmp_project, cursor=None)
    assert len(first.events) == 2
    assert first.cursor == {"intercept_lines": 2}

    # Nothing new: same cursor, no events.
    second = source.read_events(tmp_project, first.cursor)
    assert second.events == []
    assert second.cursor == {"intercept_lines": 2}

    # Append one entry: only it is read.
    _write_intercept_log(
        tmp_project,
        [{"timestamp": "2026-03-30T10:00:00Z", "tool": "Write", "success": True}],
        append=True,
    )
    third = source.read_events(tmp_project, second.cursor)
    assert len(third.events) == 1
    assert third.events[0].tool_name == "Write"
    assert third.cursor == {"intercept_lines": 3}
