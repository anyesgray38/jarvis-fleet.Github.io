"""Execution state for a Jarvis task graph."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


TERMINAL = {"passed", "rejected", "failed", "skipped"}


@dataclass
class StepState:
    step_id: str
    status: str = "pending"
    attempts: int = 0
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class TaskGraphState:
    plan_id: str
    steps: dict[str, StepState] = field(default_factory=dict)

    def ready(self, step_id: str, dependencies: tuple[str, ...]) -> bool:
        if self.steps[step_id].status != "pending":
            return False
        return all(self.steps[dep].status == "passed" for dep in dependencies)

    def mark_running(self, step_id: str) -> None:
        state = self.steps[step_id]
        if state.status != "pending":
            raise ValueError(f"step is not pending: {step_id}")
        state.status = "running"
        state.attempts += 1

    def mark_result(self, step_id: str, status: str, result: dict[str, Any] | None = None, error: str | None = None) -> None:
        if status not in TERMINAL:
            raise ValueError(f"invalid terminal status: {status}")
        state = self.steps[step_id]
        if state.status != "running":
            raise ValueError(f"step is not running: {step_id}")
        state.status = status
        state.result = result
        state.error = error

    @property
    def complete(self) -> bool:
        return bool(self.steps) and all(state.status in TERMINAL for state in self.steps.values())

    @property
    def passed(self) -> bool:
        return self.complete and all(state.status == "passed" for state in self.steps.values())
