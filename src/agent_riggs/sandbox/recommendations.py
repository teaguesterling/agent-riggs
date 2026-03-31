"""Sandbox tightening recommendations. Stub — requires blq."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_riggs.config import SandboxConfig


@dataclass
class SandboxRecommendation:
    command: str
    metric: str
    current: int
    suggested: int
    reason: str

def recommend_tightening(grades: list[dict[str, Any]], config: SandboxConfig) -> list[SandboxRecommendation]:
    return []
