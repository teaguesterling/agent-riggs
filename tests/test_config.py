from __future__ import annotations

from pathlib import Path

from agent_riggs.config import RiggsConfig, load_config


def test_load_defaults_when_no_user_config(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    assert config.trust.score_success == 1.0
    assert config.trust.alpha_short == 0.4
    assert config.store.path == ".riggs/store.duckdb"


def test_user_config_overrides_defaults(tmp_project: Path) -> None:
    user_config = tmp_project / ".riggs" / "config.toml"
    user_config.write_text('[trust]\nscore_success = 0.9\n')
    config = load_config(tmp_project)
    assert config.trust.score_success == 0.9
    # Other defaults preserved
    assert config.trust.alpha_short == 0.4


def test_config_sections_are_typed(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    assert isinstance(config.trust.score_success, float)
    assert isinstance(config.ratchet.min_frequency, int)
    assert isinstance(config.store.path, str)
