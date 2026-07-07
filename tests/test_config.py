from __future__ import annotations

from pathlib import Path

from agent_riggs.config import load_config


def test_load_defaults_when_no_user_config(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    assert config.trust.score_success == 1.0
    assert config.trust.alpha_short == 0.4
    assert config.store.path == ".riggs/store.duckdb"


def test_user_config_overrides_non_trust_sections(tmp_project: Path) -> None:
    user_config = tmp_project / ".riggs" / "config.toml"
    user_config.write_text('[ratchet]\nmin_frequency = 9\n\n[store]\npath = "custom.duckdb"\n')
    config = load_config(tmp_project)
    assert config.ratchet.min_frequency == 9
    assert config.store.path == "custom.duckdb"


def test_project_config_cannot_override_trust_policy(tmp_project: Path) -> None:
    """[trust] in the subject-writable project config must be ignored.

    Otherwise the scored subject could weaken its own scoring and gate
    thresholds (GHSA hardening).
    """
    user_config = tmp_project / ".riggs" / "config.toml"
    user_config.write_text("[trust]\nscore_failure = 1.0\ngate_threshold = 0.0\n")
    config = load_config(tmp_project)
    assert config.trust.score_failure == 0.2  # shipped default, not 1.0
    assert config.trust.gate_threshold == 0.5


def test_state_dir_policy_overrides_trust_policy(tmp_project: Path) -> None:
    """policy.toml in the out-of-tree state dir is the trusted override path."""
    from agent_riggs.statedir import state_dir_for

    state_dir = state_dir_for(tmp_project)
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "policy.toml").write_text("[trust]\ngate_threshold = 0.7\n")
    config = load_config(tmp_project)
    assert config.trust.gate_threshold == 0.7
    # Untouched values keep their defaults
    assert config.trust.alpha_short == 0.4


def test_config_sections_are_typed(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    assert isinstance(config.trust.score_success, float)
    assert isinstance(config.ratchet.min_frequency, int)
    assert isinstance(config.store.path, str)
