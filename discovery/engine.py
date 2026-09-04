"""Governed discovery lifecycle: hypothesis -> experiment -> falsification -> knowledge."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from .anomaly import detect_contradictions, detect_expectation_mismatch, detect_numeric_outliers
from .models import (
    Anomaly, Evidence, Experiment, ExperimentResult, Hypothesis, KnowledgeCandidate,
    KnowledgeState, ReproductionPlan,
)


@dataclass
class DiscoveryEngine:
    """Coordinate scientific reasoning without granting arbitrary execution authority.

    Executors are injected governed capabilities. The discovery layer may design work,
    analyze returned observations, and decide whether a claim is ready for promotion;
    it does not execute generated code or grant tools by itself.
    """
    hypotheses: dict[str, Hypothesis] = field(default_factory=dict)
    experiments: dict[str, Experiment] = field(default_factory=dict)
    results: dict[str, list[ExperimentResult]] = field(default_factory=dict)
    evidence: dict[str, Evidence] = field(default_factory=dict)

    def register_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        if hypothesis.hypothesis_id in self.hypotheses:
            raise ValueError(f"duplicate hypothesis: {hypothesis.hypothesis_id}")
        if not hypothesis.statement.strip() or not hypothesis.null_hypothesis.strip():
            raise ValueError("hypothesis and null hypothesis are required")
        if not hypothesis.falsification_criteria:
            raise ValueError("falsification criteria are required")
        self.hypotheses[hypothesis.hypothesis_id] = hypothesis
        return hypothesis

    def design_experiment(self, experiment: Experiment) -> Experiment:
        if experiment.hypothesis_id not in self.hypotheses:
            raise ValueError("experiment references unknown hypothesis")
        if not experiment.procedure or not experiment.metrics:
            raise ValueError("experiment requires procedure and metrics")
        if experiment.experiment_id in self.experiments:
            raise ValueError(f"duplicate experiment: {experiment.experiment_id}")
        self.experiments[experiment.experiment_id] = experiment
        return experiment

    def record_result(self, result: ExperimentResult) -> ExperimentResult:
        if result.experiment_id not in self.experiments:
            raise ValueError("result references unknown experiment")
        self.results.setdefault(result.experiment_id, []).append(result)
        for item in result.evidence:
            self.evidence[item.evidence_id] = item
        return result

    def reproduction_plan(self, experiment_id: str, *, independent_group: str, changed_factors: Iterable[str] = ()) -> ReproductionPlan:
        experiment = self.experiments[experiment_id]
        return ReproductionPlan(
            source_experiment_id=experiment.experiment_id,
            independent_group=independent_group,
            changed_factors=tuple(changed_factors),
        )

    def anomalies(self, *, expected: dict[str, float] | None = None, observed: dict[str, float] | None = None, tolerance: float = 0.0) -> tuple[Anomaly, ...]:
        found = list(detect_numeric_outliers(observed or {}))
        if expected and observed:
            for key, value in observed.items():
                if key in expected:
                    anomaly = detect_expectation_mismatch(expected[key], value, tolerance, related_id=key)
                    if anomaly:
                        found.append(anomaly)
        found.extend(detect_contradictions(self.evidence.values()))
        return tuple(found)

    def assess_claim(self, hypothesis_id: str, *, minimum_independent_groups: int = 2) -> KnowledgeCandidate:
        hypothesis = self.hypotheses[hypothesis_id]
        results = [r for rs in self.results.values() for r in rs if self.experiments[r.experiment_id].hypothesis_id == hypothesis_id]
        evidence_ids = tuple(e.evidence_id for r in results for e in r.evidence)
        groups = tuple(sorted({e.independent_group for r in results for e in r.evidence}))
        conflicts = tuple(a.anomaly_id for a in self.anomalies() if a.kind.value == "contradiction")
        successful = [r for r in results if r.success]
        reproduced = any(r.reproducible for r in successful)
        verified = any(r.verified for r in successful)
        if conflicts:
            state = KnowledgeState.CONFLICTED
        elif verified and len(groups) >= minimum_independent_groups:
            state = KnowledgeState.VERIFIED
        elif reproduced:
            state = KnowledgeState.REPRODUCED
        elif successful:
            state = KnowledgeState.OBSERVED
        else:
            state = KnowledgeState.HYPOTHESIS
        confidence = 0.0
        if results:
            confidence = min(0.99, (len(successful) / len(results)) * min(1.0, len(groups) / max(1, minimum_independent_groups)))
        return KnowledgeCandidate(hypothesis.statement, state, evidence_ids, groups, confidence, conflicts, hypothesis.prerequisites)

    def run_analysis(self, hypothesis_id: str, analyzer: Callable[[tuple[ExperimentResult, ...]], str]) -> str:
        """Run a pure analyzer over recorded results; execution remains external."""
        results = tuple(r for rs in self.results.values() for r in rs if self.experiments[r.experiment_id].hypothesis_id == hypothesis_id)
        return analyzer(results)
