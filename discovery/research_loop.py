"""Persistent bounded research-loop coordinator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .autonomy import AutonomousResearchPlanner, ResearchOpportunity
from .engine import DiscoveryEngine
from .ledger import EpistemicLedger, LedgerEntry


@dataclass(frozen=True)
class ResearchCycle:
    cycle_id: str
    opportunities: tuple[ResearchOpportunity, ...]
    ledger_entries: tuple[LedgerEntry, ...]


class ResearchLoop:
    """Run one bounded reasoning cycle; execution is delegated to AEGIS."""

    def __init__(self, discovery: DiscoveryEngine, ledger: EpistemicLedger):
        self.discovery = discovery
        self.ledger = ledger
        self.planner = AutonomousResearchPlanner(ledger)
        self._counter = 0

    def cycle(self, *, executor: Callable[[ResearchOpportunity], Any] | None = None) -> ResearchCycle:
        self._counter += 1
        anomalies = self.discovery.anomalies()
        opportunities = self.planner.generate(anomalies)
        if executor is not None:
            # The callback is itself expected to invoke governed AEGIS capabilities.
            # The loop never executes a command or generated code directly.
            for opportunity in opportunities[:4]:
                outcome = executor(opportunity)
                if isinstance(outcome, dict) and isinstance(outcome.get("candidate"), object):
                    candidate = outcome.get("candidate")
                    if hasattr(candidate, "claim") and hasattr(candidate, "state"):
                        self.ledger.record(candidate, reason=f"research cycle {self._counter}")
        return ResearchCycle(f"cycle-{self._counter:08d}", opportunities, self.ledger.entries)
