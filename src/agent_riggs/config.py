"""Configuration loading: merge defaults with .riggs/config.toml.

Security note: the ``[trust]`` section is *never* read from the project's
``.riggs/config.toml``. That file is writable by the scored subject, and
trust scoring/gating policy derived from it would be forgeable (the subject
could set ``score_failure = 1.0`` or ``gate_threshold = 0.0``). Trust policy
comes from the shipped defaults, optionally overridden by ``policy.toml`` in
the out-of-tree state directory (see :mod:`agent_riggs.statedir`).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from importlib import resources
from pathlib import Path
from typing import Any

from agent_riggs.statedir import state_dir_for


@dataclass
class TrustConfig:
    score_success: float = 1.0
    score_suboptimal: float = 0.7
    score_mode_switch_agent: float = 0.8
    score_mode_switch_controller: float = 0.3
    score_failure: float = 0.2
    score_path_denial: float = 0.1
    score_repeated_failure: float = 0.0
    alpha_short: float = 0.4
    alpha_session: float = 0.08
    alpha_baseline: float = 0.02
    tighten_threshold: float = 0.3
    auto_tighten_threshold: float = 0.5
    loosen_threshold: float = 0.9
    loosen_sustained_turns: int = 20
    # Seed for a subject with no verified history: LOW, must accrue.
    initial_trust: float = 0.4
    # The gate denies when min(t1, t5) is below this.
    gate_threshold: float = 0.5
    # A violation within this many ledger records keeps the gate closed.
    violation_holdoff_turns: int = 20


@dataclass
class RatchetConfig:
    min_frequency: int = 5
    min_sessions: int = 3
    min_success_rate: float = 0.8
    lookback_days: int = 30
    # Heed gate for nudged tool promotions (kibitzer A/B evidence).
    # Frequency alone never qualifies a candidate.
    min_nudge_trials: int = 5
    min_heed_rate: float = 0.25
    min_heed_lift: float = 0.0


@dataclass
class SandboxConfig:
    memory_headroom: float = 2.0
    timeout_headroom: float = 3.0
    cpu_headroom: float = 2.0
    min_runs_for_tightening: int = 5


@dataclass
class MetricsConfig:
    default_period_days: int = 30


@dataclass
class BriefingConfig:
    lookback_days: int = 14
    top_tools: int = 5


@dataclass
class StoreConfig:
    path: str = ".riggs/store.duckdb"


@dataclass
class RiggsConfig:
    trust: TrustConfig = field(default_factory=TrustConfig)
    ratchet: RatchetConfig = field(default_factory=RatchetConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    briefing: BriefingConfig = field(default_factory=BriefingConfig)
    store: StoreConfig = field(default_factory=StoreConfig)


def _load_defaults() -> dict[str, Any]:
    """Load the shipped defaults/config.toml."""
    defaults_ref = resources.files("agent_riggs") / "defaults" / "config.toml"
    return tomllib.loads(defaults_ref.read_text(encoding="utf-8"))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge override into base, recursing into nested dicts."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _dict_to_dataclass(cls: type, data: dict[str, Any]) -> Any:
    """Convert a dict to a dataclass, ignoring unknown keys."""
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})


def load_trusted_trust_config(project_root: Path | str) -> TrustConfig:
    """Load the trust policy from trusted sources only.

    Sources, in order: shipped defaults, then ``policy.toml`` in the
    out-of-tree state directory. The subject-writable
    ``.riggs/config.toml`` is deliberately ignored — trust policy read from
    the project tree would let the scored subject weaken its own scoring
    and gate thresholds.
    """
    merged = _load_defaults().get("trust", {})
    policy_path = state_dir_for(project_root) / "policy.toml"
    if policy_path.exists():
        policy = tomllib.loads(policy_path.read_text(encoding="utf-8"))
        merged = _deep_merge(merged, policy.get("trust", {}))
    return _dict_to_dataclass(TrustConfig, merged)


def load_config(project_root: Path) -> RiggsConfig:
    """Load config: defaults merged with .riggs/config.toml.

    The ``[trust]`` section is sourced via :func:`load_trusted_trust_config`
    and cannot be overridden from the project tree (see module docstring).
    """
    merged = _load_defaults()

    user_path = project_root / ".riggs" / "config.toml"
    if user_path.exists():
        user = tomllib.loads(user_path.read_text(encoding="utf-8"))
        merged = _deep_merge(merged, user)

    return RiggsConfig(
        trust=load_trusted_trust_config(project_root),
        ratchet=_dict_to_dataclass(RatchetConfig, merged.get("ratchet", {})),
        sandbox=_dict_to_dataclass(SandboxConfig, merged.get("sandbox", {})),
        metrics=_dict_to_dataclass(MetricsConfig, merged.get("metrics", {})),
        briefing=_dict_to_dataclass(BriefingConfig, merged.get("briefing", {})),
        store=_dict_to_dataclass(StoreConfig, merged.get("store", {})),
    )
