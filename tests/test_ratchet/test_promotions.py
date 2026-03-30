from __future__ import annotations

from pathlib import Path

from agent_riggs.plugins.ratchet import RATCHET_DDL
from agent_riggs.ratchet.candidates import Candidate
from agent_riggs.ratchet.history import get_history
from agent_riggs.ratchet.promotions import record_decision
from agent_riggs.store import Store


def test_record_promote_decision(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(RATCHET_DDL)
        candidate = Candidate(candidate_type="tool_promotion", candidate_key="bash-to-finddefinitions",
                              evidence={"frequency": 89, "sessions": 23}, recommendation="Graduate fledgling interceptor")
        record_decision(store, candidate, decision="promoted", reason="enough evidence")
        row = store.execute("SELECT count(*) FROM ratchet_decisions").fetchone()
        assert row == (1,)


def test_record_reject_decision(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(RATCHET_DDL)
        candidate = Candidate(candidate_type="tool_promotion", candidate_key="bash-to-blq-run-test",
                              evidence={"frequency": 10}, recommendation="Graduate blq interceptor")
        record_decision(store, candidate, decision="rejected", reason="agents need raw pytest output")
        row = store.execute("SELECT decision, reason FROM ratchet_decisions WHERE candidate_key = ?",
                            ["bash-to-blq-run-test"]).fetchone()
        assert row[0] == "rejected"
        assert row[1] == "agents need raw pytest output"


def test_get_history(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(RATCHET_DDL)
        for i in range(3):
            candidate = Candidate(candidate_type="tool_promotion", candidate_key=f"key-{i}",
                                  evidence={}, recommendation="test")
            record_decision(store, candidate, decision="promoted")
        history = get_history(store)
        assert len(history) == 3
