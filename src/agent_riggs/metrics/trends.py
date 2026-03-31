"""Trend detection over configurable windows."""
from __future__ import annotations

from dataclasses import dataclass

_SIGNIFICANCE_THRESHOLD = 0.05

@dataclass
class Trend:
    metric: str
    direction: str
    current: float
    previous: float
    delta: float

_IMPROVING_DIRECTION = {
    "structured_tool_fraction": "up",
    "computation_channel_fraction": "down",
    "failure_rate": "down",
    "trust_trajectory_end": "up",
}

def detect_trends(current, previous, threshold=_SIGNIFICANCE_THRESHOLD):
    trends = []
    for metric, good_direction in _IMPROVING_DIRECTION.items():
        cur = current.get(metric)
        prev = previous.get(metric)
        if cur is None or prev is None: continue
        delta = cur - prev
        if abs(delta) < threshold: continue
        if good_direction == "up":
            direction = "improving" if delta > 0 else "declining"
        else:
            direction = "improving" if delta < 0 else "declining"
        trends.append(Trend(metric=metric, direction=direction, current=cur, previous=prev, delta=delta))
    return trends
