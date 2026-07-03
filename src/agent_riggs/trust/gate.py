"""Fail-closed trust gate.

This is the enforcement point that consumes the verified trust ledger. It is
invoked on every capability-expanding path:

* ``agent-riggs gate`` (CLI, exit code contract for harness hooks)
* the ``RiggsGate`` MCP tool
* ratchet **tool promotions** (capability-expanding; constraint promotions
  tighten and are never gated)
* the LOOSEN recommendation published to ``.kibitzer/state.json``

Deny conditions (fail closed — unknown never means trusted):

* trust state absent → deny (a subject with no verified history is *low*
  trust, not max)
* trust state fails integrity verification → deny
* short- or session-window trust below ``gate_threshold`` → deny
* a failure-class event within the last ``violation_holdoff_turns`` records
  → deny (a serious incident must not be washed out by a burst of successes)

The gate loads its policy via :func:`agent_riggs.config.load_trusted_trust_config`,
which ignores the subject-writable ``.riggs/config.toml``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_riggs.config import TrustConfig, load_trusted_trust_config
from agent_riggs.trust.ledger import LedgerState, TrustLedger

#: Ledger record categories that count as violations for the holdoff window.
VIOLATION_CATEGORIES = frozenset({"failure", "path_denial", "repeated_failure"})


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str
    trust_1: float
    trust_5: float
    trust_15: float
    state: str  # ledger status: "ok" | "absent" | "tampered"


def _deny(reason: str, state: LedgerState) -> GateDecision:
    last = state.last
    return GateDecision(
        allowed=False,
        reason=reason,
        trust_1=last.t1 if last else 0.0,
        trust_5=last.t5 if last else 0.0,
        trust_15=last.t15 if last else 0.0,
        state=state.status,
    )


def evaluate_gate(state: LedgerState, config: TrustConfig) -> GateDecision:
    """Pure gate decision over a verified ledger state. Fail closed."""
    if state.status == "tampered":
        return GateDecision(
            allowed=False,
            reason=f"trust ledger failed integrity verification ({state.detail}); fail closed",
            trust_1=0.0,
            trust_5=0.0,
            trust_15=0.0,
            state=state.status,
        )
    if state.status != "ok" or not state.records:
        return GateDecision(
            allowed=False,
            reason="no verified trust history; unknown subjects are low trust (fail closed)",
            trust_1=0.0,
            trust_5=0.0,
            trust_15=0.0,
            state=state.status,
        )

    last = state.records[-1]
    if min(last.t1, last.t5) < config.gate_threshold:
        return _deny(
            f"trust below gate threshold: t1={last.t1:.2f}, t5={last.t5:.2f} "
            f"< {config.gate_threshold}",
            state,
        )

    holdoff = max(config.violation_holdoff_turns, 0)
    if holdoff:
        recent = state.records[-holdoff:]
        violations = [r for r in recent if r.category in VIOLATION_CATEGORIES]
        if violations:
            return _deny(
                f"{len(violations)} violation(s) within the last {holdoff} turns "
                f"(most recent: {violations[-1].category})",
                state,
            )

    return GateDecision(
        allowed=True,
        reason=(
            f"verified trust t1={last.t1:.2f}, t5={last.t5:.2f} "
            f"over {len(state.records)} turns"
        ),
        trust_1=last.t1,
        trust_5=last.t5,
        trust_15=last.t15,
        state=state.status,
    )


class TrustGate:
    """Loads verified trust state and applies the gate policy."""

    def __init__(
        self,
        project_root: Path | str,
        config: TrustConfig | None = None,
        ledger: TrustLedger | None = None,
    ) -> None:
        self.project_root = Path(project_root)
        # Policy comes from trusted sources only; never from the project tree.
        self.config = config if config is not None else load_trusted_trust_config(project_root)
        self.ledger = ledger if ledger is not None else TrustLedger(project_root)

    def check(self) -> GateDecision:
        return evaluate_gate(self.ledger.verify(), self.config)
