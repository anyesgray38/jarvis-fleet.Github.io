"""Bounded autonomous research scheduler."""
from __future__ import annotations
from dataclasses import dataclass
from .agenda import AgendaBuilder, Agenda
from .autonomy import AutonomousResearchPlanner
from .ledger import EpistemicLedger
from .engine import DiscoveryEngine


@dataclass
class ResearchScheduler:
    discovery: DiscoveryEngine
    ledger: EpistemicLedger
    max_concurrent: int = 4

    def next_agenda(self) -> Agenda:
        opportunities = AutonomousResearchPlanner(self.ledger).generate(self.discovery.anomalies())
        return AgendaBuilder(self.max_concurrent).build(opportunities)
