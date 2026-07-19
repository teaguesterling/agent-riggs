"""Ingest pipeline: discover sources, read events, score, record, store.

Ingest is incremental: each source's high-water mark (an opaque JSON cursor)
is persisted per (project, source) in the ingest_state table, so re-running
ingest only reads new data.

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
  re-reading the same logs) cannot re-count evidence. Cursors are a
  performance layer on top; the ledger is the correctness layer.
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
from agent_riggs.ingest.sources.base import Cursor, Source
from agent_riggs.ingest.sources.nudge_trials import NudgeTrialsSource
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
    trials_ingested: int = 0
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
    trials_source: NudgeTrialsSource | None = None,
    ledger: TrustLedger | None = None,
) -> IngestResult:
    """Pull new events from all discovered sources, score, record, and store."""
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
    cursors: dict[str, Cursor] = {}
    for source in sources:
        if not source.discover(project_root):
            continue
        result.sources_read.append(source.name)
        cursor = _load_cursor(store, project, source.name)
        batch = source.read_events(project_root, cursor)
        cursors[source.name] = batch.cursor
        for event in batch.events:
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
        _store_turn(store, turn_id, project, source_name, event, score, t1, t5, t15)
        result.turns_ingested += 1

        if event.event_category in _FAILURE_CATEGORIES:
            _store_failure(store, turn_id, project, event, score)
            result.failures_recorded += 1

    # Cursors advance only after all new events were applied, so a failed
    # run re-reads its data (the ledger's uid dedup makes replays safe).
    for source_name, cursor in cursors.items():
        _save_cursor(store, project, source_name, cursor)

    if trials_source is not None and trials_source.discover(project_root):
        result.trials_ingested = _ingest_trials(store, project, trials_source)
        if result.trials_ingested or trials_source.name not in result.sources_read:
            result.sources_read.append(trials_source.name)

    return result


def _ingest_trials(store: Store, project: str, source: NudgeTrialsSource) -> int:
    cursor = _load_cursor(store, project, source.name)
    trials, new_cursor = source.read_trials(cursor)

    next_trial_id = _next_id(store, "nudge_trials", "trial_id")
    for trial in trials:
        store.execute(
            """
            INSERT INTO nudge_trials (trial_id, plugin, arm, heed, turns_to_heed,
                session_id, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                next_trial_id,
                trial.plugin,
                trial.arm,
                trial.heed,
                trial.turns_to_heed,
                trial.session_id,
                trial.ts,
            ],
        )
        next_trial_id += 1

    _save_cursor(store, project, source.name, new_cursor)
    return len(trials)


def _load_cursor(store: Store, project: str, source: str) -> Cursor | None:
    row = store.execute(
        "SELECT cursor FROM ingest_state WHERE project = ? AND source = ?",
        [project, source],
    ).fetchone()
    if row and row[0]:
        return json.loads(row[0])
    return None


def _save_cursor(store: Store, project: str, source: str, cursor: Cursor) -> None:
    store.execute(
        """
        INSERT OR REPLACE INTO ingest_state (project, source, cursor, last_ingested_at)
        VALUES (?, ?, ?, ?)
        """,
        [project, source, json.dumps(cursor), datetime.now(UTC)],
    )


def _store_turn(store, turn_id, project, source, event, score, t1, t5, t15):
    store.execute(
        """
        INSERT INTO turns (
            turn_id, session_id, project, turn_number, timestamp,
            tool_name, tool_success, mode, trust_score,
            trust_1, trust_5, trust_15, event_category, metadata, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            source,
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
