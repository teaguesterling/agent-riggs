from __future__ import annotations

from agent_riggs.config import TrustConfig
from agent_riggs.trust.transitions import (
    TransitionAction,
    Recommendation,
    recommend_transition,
)


def test_no_recommendation_when_healthy() -> None:
    config = TrustConfig()
    result = recommend_transition(t1=0.9, t5=0.8, t15=0.85, turn_count=10, config=config)
    assert result is None


def test_recommend_tighten_when_t1_low() -> None:
    config = TrustConfig()
    result = recommend_transition(t1=0.2, t5=0.6, t15=0.8, turn_count=10, config=config)
    assert result is not None
    assert result.action == TransitionAction.TIGHTEN


def test_auto_tighten_when_both_low() -> None:
    config = TrustConfig()
    result = recommend_transition(t1=0.2, t5=0.4, t15=0.7, turn_count=10, config=config)
    assert result is not None
    assert result.action == TransitionAction.AUTO_TIGHTEN


def test_suggest_loosen_when_sustained_high() -> None:
    config = TrustConfig()
    result = recommend_transition(t1=0.95, t5=0.85, t15=0.9, turn_count=25, config=config)
    assert result is not None
    assert result.action == TransitionAction.LOOSEN


def test_no_loosen_if_not_sustained() -> None:
    config = TrustConfig()
    result = recommend_transition(t1=0.95, t5=0.85, t15=0.9, turn_count=10, config=config)
    assert result is None


def test_flag_project_when_baseline_low() -> None:
    config = TrustConfig()
    result = recommend_transition(t1=0.8, t5=0.6, t15=0.4, turn_count=10, config=config)
    assert result is not None
    assert result.action == TransitionAction.FLAG_PROJECT
