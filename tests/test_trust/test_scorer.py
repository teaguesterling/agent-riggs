from __future__ import annotations

from datetime import UTC, datetime

from agent_riggs.config import TrustConfig
from agent_riggs.trust.events import EventCategory, TurnEvent
from agent_riggs.trust.scorer import score_event


def _make_event(category: EventCategory) -> TurnEvent:
    return TurnEvent(
        session_id="sess-1",
        turn_number=1,
        timestamp=datetime.now(UTC),
        tool_name="Read",
        tool_success=True,
        mode="implement",
        event_category=category,
        metadata={},
    )


def test_score_success() -> None:
    config = TrustConfig()
    assert score_event(_make_event(EventCategory.SUCCESS), config) == 1.0


def test_score_suboptimal() -> None:
    config = TrustConfig()
    assert score_event(_make_event(EventCategory.SUBOPTIMAL), config) == 0.7


def test_score_path_denial() -> None:
    config = TrustConfig()
    assert score_event(_make_event(EventCategory.PATH_DENIAL), config) == 0.1


def test_score_repeated_failure() -> None:
    config = TrustConfig()
    assert score_event(_make_event(EventCategory.REPEATED_FAILURE), config) == 0.0


def test_score_with_custom_config() -> None:
    config = TrustConfig(score_success=0.5)
    assert score_event(_make_event(EventCategory.SUCCESS), config) == 0.5


def test_score_all_categories_are_handled() -> None:
    """Every EventCategory should produce a valid score."""
    config = TrustConfig()
    for category in EventCategory:
        score = score_event(_make_event(category), config)
        assert 0.0 <= score <= 1.0, f"{category} produced invalid score {score}"
