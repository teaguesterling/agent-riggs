"""Out-of-tree state directory for integrity-sensitive trust state.

Trust state must not live in the project tree, because the project tree is
writable by the scored subject (the agent whose behavior the trust score
summarizes). State is keyed by the resolved project path so a subject
cannot redirect it via project-local configuration.

Resolution order for the base directory:

1. ``AGENT_RIGGS_STATE_DIR`` environment variable (deployments and tests)
2. ``$XDG_STATE_HOME/agent-riggs``
3. ``~/.local/state/agent-riggs``

Deployments that want a real ownership boundary should point
``AGENT_RIGGS_STATE_DIR`` at a directory owned by a separate user (or
otherwise outside the subject's write scope) and run ``agent-riggs ingest``
/ ``agent-riggs gate`` under that identity. Inside a single-user account
with no write restrictions, the separation is best-effort only.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

ENV_STATE_DIR = "AGENT_RIGGS_STATE_DIR"


def state_root() -> Path:
    """Base directory for all agent-riggs trust state."""
    env = os.environ.get(ENV_STATE_DIR)
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "agent-riggs"


def state_dir_for(project_root: Path | str) -> Path:
    """Per-project state directory, keyed by the resolved project path.

    The key is derived from the resolved path (not from any project-local
    config) so the scored subject cannot point riggs at a different state
    directory by editing files inside the project.
    """
    resolved = Path(project_root).resolve()
    digest = hashlib.sha256(str(resolved).encode()).hexdigest()[:16]
    return state_root() / f"{resolved.name}-{digest}"
