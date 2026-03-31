"""Bridge to blq sandbox commands. Stub — requires blq."""

from __future__ import annotations

import subprocess


def profile_command(command: str) -> str:
    result = subprocess.run(["blq", "sandbox", "profile", command], capture_output=True, text=True)
    return result.stdout


def apply_recommendation(command: str) -> str:
    result = subprocess.run(["blq", "sandbox", "tighten", command], capture_output=True, text=True)
    return result.stdout
