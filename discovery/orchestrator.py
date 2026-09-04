"""Bridge scientific discovery plans into AEGIS governed execution.

Discovery owns hypotheses, experiment design, analysis, and epistemic state. The
control plane owns authorization, execution, verification, and evidence. This
module is the narrow boundary between the two.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jarvis.dispatcher import DispatchResult, Dispatcher

from .engine import DiscoveryEngine
from .models import Evidence, Experiment, ExperimentResult


@dataclass(frozen=True)
class ExperimentDispatch:
    """The governed execution outcome plus the normalized discovery result."""

    dispatch: DispatchResult
    result: ExperimentResult | None


class DiscoveryOrchestrator:
    """Turn an approved experiment into a normal AEGIS task.

    The experiment executor is selected by the capability supplied by the caller;
    this class never executes arbitrary generated code directly. All execution
    therefore passes through the normal registry, policy, audit, and evidence path.
    """

    def __init__(self, discovery: DiscoveryEngine, dispatcher: Dispatcher):
        self.discovery = discovery
        self.dispatcher = dispatcher

    def execute_experiment(
        self,
        experiment: Experiment,
        *,
        execution_capability: str,
        security: dict[str, Any] | None = None,
    ) -> ExperimentDispatch:
        if experiment.experiment_id not in self.discovery.experiments:
            raise ValueError("experiment must be registered before execution")
        if not execution_capability.strip():
            raise ValueError("execution capability is required")

        task = {
            "task_id": f"experiment:{experiment.experiment_id}",
            "capability": execution_capability,
            "input": {
                "experiment_id": experiment.experiment_id,
                "hypothesis_id": experiment.hypothesis_id,
                "objective": experiment.objective,
                "procedure": list(experiment.procedure),
                "controls": list(experiment.controls),
                "metrics": list(experiment.metrics),
                "required_evidence": list(experiment.required_evidence),
                "metadata": dict(experiment.metadata),
            },
            "verification": {"required": True, "independent": True},
        }
        dispatch = self.dispatcher.dispatch(task, security=security)
        if dispatch.status != "passed" or dispatch.result is None:
            return ExperimentDispatch(dispatch, None)

        result = self._normalize_result(experiment, dispatch.result)
        self.discovery.record_result(result)
        return ExperimentDispatch(dispatch, result)

    @staticmethod
    def _normalize_result(experiment: Experiment, payload: dict[str, Any]) -> ExperimentResult:
        observations = payload.get("observations", {})
        if not isinstance(observations, dict):
            raise ValueError("experiment execution must return an observations object")

        evidence_items: list[Evidence] = []
        raw_evidence = payload.get("evidence", [])
        if not isinstance(raw_evidence, list):
            raise ValueError("experiment execution evidence must be a list")
        for item in raw_evidence:
            if not isinstance(item, dict):
                raise ValueError("each evidence item must be an object")
            required = {"evidence_id", "source", "claim"}
            if not required.issubset(item):
                raise ValueError("evidence requires evidence_id, source, and claim")
            evidence_items.append(
                Evidence(
                    evidence_id=str(item["evidence_id"]),
                    source=str(item["source"]),
                    claim=str(item["claim"]),
                    independent_group=str(item.get("independent_group", experiment.independent_group)),
                    data=dict(item.get("data", {})),
                )
            )

        return ExperimentResult(
            experiment_id=experiment.experiment_id,
            success=bool(payload.get("success", False)),
            observations=observations,
            evidence=tuple(evidence_items),
            conclusion=str(payload.get("conclusion", "")),
            reproducible=bool(payload.get("reproducible", False)),
            verified=bool(payload.get("verified", False)),
        )
