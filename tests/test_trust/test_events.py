from __future__ import annotations

from datetime import datetime, timezone

from agent_riggs.trust.events import TurnEvent, EventCategory


def test_turn_event_creation() -> None:
    event = TurnEvent(
        session_id="sess-1",
        turn_number=1,
        timestamp=datetime.now(timezone.utc),
        tool_name="Read",
        tool_success=True,
        mode="implement",
        event_category=EventCategory.SUCCESS,
        metadata={},
    )
    assert event.session_id == "sess-1"
    assert event.event_category == EventCategory.SUCCESS


def test_event_category_values() -> None:
    assert EventCategory.SUCCESS.value == "success"
    assert EventCategory.PATH_DENIAL.value == "path_denial"
    assert EventCategory.FAILURE.value == "failure"
    assert EventCategory.REPEATED_FAILURE.value == "repeated_failure"
