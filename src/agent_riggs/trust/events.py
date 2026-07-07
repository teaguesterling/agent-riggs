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


class Provenance(Enum):
    """How an event's outcome was established.

    OBSERVED: recorded by an independent process from the actual outcome
    (e.g. a real exit code). May raise trust.

    SELF_REPORTED: asserted by the scored subject, or read from a file the
    subject can write. Must never raise trust — the pipeline applies these
    with ``allow_increase=False`` so only claims against interest count.
    """

    OBSERVED = "observed"
    SELF_REPORTED = "self_reported"


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
    # Safe default: unknown provenance is treated as self-reported.
    provenance: Provenance = Provenance.SELF_REPORTED
    # Stable identity for ingest idempotency; derived by the source.
    event_uid: str | None = None
