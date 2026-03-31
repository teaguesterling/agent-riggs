from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from agent_riggs.ingest.sources.lackpy import LackpySource
from agent_riggs.trust.events import EventCategory


def _write_traces(project: Path, entries: list[dict]) -> None:
    lpy_dir = project / ".lackpy"
    lpy_dir.mkdir(exist_ok=True)
    with (lpy_dir / "traces.jsonl").open("w") as f:
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
    events = LackpySource().read_events(tmp_project, since=None)
    assert len(events) == 1
    assert events[0].event_category == EventCategory.SUCCESS


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
    events = LackpySource().read_events(tmp_project, since=None)
    assert len(events) == 1
    assert events[0].event_category == EventCategory.SUBOPTIMAL


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
    events = LackpySource().read_events(tmp_project, since=None)
    assert len(events) == 1
    assert events[0].event_category == EventCategory.FAILURE


def test_respects_since(tmp_project: Path) -> None:
    _write_traces(
        tmp_project,
        [
            {"timestamp": "2026-03-30T10:00:00Z", "success": True, "generation_tier": "rules"},
            {"timestamp": "2026-03-31T10:00:00Z", "success": True, "generation_tier": "rules"},
        ],
    )
    since = datetime(2026, 3, 31, tzinfo=UTC)
    events = LackpySource().read_events(tmp_project, since=since)
    assert len(events) == 1
