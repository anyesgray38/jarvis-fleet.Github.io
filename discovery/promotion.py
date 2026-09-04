"""Conservative promotion rules from observations to knowledge."""
from __future__ import annotations

from .models import KnowledgeCandidate, KnowledgeState


def readiness(candidate: KnowledgeCandidate, *, min_confidence: float = 0.8, min_independence: int = 2) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if candidate.state is not KnowledgeState.VERIFIED:
        reasons.append(f"state={candidate.state.value}")
    if candidate.confidence < min_confidence:
        reasons.append("confidence_below_threshold")
    if len(candidate.independent_groups) < min_independence:
        reasons.append("insufficient_independence")
    if candidate.conflicts:
        reasons.append("conflicting_evidence")
    if not candidate.evidence_ids:
        reasons.append("missing_evidence")
    return not reasons, tuple(reasons)
