"""Apply and record ratchet promotion decisions."""

from __future__ import annotations

import json
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import tomli_w


def record_decision(store, candidate, decision, reason=None, config_change=None):
    row = store.execute("SELECT coalesce(max(decision_id), 0) FROM ratchet_decisions").fetchone()
    next_id = row[0] + 1

    store.execute(
        """
        INSERT INTO ratchet_decisions (decision_id, decided_at, candidate_type, candidate_key,
            decision, reason, evidence, config_change)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            next_id,
            datetime.now(UTC),
            candidate.candidate_type,
            candidate.candidate_key,
            decision,
            reason,
            json.dumps(candidate.evidence),
            json.dumps(config_change) if config_change else None,
        ],
    )


def apply_nudge_promotion(project_root: Path, plugin: str, mode: str = "redirect") -> dict:
    """Escalate a kibitzer interceptor plugin's mode in .kibitzer/config.toml.

    This is the ONE place agent-riggs writes to a sibling tool's config, and
    it only runs from the human-gated `ratchet promote` command. Kibitzer
    merges the project-local .kibitzer/config.toml over its defaults.
    """
    config_path = project_root / ".kibitzer" / "config.toml"
    data: dict = {}
    if config_path.exists():
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    plugins = data.setdefault("plugins", {})
    entry = plugins.setdefault(plugin, {})
    previous = entry.get("mode")
    entry["mode"] = mode

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(tomli_w.dumps(data), encoding="utf-8")

    return {
        "file": str(config_path),
        "plugin": plugin,
        "from_mode": previous,
        "to_mode": mode,
    }
