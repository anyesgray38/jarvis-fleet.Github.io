"""AEGIS scientific discovery primitives.

The discovery layer generates and evaluates hypotheses, experiments, anomalies,
reproduction plans, and knowledge-promotion decisions. It does not execute
arbitrary generated code; execution remains a governed AEGIS capability.
"""

from .engine import DiscoveryEngine
from .models import (
    Anomaly,
    Evidence,
    Experiment,
    ExperimentResult,
    Hypothesis,
    KnowledgeCandidate,
    ReproductionPlan,
)
from .stats import mean, permutation_p_value, summarize_samples

__all__ = [
    "Anomaly",
    "DiscoveryEngine",
    "Evidence",
    "Experiment",
    "ExperimentResult",
    "Hypothesis",
    "KnowledgeCandidate",
    "ReproductionPlan",
    "mean",
    "permutation_p_value",
    "summarize_samples",
]
