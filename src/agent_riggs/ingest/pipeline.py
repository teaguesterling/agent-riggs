"""Ingest pipeline: discover sources, read events, score, record, store.

Integrity model:

* The authoritative trust state is the out-of-tree, HMAC-chained
  :class:`~agent_riggs.trust.ledger.TrustLedger` — not the project-local
  DuckDB store, which is analytics only and writable by the scored subject.
* The EWMA is seeded from the *verified* ledger; with no ledger it starts at
  ``TrustConfig.initial_trust`` (low — an unknown subject must accrue trust).
* Events whose provenance is SELF_REPORTED are applied with
  ``allow_increase=False``: they can hold or lower trust, never raise it.
* Ingest is idempotent: each event carries a stable ``event_uid`` and events
  already present in the ledger are skipped, so replaying ``ingest`` (or
  re-reading the same logs) cannot re-count evidence.
* Events are applied in timestamp order across all sources, so the result
  does not depend on source iteration order.
* If the ledger fails verification, ingest refuses to run
  (:class:`~agent_riggs.trust.ledger.LedgerIntegrityError`) rather than
  build new trust on top of tampered state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from agent_riggs.config import TrustConfig
from agent_riggs.ingest.sources.base import Source
from agent_riggs.store import Store
from agent_riggs.trust.events import EventCategory, Provenance, TurnEvent
from agent_riggs.trust.ewma import TrustEWMA
from agent_riggs.trust.ledger import LedgerIntegrityError, LedgerState, TrustLedger
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
    duplicates_skipped: int = 0
    sources_read: list[str] = field(default_factory=list)


def _fallback_uid(source_name: str, event: TurnEvent) -> str:
    raw = (
        f"{source_name}:{event.session_id}:{event.turn_number}:"
        f"{event.timestamp.isoformat()}:{event.event_category.value}"
    )
    return f"{source_name}:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _sort_key(event: TurnEvent) -> datetime:
    ts = event.timestamp
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)


def ewma_from_ledger(state: LedgerState, config: TrustConfig) -> TrustEWMA:
    """Seed the EWMA from verified ledger state; unknown subjects start LOW."""
    ewma = TrustEWMA(
        alpha_short=config.alpha_short,
        alpha_session=config.alpha_session,
        alpha_baseline=config.alpha_baseline,
        initial=config.initial_trust,
    )
    last = state.last
    if state.status == "ok" and last is not None:
        ewma.t1 = last.t1
        ewma.t5 = last.t5
        ewma.t15 = last.t15
    return ewma


def ingest(
    store: Store,
    project_root: Path,
    sources: list[Source],
    trust_config: TrustConfig,
    since: object | None = None,
    ledger: TrustLedger | None = None,
) -> IngestResult:
    """Pull events from all discovered sources, score, record, and store."""
    result = IngestResult()
    project = project_root.name

    ledger = ledger if ledger is not None else TrustLedger(project_root)
    state = ledger.verify()
    if state.status == "tampered":
        raise LedgerIntegrityError(
            f"trust ledger failed integrity verification ({state.detail}); "
            "refusing to ingest on top of tampered state"
        )
    known_uids = {r.event_uid for r in state.records}

    ewma = ewma_from_ledger(state, trust_config)
    next_turn_id = _next_id(store, "turns", "turn_id")

    pending: list[tuple[str, TurnEvent]] = []
    for source in sources:
        if not source.discover(project_root):
            continue
        result.sources_read.append(source.name)
        for event in source.read_events(project_root, since):
            pending.append((source.name, event))

    # Apply in timestamp order so results don't depend on source order.
    pending.sort(key=lambda pair: _sort_key(pair[1]))

    for source_name, event in pending:
        uid = event.event_uid or _fallback_uid(source_name, event)
        if uid in known_uids:
            result.duplicates_skipped += 1
            continue
        known_uids.add(uid)

        score = score_event(event, trust_config)
        observed = event.provenance is Provenance.OBSERVED
        t1, t5, t15 = ewma.update(score, allow_increase=observed)
        turn_id = next_turn_id
        next_turn_id += 1

        ledger.append(
            event_uid=uid,
            session_id=event.session_id,
            category=event.event_category.value,
            score=score,
            t1=t1,
            t5=t5,
            t15=t15,
            observed=observed,
            timestamp=event.timestamp,
        )
        _store_turn(store, turn_id, project, event, score, t1, t5, t15)
        result.turns_ingested += 1

        if event.event_category in _FAILURE_CATEGORIES:
            _store_failure(store, turn_id, project, event, score)
            result.failures_recorded += 1

    return result


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
