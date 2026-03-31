"""Metrics plugin — ratchet velocity, self-service ratio, trends."""
from __future__ import annotations

from typing import TYPE_CHECKING

from agent_riggs.metrics.compute import compute_metrics

if TYPE_CHECKING:
    pass

class MetricsPlugin:
    name = "metrics"
    def bind(self, service): self.service = service
    def schema_ddl(self): return []
    def cli_commands(self): return []
    def mcp_resources(self): return [("riggs://metrics", self._metrics_resource)]
    def mcp_tools(self): return [("RiggsMetrics", self._metrics_tool)]
    def compute(self, period_days=None):
        period = period_days or self.service.config.metrics.default_period_days
        return compute_metrics(self.service.store, self.service.project_root.name, period)
    def _metrics_resource(self):
        m = self.compute()
        return (f"RATCHET METRICS ({m.total_sessions} sessions)\n\n"
                f"  Ratchet velocity:        {m.ratchet_velocity} promotions\n"
                f"  Self-service ratio:      {m.structured_tool_fraction:.0%} structured\n"
                f"  Computation channel %:   {m.computation_channel_fraction:.0%}\n"
                f"  Trust trajectory:        {m.trust_trajectory_start:.2f} -> {m.trust_trajectory_end:.2f}\n"
                f"  Failure rate:            {m.failure_rate:.0%}\n")
    def _metrics_tool(self, period=None):
        m = self.compute(period)
        return {"total_sessions": m.total_sessions, "total_turns": m.total_turns,
                "ratchet_velocity": m.ratchet_velocity, "structured_tool_fraction": m.structured_tool_fraction,
                "computation_channel_fraction": m.computation_channel_fraction,
                "trust_trajectory": [m.trust_trajectory_start, m.trust_trajectory_end],
                "failure_rate": m.failure_rate, "mode_distribution": m.mode_distribution}
