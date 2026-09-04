"""Bounded autonomous research agenda generation.

Agents may pursue low-risk scientific work without a human selecting every next
question. The agenda only creates governed work; execution still requires the
AEGIS dispatcher, capability registry, policy, verification, and evidence path.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .ledger import EpistemicLedger
from .models import Anomaly, KnowledgeState


class ResearchTrack(str, Enum):
    REPRODUCTION = "reproduction"
    CONTRADICTION = "contradiction"
    ANOMALY = "anomaly"
    PARAMETER_SEARCH = "parameter_search"
    MODEL_COMPARISON = "model_comparison"
    CODE_SYNTHESIS = "code_synthesis"
    ALGORITHM_DISCOVERY = "algorithm_discovery"
    DATA_QUALITY = "data_quality"


@dataclass(frozen=True)
class ResearchOpportunity:
    opportunity_id: str
    track: ResearchTrack
    objective: str
    priority: float
    prerequisites: tuple[str, ...] = ()
    safety_class: str = "bounded"


class AutonomousResearchPlanner:
    """Turn epistemic uncertainty into bounded, auditable research opportunities."""

    def __init__(self, ledger: EpistemicLedger):
        self.ledger = ledger

    def generate(self, anomalies: Iterable[Anomaly] = ()) -> tuple[ResearchOpportunity, ...]:
        opportunities: list[ResearchOpportunity] = []
        for anomaly in anomalies:
            track = {
                "contradiction": ResearchTrack.CONTRADICTION,
                "reproduction_mismatch": ResearchTrack.REPRODUCTION,
                "expectation_mismatch": ResearchTrack.ANOMALY,
                "outlier": ResearchTrack.ANOMALY,
                "distribution_shift": ResearchTrack.DATA_QUALITY,
                "undeclared_dependency": ResearchTrack.DATA_QUALITY,
            }[anomaly.kind.value]
            opportunities.append(
                ResearchOpportunity(
                    opportunity_id=f"research-{anomaly.anomaly_id}",
                    track=track,
                    objective=f"Investigate anomaly: {anomaly.description}",
                    priority=1.0 if anomaly.severity.lower() in {"high", "critical"} else 0.7,
                    prerequisites=anomaly.evidence_ids,
                )
            )
        for entry in self.ledger.entries[-20:]:
            if entry.state in {KnowledgeState.HYPOTHESIS, KnowledgeState.TESTABLE, KnowledgeState.OBSERVED}:
                opportunities.append(
                    ResearchOpportunity(
                        opportunity_id=f"followup-{entry.entry_id}",
                        track=ResearchTrack.REPRODUCTION,
                        objective=f"Independently reproduce or falsify: {entry.claim}",
                        priority=0.8,
                        prerequisites=entry.evidence_ids,
                    )
                )
        return tuple(opportunities)
