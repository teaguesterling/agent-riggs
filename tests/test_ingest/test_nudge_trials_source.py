from __future__ import annotations

import json
from pathlib import Path

from agent_riggs.ingest.sources.nudge_trials import NudgeTrialsSource


def _write_trials(path: Path, entries: list[dict], append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode) as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def test_discover_when_absent(tmp_project: Path) -> None:
    source = NudgeTrialsSource(trials_path=tmp_project / "nope.jsonl")
    assert source.discover(tmp_project) is False


def test_read_trials(tmp_project: Path) -> None:
    trials_path = tmp_project / "nudge_trials.jsonl"
    _write_trials(
        trials_path,
        [
            {
                "plugin": "jetsam",
                "arm": "nudge",
                "heed": False,
                "turns_to_heed": None,
                "session": "sess-1",
                "ts": 1782071670.5,
            },
            {
                "plugin": "squackit",
                "arm": "control",
                "heed": True,
                "turns_to_heed": 3,
                "session": "sess-2",
                "ts": 1782071680.5,
            },
        ],
    )
    source = NudgeTrialsSource(trials_path=trials_path)
    assert source.discover(tmp_project) is True

    trials, cursor = source.read_trials(None)
    assert len(trials) == 2
    assert trials[0].plugin == "jetsam"
    assert trials[0].arm == "nudge"
    assert trials[0].heed is False
    assert trials[1].heed is True
    assert trials[1].turns_to_heed == 3
    assert cursor == {"trial_lines": 2}


def test_cursor_makes_reads_incremental(tmp_project: Path) -> None:
    trials_path = tmp_project / "nudge_trials.jsonl"
    _write_trials(
        trials_path,
        [{"plugin": "blq", "arm": "nudge", "heed": True, "session": "s", "ts": 1.0}],
    )
    source = NudgeTrialsSource(trials_path=trials_path)

    first, cursor = source.read_trials(None)
    assert len(first) == 1

    second, cursor = source.read_trials(cursor)
    assert second == []

    _write_trials(
        trials_path,
        [{"plugin": "blq", "arm": "control", "heed": False, "session": "s", "ts": 2.0}],
        append=True,
    )
    third, cursor = source.read_trials(cursor)
    assert len(third) == 1
    assert third[0].arm == "control"


def test_malformed_lines_are_skipped(tmp_project: Path) -> None:
    trials_path = tmp_project / "nudge_trials.jsonl"
    trials_path.write_text(
        "{bad json\n"
        + json.dumps({"plugin": "jetsam", "arm": "nudge", "heed": False, "ts": 1.0})
        + "\n"
        + json.dumps({"arm": "nudge"})  # missing plugin
        + "\n"
    )
    source = NudgeTrialsSource(trials_path=trials_path)
    trials, cursor = source.read_trials(None)
    assert len(trials) == 1
    assert cursor == {"trial_lines": 3}
