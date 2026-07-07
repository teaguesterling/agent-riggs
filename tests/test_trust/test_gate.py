"""Unit tests for the fail-closed trust gate.

The gate is the enforcement point that consumes the verified trust ledger.
It must deny on: absent state, tampered state, insufficient trust, and
recent violations — and only allow on verified, sufficient, clean history.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agent_riggs.config import TrustConfig
from agent_riggs.trust.gate import TrustGate, evaluate_gate
from agent_riggs.trust.ledger import LedgerState, TrustLedger


def _record_state(
    ledger: TrustLedger,
    trusts: list[float],
    categories: list[str] | None = None,
) -> LedgerState:
    cats = categories or ["success"] * len(trusts)
    for i, (t, cat) in enumerate(zip(trusts, cats, strict=True)):
        ledger.append(
            event_uid=f"g:{i}",
            session_id="sess-1",
            category=cat,
            score=1.0 if cat == "success" else 0.2,
            t1=t,
            t5=t,
            t15=t,
            observed=True,
            timestamp=datetime(2026, 6, 1, 10, i % 60, tzinfo=UTC),
        )
    return ledger.verify()


def test_evaluate_denies_absent_state() -> None:
    decision = evaluate_gate(LedgerState(status="absent"), TrustConfig())
    assert decision.allowed is False
    assert decision.trust_1 == 0.0


def test_evaluate_denies_tampered_state() -> None:
    decision = evaluate_gate(LedgerState(status="tampered", detail="mac mismatch"), TrustConfig())
    assert decision.allowed is False
    assert "integrity" in decision.reason.lower() or "tamper" in decision.reason.lower()


def test_evaluate_denies_low_trust(tmp_project: Path) -> None:
    state = _record_state(TrustLedger(tmp_project), [0.9, 0.7, 0.4])
    decision = evaluate_gate(state, TrustConfig())
    assert decision.allowed is False


def test_evaluate_allows_verified_high_trust(tmp_project: Path) -> None:
    state = _record_state(TrustLedger(tmp_project), [0.7, 0.8, 0.9])
    decision = evaluate_gate(state, TrustConfig())
    assert decision.allowed is True


def test_evaluate_denies_recent_violation(tmp_project: Path) -> None:
    """A serious incident must be sticky: high EWMA alone doesn't reopen the gate."""
    trusts = [0.9] * 10
    cats = ["success"] * 10
    cats[7] = "failure"  # violation 3 records ago, within the holdoff window
    state = _record_state(TrustLedger(tmp_project), trusts, cats)
    decision = evaluate_gate(state, TrustConfig(violation_holdoff_turns=5))
    assert decision.allowed is False


def test_evaluate_violation_outside_holdoff_ok(tmp_project: Path) -> None:
    trusts = [0.9] * 10
    cats = ["success"] * 10
    cats[1] = "failure"  # long since past
    state = _record_state(TrustLedger(tmp_project), trusts, cats)
    decision = evaluate_gate(state, TrustConfig(violation_holdoff_turns=5))
    assert decision.allowed is True


def test_gate_check_fail_closed_on_missing_state(tmp_project: Path) -> None:
    decision = TrustGate(tmp_project).check()
    assert decision.allowed is False


def test_gate_check_fail_closed_on_tamper(tmp_project: Path) -> None:
    ledger = TrustLedger(tmp_project)
    _record_state(ledger, [0.9] * 5)
    # Flip a byte in the ledger.
    raw = ledger.ledger_path.read_bytes()
    ledger.ledger_path.write_bytes(raw.replace(b'"t1": 0.9', b'"t1": 1.0'))

    decision = TrustGate(tmp_project).check()
    assert decision.allowed is False
