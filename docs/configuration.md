# Configuration Reference

Agent Riggs is configured through `.riggs/config.toml`. When you run `agent-riggs init`, a copy of the defaults is placed in your project. Any value you set overrides the default; values you omit keep their defaults.

## [trust]

Trust scoring weights, EWMA parameters, and gate policy.

**Security note:** unlike every other section, `[trust]` is **not** read from
the project's `.riggs/config.toml` — that file is writable by the scored
agent, which could otherwise weaken its own scoring and gate thresholds. The
values here are the shipped defaults; to override them, put a `[trust]`
section in `policy.toml` inside the out-of-tree state directory (see
[Trust Integrity](trust-integrity.md)).

### Scoring Weights

Each turn event gets a score between 0 and 1. These weights define the mapping:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `score_success` | float | 1.0 | Successful tool call in the correct mode |
| `score_suboptimal` | float | 0.7 | Successful call, but a structured alternative exists |
| `score_mode_switch_agent` | float | 0.8 | Agent initiated a mode switch (appropriate adaptation) |
| `score_mode_switch_controller` | float | 0.3 | Controller forced a mode switch (System 3 had to intervene) |
| `score_failure` | float | 0.2 | Tool call failed |
| `score_path_denial` | float | 0.1 | Agent tried to write outside mode bounds |
| `score_repeated_failure` | float | 0.0 | Agent is stuck in a failure loop |

### EWMA Parameters

Three exponentially weighted moving averages track trust at different timescales:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `alpha_short` | float | 0.4 | Decay rate for trust_1 (~5 turn half-life). Higher = more responsive. |
| `alpha_session` | float | 0.08 | Decay rate for trust_5 (~25 turn half-life). Tracks session trajectory. |
| `alpha_baseline` | float | 0.02 | Decay rate for trust_15 (~100 turn half-life). Project baseline. |

### Transition Thresholds

When trust crosses these thresholds, Riggs generates recommendations:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tighten_threshold` | float | 0.3 | trust_1 below this triggers a tightening recommendation |
| `auto_tighten_threshold` | float | 0.5 | trust_5 below this (combined with low trust_1) triggers auto-tighten |
| `loosen_threshold` | float | 0.9 | trust_1 above this may trigger a loosening suggestion |
| `loosen_sustained_turns` | int | 20 | Consecutive trailing turns of high trust required before suggesting loosening |

### Gate Policy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `initial_trust` | float | 0.4 | EWMA seed for a subject with no verified history (below the gate threshold: trust must be accrued) |
| `gate_threshold` | float | 0.5 | The gate denies when min(trust_1, trust_5) is below this |
| `violation_holdoff_turns` | int | 20 | A failure-class event within this many ledger records keeps the gate closed |

## [ratchet]

Controls when ratchet candidates are surfaced.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `min_frequency` | int | 5 | Minimum occurrences of a pattern before it becomes a candidate |
| `min_sessions` | int | 3 | Minimum distinct sessions where the pattern appears |
| `min_success_rate` | float | 0.8 | Minimum success rate for tool promotion candidates |
| `lookback_days` | int | 30 | Time window for candidate identification |

**Tuning guidance:** If you want candidates to appear faster, lower `min_frequency` and `min_sessions`. If you're getting too many noisy candidates, raise them. The `min_success_rate` filters out patterns that work sometimes but fail often — you generally want to keep this high (0.8+).

## [sandbox]

Controls sandbox tightening recommendations. Only active when blq is installed.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `memory_headroom` | float | 2.0 | Multiplier for memory limit recommendations (p95 * this = suggested limit) |
| `timeout_headroom` | float | 3.0 | Multiplier for timeout recommendations |
| `cpu_headroom` | float | 2.0 | Multiplier for CPU limit recommendations |
| `min_runs_for_tightening` | int | 5 | Minimum command runs before recommending tightening |

## [metrics]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_period_days` | int | 30 | Default analysis window for `agent-riggs metrics` |

## [store]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `path` | string | `".riggs/store.duckdb"` | Path to the DuckDB database file (relative to project root) |

## Example: Tuning for a New Project

A new project with few sessions might want faster feedback:

```toml
[ratchet]
min_frequency = 3      # Lower threshold for candidates
min_sessions = 2       # Don't wait for 3 sessions
lookback_days = 14     # Shorter window
```

A mature project with many sessions might want stricter filtering:

```toml
[ratchet]
min_frequency = 10
min_sessions = 5
min_success_rate = 0.9
lookback_days = 60
```
