from __future__ import annotations

from agent_riggs.metrics.trends import detect_trends


def test_detect_improving_trend():
    current = {"structured_tool_fraction": 0.72}
    previous = {"structured_tool_fraction": 0.58}
    trends = detect_trends(current, previous)
    assert any(
        t.metric == "structured_tool_fraction" and t.direction == "improving" for t in trends
    )


def test_detect_declining_trend():
    current = {"structured_tool_fraction": 0.40}
    previous = {"structured_tool_fraction": 0.60}
    trends = detect_trends(current, previous)
    assert any(
        t.metric == "structured_tool_fraction" and t.direction == "declining" for t in trends
    )


def test_no_trend_when_stable():
    current = {"structured_tool_fraction": 0.71}
    previous = {"structured_tool_fraction": 0.70}
    trends = detect_trends(current, previous)
    assert len(trends) == 0
