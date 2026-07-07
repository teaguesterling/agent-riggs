# Trust Integrity Model

The trust score exists to answer one question: *how much should this agent be
trusted right now?* That answer is only useful if the scored agent (the
"subject") cannot manufacture it. This page describes what riggs guarantees,
how, and — just as importantly — where the boundary of the guarantee lies.

## Threat model

The subject is an agent session working in the project tree. It can read and
write anything in the project (including `.riggs/`, `.kibitzer/`, `.lackpy/`,
`.bird/`), run commands, and call riggs's CLI/MCP surfaces. It must not be
able to:

1. reset or rewrite its accumulated trust state,
2. raise its trust by asserting its own success, or
3. pass the trust gate without verified, sufficient, clean history.

## The trust ledger

Authoritative trust state lives in an **append-only, HMAC-chained ledger**
stored *outside the project tree*:

- Location: `$AGENT_RIGGS_STATE_DIR` (if set), else
  `$XDG_STATE_HOME/agent-riggs`, else `~/.local/state/agent-riggs`, in a
  per-project subdirectory keyed by the *resolved project path* — not by any
  project-local config the subject could edit.
- Each record carries an HMAC (key created `0600` in a `0700` directory)
  over its payload chained to the previous record's MAC; a MAC'd head file
  pins the last record so truncation is detected.
- Verification failure of any kind reads as **`tampered`**; a missing ledger
  reads as **`absent`**. Both are treated as **low trust** (fail closed).
  Deleting state never grants trust — it removes it.

The project-local DuckDB store (`.riggs/store.duckdb`) is **analytics only**.
It feeds briefings, metrics, and candidate mining, but nothing security
relevant reads trust values from it: deleting it or inserting forged rows
does not change the verified trust state.

## Provenance: observed vs self-reported

Every ingested event carries a provenance:

- **OBSERVED** — recorded by an independent process from the actual outcome.
  Today that is blq's real exit codes. Observed events update the EWMA
  normally and are the only way to *raise* trust.
- **SELF_REPORTED** — asserted by the subject or read from a file the
  subject can write (kibitzer intercept log, lackpy traces, conversation
  transcripts). These update the EWMA with a per-window
  `min(score, window)` cap: they can hold or *lower* trust (claims against
  interest count) but can never raise it.

An unknown subject starts at `initial_trust` (default 0.4, below the gate
threshold) and must accrue trust from observed evidence. Ingest is
idempotent — every event has a stable UID recorded in the ledger, so
replaying `ingest` or re-reading the same logs cannot re-count evidence.

## The gate

`agent-riggs gate` (CLI, exit `0` allow / `2` deny) and the `RiggsGate` MCP
tool evaluate the fail-closed gate. It is also invoked internally before
capability-expanding actions: ratchet **tool promotions** (constraint
promotions tighten and are never gated) and the LOOSEN recommendation
published to `.kibitzer/state.json`.

Deny conditions:

| Condition | Decision |
|---|---|
| ledger absent | deny — unknown subjects are low trust |
| ledger fails verification | deny — and `ingest` refuses to run |
| `min(t1, t5)` below `gate_threshold` (default 0.5) | deny |
| violation within the last `violation_holdoff_turns` (default 20) records | deny |

The holdoff makes serious incidents *sticky*: a failure cannot be washed out
of the gate by a quick burst of successes even though the short EWMA window
recovers fast.

## Trust policy is not subject-configurable

The `[trust]` section (scoring weights, alphas, thresholds, gate policy) is
**never read from `.riggs/config.toml`** — that file is subject-writable, and
policy read from it would let the subject weaken its own scoring. Policy
comes from the shipped defaults, optionally overridden by `policy.toml` in
the out-of-tree state directory.

## Limits of the guarantee — read this

Riggs is a Python package, not an operating system. The integrity mechanisms
hold **only if the state directory is outside the subject's write scope**:

- **Deployment guidance:** point `AGENT_RIGGS_STATE_DIR` at a directory
  owned by a separate user (or otherwise excluded from the agent's sandbox
  write scope, e.g. via your harness's permission system) and run
  `agent-riggs ingest` / `agent-riggs gate` under that identity. If the
  subject can read the HMAC key or replace the whole state directory with a
  snapshot taken at a high-trust moment, the chain does not protect you.
- **Evidence files are only as trustworthy as their protection.** blq's
  database is classified OBSERVED because blq records real exit codes, but
  it lives in the project tree; a subject that fabricates a plausible blq
  database can still manufacture observed successes. Where that matters,
  protect `.bird/` the same way or ingest from a location the subject
  cannot write.
- **Concurrent ingests** are not locked; interleaved appends will read as
  `tampered` (fail closed — recoverable by consciously resetting the state
  directory, which resets trust to *low*, not high).

Within a single-user account with no write restrictions at all, riggs
degrades to tamper-*evident* bookkeeping against accidental corruption; it
cannot be tamper-*proof* against that account. The gate, provenance rules,
and fail-closed defaults still remove every in-band self-elevation path —
`rm`-to-reset, store edits, self-reported success, config weakening, and
replay.
