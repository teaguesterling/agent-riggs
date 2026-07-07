"""Unit tests for the HMAC-chained, out-of-tree trust ledger.

These are the always-run guards for store integrity: tampering with the
ledger in any way (edit, truncate, delete the key) must be detected and
read as an unverifiable — i.e. untrusted — state.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from agent_riggs.trust.ledger import TrustLedger


def _append_n(ledger: TrustLedger, n: int, t1: float = 0.9) -> None:
    for i in range(n):
        ledger.append(
            event_uid=f"test:{i}",
            session_id="sess-1",
            category="success",
            score=1.0,
            t1=t1,
            t5=t1,
            t15=t1,
            observed=True,
            timestamp=datetime(2026, 6, 1, 10, i % 60, tzinfo=UTC),
        )


def test_roundtrip_verifies_ok(tmp_project: Path) -> None:
    ledger = TrustLedger(tmp_project)
    _append_n(ledger, 5)

    state = TrustLedger(tmp_project).verify()
    assert state.status == "ok"
    assert len(state.records) == 5
    assert state.last is not None
    assert state.last.seq == 5
    assert state.last.t1 == 0.9


def test_absent_state_reports_absent(tmp_project: Path) -> None:
    state = TrustLedger(tmp_project).verify()
    assert state.status == "absent"
    assert state.records == []


def test_edited_record_is_tampered(tmp_project: Path) -> None:
    ledger = TrustLedger(tmp_project)
    _append_n(ledger, 5, t1=0.2)

    # The subject rewrites a record to claim max trust.
    lines = ledger.ledger_path.read_text().splitlines()
    record = json.loads(lines[-1])
    record["t1"] = record["t5"] = record["t15"] = 1.0
    lines[-1] = json.dumps(record)
    ledger.ledger_path.write_text("\n".join(lines) + "\n")

    state = TrustLedger(tmp_project).verify()
    assert state.status == "tampered"


def test_truncated_ledger_is_tampered(tmp_project: Path) -> None:
    ledger = TrustLedger(tmp_project)
    _append_n(ledger, 3, t1=0.9)
    # Trust drops; the subject then truncates the trailing low-trust records.
    ledger.append(
        event_uid="test:fail",
        session_id="sess-1",
        category="failure",
        score=0.2,
        t1=0.2,
        t5=0.5,
        t15=0.8,
        observed=True,
        timestamp=datetime(2026, 6, 1, 11, 0, tzinfo=UTC),
    )

    lines = ledger.ledger_path.read_text().splitlines()
    ledger.ledger_path.write_text("\n".join(lines[:-1]) + "\n")

    state = TrustLedger(tmp_project).verify()
    assert state.status == "tampered"


def test_missing_key_is_tampered(tmp_project: Path) -> None:
    ledger = TrustLedger(tmp_project)
    _append_n(ledger, 2)
    ledger.key_path.unlink()

    state = TrustLedger(tmp_project).verify()
    assert state.status == "tampered"


def test_forged_head_is_tampered(tmp_project: Path) -> None:
    """A head file rewritten to point at an earlier (higher-trust) record fails."""
    ledger = TrustLedger(tmp_project)
    _append_n(ledger, 2, t1=0.95)
    ledger.append(
        event_uid="test:fail",
        session_id="sess-1",
        category="failure",
        score=0.2,
        t1=0.2,
        t5=0.4,
        t15=0.7,
        observed=True,
        timestamp=datetime(2026, 6, 1, 11, 0, tzinfo=UTC),
    )

    lines = ledger.ledger_path.read_text().splitlines()
    second = json.loads(lines[1])
    # Forge a head pointing at record 2 (no key, so no valid head MAC).
    ledger.head_path.write_text(
        json.dumps({"seq": second["seq"], "mac": second["mac"], "head_mac": "0" * 64})
    )
    ledger.ledger_path.write_text("\n".join(lines[:2]) + "\n")

    state = TrustLedger(tmp_project).verify()
    assert state.status == "tampered"


def test_ledger_lives_outside_project_tree(tmp_project: Path) -> None:
    ledger = TrustLedger(tmp_project)
    _append_n(ledger, 1)
    assert not ledger.ledger_path.is_relative_to(tmp_project)
    assert not ledger.key_path.is_relative_to(tmp_project)


def test_key_file_permissions(tmp_project: Path) -> None:
    ledger = TrustLedger(tmp_project)
    _append_n(ledger, 1)
    mode = ledger.key_path.stat().st_mode & 0o777
    assert mode == 0o600
