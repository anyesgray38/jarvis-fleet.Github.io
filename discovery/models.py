"""Contracts for governed scientific discovery."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class KnowledgeState(str, Enum):
    IDEA = "idea"
    HYPOTHESIS = "hypothesis"
    TESTABLE = "testable"
    OBSERVED = "observed"
    REPRODUCED = "reproduced"
    VERIFIED = "verified"
    REJECTED = "rejected"
    CONFLICTED = "conflicted"


class AnomalyKind(str, Enum):
    EXPECTATION_MISMATCH = "expectation_mismatch"
    REPRODUCTION_MISMATCH = "reproduction_mismatch"
    DISTRIBUTION_SHIFT = "distribution_shift"
    OUTLIER = "outlier"
    CONTRADICTION = "contradiction"
    UNDECLARED_DEPENDENCY = "undeclared_dependency"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source: str
    claim: str
    observed_at: str = field(default_factory=_now)
    independent_group: str = "default"
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    statement: str
    null_hypothesis: str
    variables: tuple[str, ...] = ()
    falsification_criteria: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()
    state: KnowledgeState = KnowledgeState.TESTABLE
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    hypothesis_id: str
    objective: str
    procedure: tuple[str, ...]
    controls: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    independent_group: str = "primary"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentResult:
    experiment_id: str
    success: bool
    observations: dict[str, float | int | str | bool]
    evidence: tuple[Evidence, ...] = ()
    conclusion: str = ""
    reproducible: bool = False
    verified: bool = False


@dataclass(frozen=True)
class ReproductionPlan:
    source_experiment_id: str
    independent_group: str
    changed_factors: tuple[str, ...]
    minimum_repetitions: int = 2


@dataclass(frozen=True)
class Anomaly:
    anomaly_id: str
    kind: AnomalyKind
    description: str
    severity: str
    related_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    discovered_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class KnowledgeCandidate:
    claim: str
    state: KnowledgeState
    evidence_ids: tuple[str, ...]
    independent_groups: tuple[str, ...]
    confidence: float
    conflicts: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"
