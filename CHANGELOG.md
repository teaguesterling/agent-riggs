# Changelog

## 0.2.0 — 2026-07-18

The Step 1 "value layer" release plus the trust-integrity rework:
agent-riggs now ingests from the full Rigged suite, re-ingests
incrementally, gates ratchet promotion on measured heed lift instead of
raw frequency, and derives trust from tamper-evident observed signals.

### Added
- New ingest sources: jetsam (git workflow events) and nudge-trials
  (kibitzer A/B trial outcomes), joining the fledgling, lackpy, and blq
  sources added since 0.1.1.
- Incremental ingest cursors (`ingest_state` table): re-ingest is fast and
  idempotent — each source resumes from its last cursor instead of
  rescanning. Cursors are the performance layer; the trust ledger's
  per-event UIDs are the correctness layer.
- Heed-gated ratchet candidates: promotion is gated on kibitzer A/B heed
  lift; frequency-only promotion has been removed.
- `ratchet promote` now writes `[plugins.X] mode` into the project's
  `.kibitzer/config.toml`, so promotions take effect in the live kibitzer
  config.
- Rewritten project brief: `brief` now produces a real, non-empty briefing
  from ingested data.

### Security
- Trust state integrity rework (GHSA-j5cw-vqqp-pmm5, #3, #4): authoritative
  trust state moves to an out-of-tree, HMAC-chained append-only ledger; the
  project-local DuckDB store is analytics only. Absent or unverifiable
  ledger state reads as low trust, never max (fail closed).
- Event provenance: OBSERVED outcomes (e.g. blq exit codes) may raise
  trust; SELF_REPORTED logs (kibitzer/lackpy/fledgling) can hold or lower
  trust but never raise it.
- New fail-closed trust gate on capability-expanding paths: `agent-riggs
  gate` CLI (exit 0/2), the RiggsGate MCP tool, ratchet tool promotions,
  and the LOOSEN recommendation published to `.kibitzer/state.json`.
- Trust policy is no longer read from the subject-writable
  `.riggs/config.toml`; it comes from shipped defaults plus `policy.toml`
  in the state directory.

### Changed
- Kibitzer intercepts that carry a `suggested_tool` are now classified as
  suboptimal tool choices.
- Schema migration: `turns` table gains a `source` column.
- Ingest applies events in timestamp order across sources and skips
  malformed log lines instead of aborting.

## 0.1.1 — earlier

- Add pytz dependency; derive turn/decision IDs from the store.

## 0.1.0 — earlier

- Initial release: DuckDB store, ingest pipeline, trust scoring (EWMA),
  ratchet candidates, briefing, MCP server, PyPI publish workflow.
