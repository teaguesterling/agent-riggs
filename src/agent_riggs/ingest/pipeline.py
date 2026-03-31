"""Ingest pipeline: discover sources, read events, score, store."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from agent_riggs.config import TrustConfig
from agent_riggs.ingest.sources.base import Source
from agent_riggs.store import Store
from agent_riggs.trust.events import EventCategory
from agent_riggs.trust.ewma import TrustEWMA
from agent_riggs.trust.scorer import score_event

_FAILURE_CATEGORIES = frozenset(
    {
        EventCategory.FAILURE,
        EventCategory.PATH_DENIAL,
        EventCategory.REPEATED_FAILURE,
    }
)

def _next_id(store: Store, table: str, column: str) -> int:
    """Get the next available ID from a table."""
    row = store.execute(f"SELECT coalesce(max({column}), 0) FROM {table}").fetchone()
    return row[0] + 1


@dataclass
class IngestResult:
    turns_ingested: int = 0
    failures_recorded: int = 0
    sources_read: list[str] = field(default_factory=list)


def ingest(
    store: Store,
    project_root: Path,
    sources: list[Source],
    trust_config: TrustConfig,
    since: object | None = None,
) -> IngestResult:
    """Pull events from all discovered sources, score, and store."""
    result = IngestResult()
    project = project_root.name

    ewma = _load_or_create_ewma(store, project, trust_config)
    next_turn_id = _next_id(store, "turns", "turn_id")

    for source in sources:
        if not source.discover(project_root):
            continue
        result.sources_read.append(source.name)
        events = source.read_events(project_root, since)

        for event in events:
            score = score_event(event, trust_config)
            t1, t5, t15 = ewma.update(score)
            turn_id = next_turn_id
            next_turn_id += 1

            _store_turn(store, turn_id, project, event, score, t1, t5, t15)
            result.turns_ingested += 1

            if event.event_category in _FAILURE_CATEGORIES:
                _store_failure(store, turn_id, project, event, score)
                result.failures_recorded += 1

    return result


def _load_or_create_ewma(store: Store, project: str, config: TrustConfig) -> TrustEWMA:
    row = store.execute(
        """SELECT trust_1, trust_5, trust_15 FROM turns
           WHERE project = ? ORDER BY timestamp DESC LIMIT 1""",
        [project],
    ).fetchone()

    ewma = TrustEWMA(
        alpha_short=config.alpha_short,
        alpha_session=config.alpha_session,
        alpha_baseline=config.alpha_baseline,
    )
    if row:
        ewma.t1 = row[0]
        ewma.t5 = row[1]
        ewma.t15 = row[2]
    return ewma


def _store_turn(store, turn_id, project, event, score, t1, t5, t15):
    store.execute(
        """
        INSERT INTO turns (
            turn_id, session_id, project, turn_number, timestamp,
            tool_name, tool_success, mode, trust_score,
            trust_1, trust_5, trust_15, event_category, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            turn_id,
            event.session_id,
            project,
            event.turn_number,
            event.timestamp,
            event.tool_name,
            event.tool_success,
            event.mode,
            score,
            t1,
            t5,
            t15,
            event.event_category.value,
            json.dumps(event.metadata),
        ],
    )


def _store_failure(store, turn_id, project, event, trust_at_failure):
    store.execute(
        """
        INSERT INTO failure_stream (
            failure_id, turn_id, session_id, project, occurred_at,
            failure_category, tool_name, mode, trust_at_failure, detail
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            turn_id,
            turn_id,
            event.session_id,
            project,
            event.timestamp,
            event.event_category.value,
            event.tool_name,
            event.mode,
            trust_at_failure,
            json.dumps(event.metadata),
        ],
    )
