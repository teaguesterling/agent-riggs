"""Ratchet plugin — candidates, promotions, history."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_riggs.ratchet.aggregator import failure_summary
from agent_riggs.ratchet.candidates import (
    find_constraint_candidates,
    find_nudge_candidates,
    nudge_heed_summary,
)
from agent_riggs.ratchet.history import get_history
from agent_riggs.ratchet.promotions import apply_nudge_promotion, record_decision

if TYPE_CHECKING:
    pass

RATCHET_DDL = [
    """
    CREATE TABLE IF NOT EXISTS ratchet_decisions (
        decision_id     BIGINT PRIMARY KEY,
        decided_at      TIMESTAMP NOT NULL,
        candidate_type  VARCHAR NOT NULL,
        candidate_key   VARCHAR NOT NULL,
        decision        VARCHAR NOT NULL,
        reason          VARCHAR,
        evidence        JSON,
        config_change   JSON
    )"""
]


class RatchetPlugin:
    name = "ratchet"

    def bind(self, service):
        self.service = service

    def schema_ddl(self):
        return list(RATCHET_DDL)

    def cli_commands(self):
        return []

    def mcp_resources(self):
        return [("riggs://ratchet", self._ratchet_resource)]

    def mcp_tools(self):
        return [("RiggsFailures", self._failures_tool)]

    def candidates(self):
        project = self.service.project_root.name
        config = self.service.config.ratchet
        store = self.service.store
        return find_nudge_candidates(store, project, config) + find_constraint_candidates(
            store, project, config
        )

    def heed_summary(self):
        """All evaluated nudge-trial evidence, including non-qualifying plugins."""
        return nudge_heed_summary(self.service.store)

    def promote(self, key, reason=None):
        for c in self.candidates():
            if c.candidate_key == key:
                if c.candidate_type in ("tool_promotion", "nudged_tool_promotion"):
                    # Capability-expanding: consult the fail-closed trust gate.
                    # (Constraint promotions tighten and are never gated.)
                    from agent_riggs.trust.gate import TrustGate

                    decision = TrustGate(self.service.project_root).check()
                    if not decision.allowed:
                        raise PermissionError(
                            f"trust gate denied promotion of {key!r}: {decision.reason}"
                        )
                config_change = None
                if c.candidate_type == "nudged_tool_promotion":
                    config_change = apply_nudge_promotion(
                        self.service.project_root, c.evidence["plugin"]
                    )
                record_decision(self.service.store, c, "promoted", reason, config_change)
                return
        raise KeyError(f"No candidate with key: {key}")

    def reject(self, key, reason):
        for c in self.candidates():
            if c.candidate_key == key:
                record_decision(self.service.store, c, "rejected", reason)
                return
        raise KeyError(f"No candidate with key: {key}")

    def history(self):
        return get_history(self.service.store)

    def failures(self, category=None, limit=20):
        return failure_summary(self.service.store, self.service.project_root.name)

    def _ratchet_resource(self):
        candidates = self.candidates()
        if not candidates:
            return "No ratchet candidates pending."
        lines = ["RATCHET CANDIDATES\n"]
        for c in candidates:
            lines.append(f"  [{c.candidate_type}] {c.candidate_key}")
            lines.append(f"    {c.recommendation}")
            lines.append(f"    Evidence: {c.evidence}\n")
        return "\n".join(lines)

    def _failures_tool(self, category=None, limit=20):
        return {"failures": self.failures(category, limit)}
