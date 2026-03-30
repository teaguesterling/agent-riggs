"""Per-turn scoring function. Pure, no side effects."""

from __future__ import annotations

from agent_riggs.config import TrustConfig
from agent_riggs.trust.events import EventCategory, TurnEvent

_CATEGORY_TO_CONFIG_KEY: dict[EventCategory, str] = {
    EventCategory.SUCCESS: "score_success",
    EventCategory.SUBOPTIMAL: "score_suboptimal",
    EventCategory.MODE_SWITCH_AGENT: "score_mode_switch_agent",
    EventCategory.MODE_SWITCH_CONTROLLER: "score_mode_switch_controller",
    EventCategory.FAILURE: "score_failure",
    EventCategory.PATH_DENIAL: "score_path_denial",
    EventCategory.REPEATED_FAILURE: "score_repeated_failure",
}


def score_event(event: TurnEvent, config: TrustConfig) -> float:
    """Score a turn event (0-1) based on its category and config."""
    key = _CATEGORY_TO_CONFIG_KEY[event.event_category]
    return float(getattr(config, key))
