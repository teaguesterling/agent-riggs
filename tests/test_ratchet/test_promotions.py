from __future__ import annotations

import tomllib

from agent_riggs.plugins.ratchet import RATCHET_DDL
from agent_riggs.ratchet.candidates import Candidate
from agent_riggs.ratchet.history import get_history
from agent_riggs.ratchet.promotions import apply_nudge_promotion, record_decision
from agent_riggs.store import Store


def test_record_promote_decision(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(RATCHET_DDL)
        candidate = Candidate(
            candidate_type="nudged_tool_promotion",
            candidate_key="nudge-squackit",
            evidence={"nudges": 10, "heed_rate": 0.6, "lift": 0.5},
            recommendation="Escalate squackit interceptor",
        )
        record_decision(store, candidate, decision="promoted", reason="enough evidence")
        row = store.execute("SELECT count(*) FROM ratchet_decisions").fetchone()
        assert row == (1,)


def test_record_reject_decision(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(RATCHET_DDL)
        candidate = Candidate(
            candidate_type="nudged_tool_promotion",
            candidate_key="nudge-blq",
            evidence={"nudges": 10},
            recommendation="Escalate blq interceptor",
        )
        record_decision(
            store, candidate, decision="rejected", reason="agents need raw pytest output"
        )
        row = store.execute(
            "SELECT decision, reason FROM ratchet_decisions WHERE candidate_key = ?",
            ["nudge-blq"],
        ).fetchone()
        assert row[0] == "rejected"
        assert row[1] == "agents need raw pytest output"


def test_get_history(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(RATCHET_DDL)
        for i in range(3):
            candidate = Candidate(
                candidate_type="nudged_tool_promotion",
                candidate_key=f"key-{i}",
                evidence={},
                recommendation="test",
            )
            record_decision(store, candidate, decision="promoted")
        history = get_history(store)
        assert len(history) == 3


def test_apply_nudge_promotion_writes_kibitzer_config(tmp_project):
    change = apply_nudge_promotion(tmp_project, "squackit")

    config_path = tmp_project / ".kibitzer" / "config.toml"
    assert config_path.exists()
    data = tomllib.loads(config_path.read_text())
    assert data["plugins"]["squackit"]["mode"] == "redirect"
    assert change["plugin"] == "squackit"
    assert change["from_mode"] is None
    assert change["to_mode"] == "redirect"


def test_apply_nudge_promotion_preserves_existing_config(tmp_project):
    kib_dir = tmp_project / ".kibitzer"
    kib_dir.mkdir()
    (kib_dir / "config.toml").write_text(
        '[plugins.jetsam]\nmode = "suggest"\nenabled = true\n\n[coach]\nlevel = 2\n'
    )

    change = apply_nudge_promotion(tmp_project, "jetsam")

    data = tomllib.loads((kib_dir / "config.toml").read_text())
    assert data["plugins"]["jetsam"]["mode"] == "redirect"
    assert data["plugins"]["jetsam"]["enabled"] is True
    assert data["coach"]["level"] == 2
    assert change["from_mode"] == "suggest"
