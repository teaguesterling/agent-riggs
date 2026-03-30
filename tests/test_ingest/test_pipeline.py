from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent_riggs.config import load_config
from agent_riggs.ingest.pipeline import ingest, IngestResult
from agent_riggs.ingest.sources.kibitzer import KibitzerSource
from agent_riggs.store import Store


def _setup_kibitzer(project: Path) -> None:
    kib_dir = project / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    (kib_dir / "state.json").write_text(json.dumps({
        "mode": "implement",
        "turn_count": 3,
        "session_id": "sess-test",
    }))
    with (kib_dir / "intercept.log").open("w") as f:
        for i in range(3):
            f.write(json.dumps({
                "timestamp": f"2026-03-29T10:0{i}:00Z",
                "tool": "Read",
                "success": True,
            }) + "\n")


def test_ingest_stores_turns(tmp_project: Path) -> None:
    _setup_kibitzer(tmp_project)
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        from agent_riggs.plugins.trust import TRUST_DDL
        store.ensure_schema(TRUST_DDL)

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


def test_ingest_computes_trust_scores(tmp_project: Path) -> None:
    _setup_kibitzer(tmp_project)
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        from agent_riggs.plugins.trust import TRUST_DDL
        store.ensure_schema(TRUST_DDL)

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
        assert row[0] > 0.9
        assert row[1] > 0.9
        assert row[2] > 0.9


def test_ingest_skips_missing_sources(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        from agent_riggs.plugins.trust import TRUST_DDL
        store.ensure_schema(TRUST_DDL)

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
    (kib_dir / "state.json").write_text(json.dumps({
        "mode": "implement",
        "session_id": "sess-fail",
    }))
    with (kib_dir / "intercept.log").open("w") as f:
        f.write(json.dumps({
            "timestamp": "2026-03-29T10:00:00Z",
            "tool": "Edit",
            "success": False,
            "error": "old_string not found",
        }) + "\n")

    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        from agent_riggs.plugins.trust import TRUST_DDL
        store.ensure_schema(TRUST_DDL)

        ingest(
            store=store,
            project_root=tmp_project,
            sources=[KibitzerSource()],
            trust_config=config.trust,
        )

        failures = store.execute("SELECT count(*) FROM failure_stream").fetchone()
        assert failures is not None
        assert failures[0] >= 1
