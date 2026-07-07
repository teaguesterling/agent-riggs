"""Regression tests: the scored subject must not be able to elevate its own trust.

These reproduce the tamper paths from the private security advisory
GHSA-j5cw-vqqp-pmm5 and FAIL on the vulnerable code:

1. rm-to-reset: deleting ``.riggs/store.duckdb`` must not restore trust.
2. Direct edit: a subject-forged max-trust row in the store must not be
   believed.
3. Self-report: a session appending its own ``success`` entries must not be
   able to raise its trust/EWMA.
4. Replay: re-ingesting the same evidence must not re-count it.

Note on the ownership boundary: real filesystem-permission separation
(separate uid owning the state directory) is not practical in CI. The
boundary is simulated by an out-of-tree state directory
(``AGENT_RIGGS_STATE_DIR``), and the always-run guards for the
score-derivation and gate decision are the pure unit tests in
``test_ledger.py`` and ``test_gate.py``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from agent_riggs.assembly import assemble
from agent_riggs.config import load_config
from agent_riggs.ingest.pipeline import ingest
from agent_riggs.ingest.sources.blq import BlqSource
from agent_riggs.ingest.sources.kibitzer import KibitzerSource
from agent_riggs.plugins.trust import TRUST_DDL
from agent_riggs.store import Store

LOW_TRUST = 0.5  # anything at/above this would satisfy the default gate


def _write_kibitzer_log(
    project: Path, entries: list[dict[str, Any]], append: bool = False
) -> None:
    kib_dir = project / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    state_path = kib_dir / "state.json"
    if not state_path.exists():
        state_path.write_text(json.dumps({"mode": "implement", "session_id": "sess-subject"}))
    mode = "a" if append else "w"
    with (kib_dir / "intercept.log").open(mode) as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _failure_entries(n: int, start: int = 0) -> list[dict[str, Any]]:
    base = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    return [
        {
            "timestamp": (base + timedelta(minutes=start + i)).isoformat(),
            "tool": "Edit",
            "success": False,
            "error": "old_string not found",
        }
        for i in range(n)
    ]


def _success_entries(n: int, start: int = 0) -> list[dict[str, Any]]:
    base = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    return [
        {
            "timestamp": (base + timedelta(minutes=start + i)).isoformat(),
            "tool": "Read",
            "success": True,
        }
        for i in range(n)
    ]


def _write_blq_db(project: Path, exit_codes: list[int]) -> None:
    """Create a .bird/blq.duckdb with observed invocation outcomes."""
    bird = project / ".bird"
    bird.mkdir(exist_ok=True)
    db = bird / "blq.duckdb"
    conn = duckdb.connect(str(db))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS invocations (
            id INTEGER, session_id VARCHAR, timestamp TIMESTAMP, cmd VARCHAR,
            executable VARCHAR, exit_code INTEGER, duration_ms INTEGER, source_name VARCHAR
        )"""
    )
    row = conn.execute("SELECT coalesce(max(id), 0) FROM invocations").fetchone()
    next_id = (row[0] if row else 0) + 1
    base = datetime(2026, 6, 2, 9, 0)
    for i, code in enumerate(exit_codes):
        conn.execute(
            "INSERT INTO invocations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [next_id + i, "sess-blq", base + timedelta(minutes=i), "pytest", "pytest", code, 100,
             "test"],
        )
    conn.close()


def _ingest(project: Path, sources: list[Any]) -> Any:
    config = load_config(project)
    with Store(project / ".riggs" / "store.duckdb") as store:
        store.ensure_schema(TRUST_DDL)
        return ingest(
            store=store,
            project_root=project,
            sources=sources,
            trust_config=config.trust,
        )


def _current_trust(project: Path) -> dict[str, Any]:
    service = assemble(project)
    try:
        return service.plugin("trust").current()
    finally:
        service.store.close()


def test_deleting_store_does_not_restore_trust(tmp_project: Path) -> None:
    """Advisory path 1: `rm .riggs/store.duckdb` must not reset trust to max."""
    _write_kibitzer_log(tmp_project, _failure_entries(10))
    _ingest(tmp_project, [KibitzerSource()])

    before = _current_trust(tmp_project)
    assert before["trust_1"] < LOW_TRUST  # sanity: repeated failures = low trust

    # The scored subject deletes the store in its own project tree.
    (tmp_project / ".riggs" / "store.duckdb").unlink()

    after = _current_trust(tmp_project)
    assert after["trust_1"] < LOW_TRUST, "deleting the store must not restore trust"
    assert after["trust_1"] <= before["trust_1"] + 1e-9


def test_direct_store_edit_cannot_raise_trust(tmp_project: Path) -> None:
    """Advisory path 1b: a forged max-trust row in the store must not be believed."""
    _write_kibitzer_log(tmp_project, _failure_entries(10))
    _ingest(tmp_project, [KibitzerSource()])

    before = _current_trust(tmp_project)
    assert before["trust_1"] < LOW_TRUST

    # The subject opens its own read-write connection and forges max trust.
    conn = duckdb.connect(str(tmp_project / ".riggs" / "store.duckdb"))
    conn.execute(
        """INSERT INTO turns (turn_id, session_id, project, turn_number, timestamp,
               tool_name, tool_success, mode, trust_score, trust_1, trust_5, trust_15,
               event_category, metadata)
           VALUES (999999, 'forged', ?, 999, now(), 'Bash', true, 'implement',
                   1.0, 1.0, 1.0, 1.0, 'success', '{}')""",
        [tmp_project.name],
    )
    conn.close()

    after = _current_trust(tmp_project)
    assert after["trust_1"] < LOW_TRUST, "a subject-written store row must not raise trust"
    assert after["trust_1"] <= before["trust_1"] + 1e-9


def test_self_reported_success_cannot_raise_trust(tmp_project: Path) -> None:
    """Advisory path 2: self-reported `success` entries must not raise trust/EWMA."""
    _write_kibitzer_log(tmp_project, _failure_entries(5))
    _ingest(tmp_project, [KibitzerSource()])

    before = _current_trust(tmp_project)
    assert before["trust_1"] < LOW_TRUST

    # The subject appends 50 self-reported successes to its own log.
    _write_kibitzer_log(tmp_project, _success_entries(50, start=100), append=True)
    _ingest(tmp_project, [KibitzerSource()])

    after = _current_trust(tmp_project)
    assert after["trust_1"] <= before["trust_1"] + 1e-9, (
        "self-reported success must not raise trust "
        f"(before={before['trust_1']:.3f}, after={after['trust_1']:.3f})"
    )
    assert after["trust_5"] <= before["trust_5"] + 1e-9
    assert after["trust_15"] <= before["trust_15"] + 1e-9


def test_self_reported_failure_still_lowers_trust(tmp_project: Path) -> None:
    """Asymmetry check: claims against interest are still counted."""
    _write_blq_db(tmp_project, exit_codes=[0] * 20)
    _ingest(tmp_project, [BlqSource()])
    before = _current_trust(tmp_project)

    _write_kibitzer_log(tmp_project, _failure_entries(3, start=500))
    _ingest(tmp_project, [KibitzerSource()])
    after = _current_trust(tmp_project)

    assert after["trust_1"] < before["trust_1"]


def test_reingesting_same_evidence_is_idempotent(tmp_project: Path) -> None:
    """Replaying `ingest` over the same evidence must not re-count it."""
    _write_blq_db(tmp_project, exit_codes=[0] * 5)
    first = _ingest(tmp_project, [BlqSource()])
    assert first.turns_ingested == 5

    trust_after_first = _current_trust(tmp_project)

    second = _ingest(tmp_project, [BlqSource()])
    assert second.turns_ingested == 0, "re-ingest must not duplicate already-counted events"

    trust_after_second = _current_trust(tmp_project)
    assert abs(trust_after_second["trust_5"] - trust_after_first["trust_5"]) < 1e-9


def test_observed_success_still_accrues_trust(tmp_project: Path) -> None:
    """Legitimate accrual: independently observed outcomes raise trust."""
    _write_blq_db(tmp_project, exit_codes=[0] * 40)
    _ingest(tmp_project, [BlqSource()])

    current = _current_trust(tmp_project)
    assert current["has_data"] is True
    assert current["trust_1"] > 0.9
    assert current["trust_5"] > 0.8


def test_gate_denies_unknown_subject(tmp_project: Path) -> None:
    """Advisory path 3: absent trust state must read as LOW trust, gate denies."""
    from agent_riggs.trust.gate import TrustGate

    decision = TrustGate(tmp_project).check()
    assert decision.allowed is False
    assert decision.trust_1 < LOW_TRUST


def test_gate_allows_after_observed_accrual(tmp_project: Path) -> None:
    """A well-behaved subject with verified observed history passes the gate."""
    from agent_riggs.trust.gate import TrustGate

    _write_blq_db(tmp_project, exit_codes=[0] * 40)
    _ingest(tmp_project, [BlqSource()])

    decision = TrustGate(tmp_project).check()
    assert decision.allowed is True


def test_subject_config_cannot_weaken_gate(tmp_project: Path) -> None:
    """The subject-writable .riggs/config.toml must not weaken gate/scoring policy."""
    from agent_riggs.trust.gate import TrustGate

    (tmp_project / ".riggs" / "config.toml").write_text(
        "[trust]\n"
        "gate_threshold = 0.0\n"
        "initial_trust = 1.0\n"
        "score_failure = 1.0\n"
        "score_repeated_failure = 1.0\n"
    )

    # Gate must still deny a subject with no verified history.
    decision = TrustGate(tmp_project).check()
    assert decision.allowed is False

    # And failures must still score as failures during ingest.
    _write_kibitzer_log(tmp_project, _failure_entries(10))
    _ingest(tmp_project, [KibitzerSource()])
    current = _current_trust(tmp_project)
    assert current["trust_1"] < LOW_TRUST
