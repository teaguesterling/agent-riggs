"""Ingest plugin — wires ingest pipeline into the service layer."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

import click

from agent_riggs.ingest.pipeline import IngestResult, ingest
from agent_riggs.ingest.sources.blq import BlqSource
from agent_riggs.ingest.sources.fledgling import FledglingSource
from agent_riggs.ingest.sources.kibitzer import KibitzerSource
from agent_riggs.ingest.sources.lackpy import LackpySource

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService


class IngestPlugin:
    name = "ingest"

    def bind(self, service: RiggsService) -> None:
        self.service = service

    def schema_ddl(self) -> list[str]:
        return []

    def cli_commands(self) -> list[click.Command]:
        return []

    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return []

    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return []

    def run(self, since: datetime | None = None) -> IngestResult:
        sources = self._discover_sources()
        result = ingest(
            store=self.service.store,
            project_root=self.service.project_root,
            sources=sources,
            trust_config=self.service.config.trust,
            since=since,
        )
        self._publish_recommendation()
        return result

    def _discover_sources(self) -> list[Any]:
        return [BlqSource(), FledglingSource(), KibitzerSource(), LackpySource()]

    def _publish_recommendation(self) -> None:
        """Write the trust-informed recommendation to .kibitzer/state.json.

        This is the advisory half of the loop (kibitzer's mode controller
        reads it); the authoritative decision is the fail-closed gate over
        the verified ledger, which is what the recommendation is derived
        from. state.json lives in the project tree and is not integrity
        protected.
        """
        import json
        from datetime import UTC
        from datetime import datetime as dt

        from agent_riggs.config import load_trusted_trust_config
        from agent_riggs.trust.gate import evaluate_gate
        from agent_riggs.trust.ledger import TrustLedger
        from agent_riggs.trust.transitions import recommend_transition

        root = self.service.project_root
        state_path = root / ".kibitzer" / "state.json"
        if not state_path.parent.exists():
            return

        config = load_trusted_trust_config(root)
        ledger_state = TrustLedger(root).verify()
        gate = evaluate_gate(ledger_state, config)

        recommendation = None
        if ledger_state.status == "ok" and ledger_state.last is not None:
            last = ledger_state.last
            sustained = 0
            for record in reversed(ledger_state.records):
                if record.t1 > config.loosen_threshold:
                    sustained += 1
                else:
                    break
            rec = recommend_transition(
                t1=last.t1,
                t5=last.t5,
                t15=last.t15,
                sustained_high_turns=sustained,
                config=config,
            )
            if rec is not None:
                # LOOSEN is capability-expanding: only publish it if the
                # fail-closed gate agrees.
                if rec.action.value == "loosen" and not gate.allowed:
                    recommendation = {"action": "hold", "reason": gate.reason}
                else:
                    recommendation = {"action": rec.action.value, "reason": rec.reason}
        else:
            recommendation = {
                "action": "auto_tighten",
                "reason": f"trust state {ledger_state.status} (fail closed)",
            }

        try:
            data = json.loads(state_path.read_text()) if state_path.exists() else {}
            if not isinstance(data, dict):
                data = {}
        except (OSError, json.JSONDecodeError):
            data = {}
        data["riggs"] = {
            "recommendation": recommendation,
            "gate": {"allowed": gate.allowed, "reason": gate.reason},
            "trust": {
                "trust_1": gate.trust_1,
                "trust_5": gate.trust_5,
                "trust_15": gate.trust_15,
                "state": gate.state,
            },
            "updated_at": dt.now(UTC).isoformat(),
        }
        state_path.write_text(json.dumps(data, indent=2))
