"""Trust-informed mode transition recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent_riggs.config import TrustConfig


class TransitionAction(Enum):
    TIGHTEN = "tighten"
    AUTO_TIGHTEN = "auto_tighten"
    LOOSEN = "loosen"
    FLAG_PROJECT = "flag_project"


@dataclass(frozen=True)
class Recommendation:
    action: TransitionAction
    reason: str
    trust_1: float
    trust_5: float


def recommend_transition(
    t1: float,
    t5: float,
    t15: float,
    turn_count: int,
    config: TrustConfig,
) -> Recommendation | None:
    """Evaluate trust state and return a recommendation, or None if healthy.

    Rules are evaluated in priority order (most urgent first).
    """
    # Auto-tighten: both short and session windows are bad
    if t1 < config.tighten_threshold and t5 < config.auto_tighten_threshold:
        return Recommendation(
            action=TransitionAction.AUTO_TIGHTEN,
            reason=f"trust_1={t1:.2f} < {config.tighten_threshold} "
            f"and trust_5={t5:.2f} < {config.auto_tighten_threshold}",
            trust_1=t1,
            trust_5=t5,
        )

    # Tighten: short window is bad
    if t1 < config.tighten_threshold:
        return Recommendation(
            action=TransitionAction.TIGHTEN,
            reason=f"trust_1={t1:.2f} < {config.tighten_threshold}",
            trust_1=t1,
            trust_5=t5,
        )

    # Flag project: baseline is bad
    if t15 < config.auto_tighten_threshold:
        return Recommendation(
            action=TransitionAction.FLAG_PROJECT,
            reason=f"trust_15={t15:.2f} < {config.auto_tighten_threshold}: "
            "project configuration needs review",
            trust_1=t1,
            trust_5=t5,
        )

    # Loosen: sustained high trust
    if (
        t1 > config.loosen_threshold
        and t5 > config.loosen_threshold - 0.1
        and turn_count >= config.loosen_sustained_turns
    ):
        return Recommendation(
            action=TransitionAction.LOOSEN,
            reason=f"trust_1={t1:.2f} and trust_5={t5:.2f} sustained for {turn_count} turns",
            trust_1=t1,
            trust_5=t5,
        )

    return None
