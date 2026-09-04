"""Construct reproducible experiments from research opportunities."""
from __future__ import annotations
from dataclasses import dataclass
from .autonomy import ResearchOpportunity, ResearchTrack
from .models import Experiment, new_id


@dataclass(frozen=True)
class ExperimentTemplate:
    controls: tuple[str, ...]
    metrics: tuple[str, ...]
    falsification_criteria: tuple[str, ...]


class ExperimentFactory:
    """Create explicit, bounded experiments; never executes them."""

    def build(self, opportunity: ResearchOpportunity, *, hypothesis_id: str, procedure: tuple[str, ...], template: ExperimentTemplate) -> Experiment:
        if not hypothesis_id.strip() or not procedure:
            raise ValueError("hypothesis_id and procedure are required")
        if not template.metrics or not template.falsification_criteria:
            raise ValueError("metrics and falsification criteria are required")
        return Experiment(
            experiment_id=new_id("exp"),
            hypothesis_id=hypothesis_id,
            objective=opportunity.objective,
            procedure=procedure,
            controls=template.controls,
            metrics=template.metrics,
            required_evidence=("raw_observations", "provenance", "verification"),
            metadata={"research_track": opportunity.track.value, "priority": opportunity.priority},
        )
