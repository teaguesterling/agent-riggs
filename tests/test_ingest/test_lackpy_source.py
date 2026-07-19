from __future__ import annotations

import json
from pathlib import Path

from agent_riggs.ingest.sources.lackpy import LackpySource
from agent_riggs.trust.events import EventCategory


def _write_traces(project: Path, entries: list[dict], append: bool = False) -> None:
    lpy_dir = project / ".lackpy"
    lpy_dir.mkdir(exist_ok=True)
    mode = "a" if append else "w"
    with (lpy_dir / "traces.jsonl").open(mode) as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def test_discover_when_traces_present(tmp_project: Path) -> None:
    _write_traces(tmp_project, [{"timestamp": "2026-03-31T10:00:00Z", "success": True}])
    assert LackpySource().discover(tmp_project) is True


def test_discover_when_absent(tmp_project: Path) -> None:
    assert LackpySource().discover(tmp_project) is False


def test_successful_template_delegation(tmp_project: Path) -> None:
    _write_traces(
        tmp_project,
        [
            {
                "timestamp": "2026-03-31T10:00:00Z",
                "intent": "read file main.py",
                "generation_tier": "templates",
                "success": True,
                "trace": [{"step": 0, "tool": "read", "success": True}],
            }
        ],
    )
    batch = LackpySource().read_events(tmp_project, cursor=None)
    assert len(batch.events) == 1
    assert batch.events[0].event_category == EventCategory.SUCCESS


def test_successful_model_delegation_is_suboptimal(tmp_project: Path) -> None:
    _write_traces(
        tmp_project,
        [
            {
                "timestamp": "2026-03-31T10:00:00Z",
                "intent": "find callers of validate",
                "generation_tier": "ollama-local",
                "success": True,
                "trace": [],
            }
        ],
    )
    batch = LackpySource().read_events(tmp_project, cursor=None)
    assert len(batch.events) == 1
    assert batch.events[0].event_category == EventCategory.SUBOPTIMAL


def test_failed_delegation(tmp_project: Path) -> None:
    _write_traces(
        tmp_project,
        [
            {
                "timestamp": "2026-03-31T10:00:00Z",
                "intent": "check coverage for auth module",
                "generation_tier": "ollama-local",
                "success": False,
                "error": "NameError: name 'coverage' is not defined",
            }
        ],
    )
    batch = LackpySource().read_events(tmp_project, cursor=None)
    assert len(batch.events) == 1
    assert batch.events[0].event_category == EventCategory.FAILURE


def test_cursor_makes_reads_incremental(tmp_project: Path) -> None:
    _write_traces(
        tmp_project,
        [
            {"timestamp": "2026-03-30T10:00:00Z", "success": True, "generation_tier": "rules"},
            {"timestamp": "2026-03-31T10:00:00Z", "success": True, "generation_tier": "rules"},
        ],
    )
    source = LackpySource()
    first = source.read_events(tmp_project, cursor=None)
    assert len(first.events) == 2
    assert first.cursor == {"trace_lines": 2}

    second = source.read_events(tmp_project, first.cursor)
    assert second.events == []

    _write_traces(
        tmp_project,
        [{"timestamp": "2026-04-01T10:00:00Z", "success": True, "generation_tier": "rules"}],
        append=True,
    )
    third = source.read_events(tmp_project, second.cursor)
    assert len(third.events) == 1
