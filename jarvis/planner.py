"""Domain-agnostic task graph planner for Jarvis.

The planner does not execute work. It turns an objective into a validated,
ordered graph that the dispatcher can execute later. Dependencies are explicit
and cycles are rejected.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlanStep:
    id: str
    capability: str
    input: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    verification: dict[str, Any] = field(default_factory=lambda: {"required": True})
    constraints: dict[str, Any] = field(default_factory=dict)

    def to_task(self, task_id: str) -> dict[str, Any]:
        return {
            "task_id": task_id,
            "capability": self.capability,
            "input": self.input,
            "constraints": self.constraints,
            "verification": self.verification,
        }


@dataclass
class TaskPlan:
    objective: str
    steps: list[PlanStep]
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate plan step id")
        known = set(ids)
        for step in self.steps:
            missing = set(step.depends_on) - known
            if missing:
                raise ValueError(f"unknown dependencies for {step.id}: {sorted(missing)}")
        self.topological_order()

    def topological_order(self) -> list[PlanStep]:
        self.validate_without_order()
        by_id = {step.id: step for step in self.steps}
        remaining = {step.id: set(step.depends_on) for step in self.steps}
        ordered: list[PlanStep] = []
        while remaining:
            ready = sorted(step_id for step_id, deps in remaining.items() if not deps)
            if not ready:
                raise ValueError("plan contains a dependency cycle")
            for step_id in ready:
                ordered.append(by_id[step_id])
                del remaining[step_id]
            for deps in remaining.values():
                deps.difference_update(ready)
        return ordered

    def validate_without_order(self) -> None:
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate plan step id")
        known = set(ids)
        for step in self.steps:
            missing = set(step.depends_on) - known
            if missing:
                raise ValueError(f"unknown dependencies for {step.id}: {sorted(missing)}")


class Planner:
    """Build plans from an explicit step specification.

    LLM-based planning can sit above this class; this layer remains deterministic
    and is responsible for validating the resulting graph before execution.
    """

    def build(self, objective: str, steps: list[dict[str, Any]], *, metadata: dict[str, Any] | None = None) -> TaskPlan:
        if not objective.strip():
            raise ValueError("objective must not be empty")
        plan_steps = [
            PlanStep(
                id=str(item["id"]),
                capability=str(item["capability"]),
                input=dict(item.get("input", {})),
                depends_on=tuple(item.get("depends_on", ())),
                verification=dict(item.get("verification", {"required": True})),
                constraints=dict(item.get("constraints", {})),
            )
            for item in steps
        ]
        plan = TaskPlan(objective=objective, steps=plan_steps, metadata=metadata or {})
        plan.validate()
        return plan
