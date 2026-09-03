"""Governed workflow execution for AEGIS.

A workflow is a validated DAG of capability steps with bounded retries,
conditional execution, output references, and explicit failure handling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


TERMINAL = {"passed", "failed", "rejected", "skipped", "escalated"}


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    capability: str
    input: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    condition: str | None = None
    max_attempts: int = 1
    on_failure: str = "stop"
    verification: dict[str, Any] = field(default_factory=lambda: {"required": True})
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowPlan:
    workflow_id: str
    objective: str
    steps: list[WorkflowStep]
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.workflow_id.strip() or not self.objective.strip():
            raise ValueError("workflow_id and objective are required")
        ids = [s.id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate workflow step id")
        known = set(ids)
        for step in self.steps:
            if not step.id or not step.capability:
                raise ValueError("workflow steps require id and capability")
            if step.max_attempts < 1:
                raise ValueError(f"max_attempts must be >= 1: {step.id}")
            if step.on_failure not in {"stop", "continue", "escalate"}:
                raise ValueError(f"invalid on_failure policy: {step.id}")
            missing = set(step.depends_on) - known
            if missing:
                raise ValueError(f"unknown dependencies for {step.id}: {sorted(missing)}")
        self.topological_order()

    def topological_order(self) -> list[WorkflowStep]:
        ids = [s.id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate workflow step id")
        by_id = {s.id: s for s in self.steps}
        remaining = {s.id: set(s.depends_on) for s in self.steps}
        ordered: list[WorkflowStep] = []
        while remaining:
            ready = sorted(k for k, deps in remaining.items() if not deps)
            if not ready:
                raise ValueError("workflow contains a dependency cycle")
            for key in ready:
                ordered.append(by_id[key])
                del remaining[key]
            for deps in remaining.values():
                deps.difference_update(ready)
        return ordered

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowPlan":
        steps = []
        for item in data.get("steps", []):
            steps.append(WorkflowStep(
                id=str(item["id"]),
                capability=str(item["capability"]),
                input=dict(item.get("input", {})),
                depends_on=tuple(item.get("depends_on", ())),
                condition=item.get("condition"),
                max_attempts=int(item.get("max_attempts", 1)),
                on_failure=str(item.get("on_failure", "stop")),
                verification=dict(item.get("verification", {"required": True})),
                constraints=dict(item.get("constraints", {})),
            ))
        plan = cls(str(data.get("workflow_id", "")), str(data.get("objective", "")), steps, dict(data.get("metadata", {})))
        plan.validate()
        return plan


@dataclass
class WorkflowStepState:
    step_id: str
    status: str = "pending"
    attempts: int = 0
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class WorkflowRunResult:
    workflow_id: str
    status: str
    steps: dict[str, WorkflowStepState]
    escalated: bool = False


class WorkflowRunner:
    """Execute workflows through an injected dispatcher."""

    def __init__(self, dispatcher: Callable[[dict[str, Any]], Any], *, evidence: Any | None = None):
        self.dispatcher = dispatcher
        self.evidence = evidence

    @staticmethod
    def _resolve(value: Any, outputs: dict[str, dict[str, Any]]) -> Any:
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            path = value[2:-1].split(".")
            if len(path) < 2 or path[0] not in outputs:
                raise ValueError(f"unresolved workflow reference: {value}")
            current: Any = outputs[path[0]]
            for key in path[1:]:
                if not isinstance(current, dict) or key not in current:
                    raise ValueError(f"unresolved workflow reference: {value}")
                current = current[key]
            return current
        if isinstance(value, dict):
            return {k: WorkflowRunner._resolve(v, outputs) for k, v in value.items()}
        if isinstance(value, list):
            return [WorkflowRunner._resolve(v, outputs) for v in value]
        return value

    def run(self, plan: WorkflowPlan) -> WorkflowRunResult:
        plan.validate()
        states = {s.id: WorkflowStepState(s.id) for s in plan.steps}
        outputs: dict[str, dict[str, Any]] = {}
        escalated = False
        halted = False

        for step in plan.topological_order():
            state = states[step.id]
            if halted or not all(states[d].status == "passed" for d in step.depends_on):
                state.status = "skipped"
                state.error = "dependency did not pass"
                continue
            if step.condition is not None:
                if not self._condition(step.condition, outputs):
                    state.status = "skipped"
                    state.error = "condition evaluated false"
                    continue
            task_input = self._resolve(step.input, outputs)
            task = {
                "task_id": f"{plan.workflow_id}:{step.id}",
                "capability": step.capability,
                "input": task_input,
                "constraints": step.constraints,
                "verification": step.verification,
            }
            success = False
            last_error = None
            for _ in range(step.max_attempts):
                state.status = "running"
                state.attempts += 1
                try:
                    result = self.dispatcher(task)
                    status = getattr(result, "status", None) or (result.get("status", "failed") if isinstance(result, dict) else "failed")
                    payload = getattr(result, "result", None) if not isinstance(result, dict) else result.get("result")
                    error = getattr(result, "error", None) if not isinstance(result, dict) else result.get("error")
                    if status == "passed":
                        state.status, state.result = "passed", payload or {}
                        outputs[step.id] = state.result
                        success = True
                        break
                    last_error = error or f"dispatcher status: {status}"
                except Exception as exc:
                    last_error = str(exc)
            if not success:
                state.status = "escalated" if step.on_failure == "escalate" else "failed"
                state.error = last_error
                if step.on_failure == "escalate":
                    escalated = True
                if step.on_failure == "stop":
                    halted = True
            self._record(plan, step, state)

        if escalated:
            status = "escalated"
        elif all(s.status == "passed" for s in states.values()):
            status = "passed"
        elif any(s.status == "failed" for s in states.values()):
            status = "failed"
        else:
            status = "rejected"
        return WorkflowRunResult(plan.workflow_id, status, states, escalated)

    @staticmethod
    def _condition(expression: str, outputs: dict[str, dict[str, Any]]) -> bool:
        if expression.startswith("${") and expression.endswith("}"):
            value = WorkflowRunner._resolve(expression, outputs)
            return bool(value)
        raise ValueError("workflow conditions must use output references")

    def _record(self, plan: WorkflowPlan, step: WorkflowStep, state: WorkflowStepState) -> None:
        if self.evidence is not None:
            self.evidence.append({"event": "workflow.step", "workflow_id": plan.workflow_id, "step_id": step.id, "status": state.status, "attempts": state.attempts})
