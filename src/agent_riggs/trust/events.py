"""Turn events — the unit of observation for the trust engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventCategory(Enum):
    SUCCESS = "success"
    SUBOPTIMAL = "suboptimal"
    MODE_SWITCH_AGENT = "mode_switch_agent"
    MODE_SWITCH_CONTROLLER = "mode_switch_controller"
    FAILURE = "failure"
    PATH_DENIAL = "path_denial"
    REPEATED_FAILURE = "repeated_failure"


@dataclass(frozen=True)
class TurnEvent:
    session_id: str
    turn_number: int
    timestamp: datetime
    tool_name: str | None
    tool_success: bool | None
    mode: str | None
    event_category: EventCategory
    metadata: dict[str, Any] = field(default_factory=dict)
