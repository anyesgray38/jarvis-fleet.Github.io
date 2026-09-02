"""Bridge between planning and dispatch without coupling to fleet internals."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .planner import TaskPlan, PlanStep
from .task_graph import TaskGraphState, StepState


@dataclass
class PlanRunResult:
    plan_id: str
    passed: bool
    steps: dict[str, dict[str, Any]]


class PlanRunner:
    """Execute a validated plan through an injected dispatcher.

    The runner serializes dependent work and allows independent steps to be
    scheduled by a future concurrent executor without changing the contract.
    """

    def __init__(self, dispatcher: Callable[[dict[str, Any]], Any]):
        self.dispatcher = dispatcher

    def run(self, plan: TaskPlan, *, plan_id: str = "plan") -> PlanRunResult:
        plan.validate()
        state = TaskGraphState(plan_id=plan_id, steps={s.id: StepState(s.id) for s in plan.steps})
        by_id = {s.id: s for s in plan.steps}

        for step in plan.topological_order():
            if not state.ready(step.id, step.depends_on):
                state.steps[step.id].status = "skipped"
                state.steps[step.id].error = "dependency did not pass"
                continue
            state.mark_running(step.id)
            task = step.to_task(f"{plan_id}:{step.id}")
            result = self.dispatcher(task)
            status = getattr(result, "status", None) or result.get("status", "failed")
            payload = getattr(result, "result", None) or result.get("result") if isinstance(result, dict) else getattr(result, "result", None)
            error = getattr(result, "error", None) if not isinstance(result, dict) else result.get("error")
            state.mark_result(step.id, status, payload, error)

        return PlanRunResult(
            plan_id=plan_id,
            passed=state.passed,
            steps={k: vars(v).copy() for k, v in state.steps.items()},
        )
