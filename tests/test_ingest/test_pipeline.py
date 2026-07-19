from __future__ import annotations

import json
from pathlib import Path

from agent_riggs.config import load_config
from agent_riggs.ingest.pipeline import ingest
from agent_riggs.ingest.sources.kibitzer import KibitzerSource
from agent_riggs.ingest.sources.nudge_trials import NudgeTrialsSource
from agent_riggs.store import Store


def _all_ddl():
    from agent_riggs.plugins.ingest import INGEST_DDL
    from agent_riggs.plugins.trust import TRUST_DDL

    return TRUST_DDL + INGEST_DDL


def _setup_kibitzer(project: Path, entries: list[dict] | None = None) -> None:
    kib_dir = project / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    (kib_dir / "state.json").write_text(
        json.dumps(
            {
                "mode": "implement",
                "turn_count": 3,
                "session_id": "sess-test",
            }
        )
    )
    if entries is None:
        entries = [
            {"timestamp": f"2026-03-29T10:0{i}:00Z", "tool": "Read", "success": True}
            for i in range(3)
        ]
    with (kib_dir / "intercept.log").open("a") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def test_ingest_stores_turns(tmp_project: Path) -> None:
    _setup_kibitzer(tmp_project)
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        store.ensure_schema(_all_ddl())

        result = ingest(
            store=store,
            project_root=tmp_project,
            sources=[KibitzerSource()],
            trust_config=config.trust,
        )
        assert result.turns_ingested == 3
        assert result.sources_read == ["kibitzer"]

        count = store.execute("SELECT count(*) FROM turns").fetchone()
        assert count == (3,)
        source_col = store.execute("SELECT DISTINCT source FROM turns").fetchone()
        assert source_col == ("kibitzer",)


def test_ingest_is_incremental_and_idempotent(tmp_project: Path) -> None:
    _setup_kibitzer(tmp_project)
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        store.ensure_schema(_all_ddl())

        first = ingest(store, tmp_project, [KibitzerSource()], config.trust)
        assert first.turns_ingested == 3

        # Second run with no new data: nothing ingested, no duplicates.
        second = ingest(store, tmp_project, [KibitzerSource()], config.trust)
        assert second.turns_ingested == 0
        assert store.execute("SELECT count(*) FROM turns").fetchone() == (3,)

        # New data appended: only the new entry is ingested.
        _setup_kibitzer(
            tmp_project,
            [{"timestamp": "2026-03-29T11:00:00Z", "tool": "Edit", "success": True}],
        )
        third = ingest(store, tmp_project, [KibitzerSource()], config.trust)
        assert third.turns_ingested == 1
        assert store.execute("SELECT count(*) FROM turns").fetchone() == (4,)


def test_ingest_computes_trust_scores(tmp_project: Path) -> None:
    """Self-reported kibitzer successes are recorded but cannot inflate trust.

    An unknown subject starts at ``initial_trust`` and self-reported success
    holds trust at most where it is (GHSA: self-report must not raise trust).
    """
    _setup_kibitzer(tmp_project)
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        store.ensure_schema(_all_ddl())

        ingest(
            store=store,
            project_root=tmp_project,
            sources=[KibitzerSource()],
            trust_config=config.trust,
        )

        row = store.execute(
            "SELECT trust_1, trust_5, trust_15 FROM turns ORDER BY turn_number DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[0] <= config.trust.initial_trust + 1e-9
        assert row[1] <= config.trust.initial_trust + 1e-9
        assert row[2] <= config.trust.initial_trust + 1e-9


def test_ingest_skips_malformed_log_lines(tmp_project: Path) -> None:
    """One malformed subject-controlled line must not abort the whole ingest."""
    _setup_kibitzer(tmp_project)
    with (tmp_project / ".kibitzer" / "intercept.log").open("a") as f:
        f.write("{not valid json\n")
        f.write(
            json.dumps({"timestamp": "2026-03-29T10:10:00Z", "tool": "Edit", "success": False})
            + "\n"
        )

    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        store.ensure_schema(_all_ddl())

        result = ingest(
            store=store,
            project_root=tmp_project,
            sources=[KibitzerSource()],
            trust_config=config.trust,
        )
        assert result.turns_ingested == 4  # 3 valid + 1 after the bad line


def test_ingest_skips_missing_sources(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        store.ensure_schema(_all_ddl())

        result = ingest(
            store=store,
            project_root=tmp_project,
            sources=[KibitzerSource()],
            trust_config=config.trust,
        )
        assert result.turns_ingested == 0
        assert result.sources_read == []


def test_ingest_records_failures(tmp_project: Path) -> None:
    kib_dir = tmp_project / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    (kib_dir / "state.json").write_text(
        json.dumps(
            {
                "mode": "implement",
                "session_id": "sess-fail",
            }
        )
    )
    with (kib_dir / "intercept.log").open("w") as f:
        f.write(
            json.dumps(
                {
                    "timestamp": "2026-03-29T10:00:00Z",
                    "tool": "Edit",
                    "success": False,
                    "error": "old_string not found",
                }
            )
            + "\n"
        )

    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        store.ensure_schema(_all_ddl())

        ingest(
            store=store,
            project_root=tmp_project,
            sources=[KibitzerSource()],
            trust_config=config.trust,
        )

        failures = store.execute("SELECT count(*) FROM failure_stream").fetchone()
        assert failures is not None
        assert failures[0] >= 1


def test_ingest_nudge_trials(tmp_project: Path) -> None:
    trials_path = tmp_project / "nudge_trials.jsonl"
    with trials_path.open("w") as f:
        for i in range(4):
            f.write(
                json.dumps(
                    {
                        "plugin": "jetsam",
                        "arm": "nudge" if i % 2 == 0 else "control",
                        "heed": i == 0,
                        "turns_to_heed": 2 if i == 0 else None,
                        "session": f"sess-{i}",
                        "ts": 1782071670.0 + i,
                    }
                )
                + "\n"
            )

    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        store.ensure_schema(_all_ddl())

        result = ingest(
            store=store,
            project_root=tmp_project,
            sources=[],
            trust_config=config.trust,
            trials_source=NudgeTrialsSource(trials_path),
        )
        assert result.trials_ingested == 4
        assert store.execute("SELECT count(*) FROM nudge_trials").fetchone() == (4,)

        # Idempotent: second run ingests nothing new.
        result = ingest(
            store=store,
            project_root=tmp_project,
            sources=[],
            trust_config=config.trust,
            trials_source=NudgeTrialsSource(trials_path),
        )
        assert result.trials_ingested == 0
        assert store.execute("SELECT count(*) FROM nudge_trials").fetchone() == (4,)
