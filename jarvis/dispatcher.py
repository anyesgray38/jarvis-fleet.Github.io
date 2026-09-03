"""Domain-agnostic AEGIS task and workflow lifecycle coordinator.

The dispatcher depends on protocols/callables rather than the fleet
implementation. This keeps cognition and policy separate from low-level
execution while giving workflows a governed path into the same lifecycle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .audit import audit_result
from .capabilities import CapabilityRegistry
from .workflow import WorkflowPlan, WorkflowRunResult, WorkflowRunner
from security.policy import Policy, PolicyDenied


class Executor(Protocol):
    def __call__(self, task: dict[str, Any], capability: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class DispatchResult:
    task_id: str
    status: str
    result: dict[str, Any] | None = None
    audit: dict[str, Any] | None = None
    error: str | None = None


class Dispatcher:
    def __init__(
        self,
        registry: CapabilityRegistry,
        policy: Policy,
        executor: Executor,
        *,
        checks: dict[str, Callable[[dict[str, Any], dict[str, Any]], tuple[bool, str]]] | None = None,
        evidence: Any | None = None,
    ):
        self.registry = registry
        self.policy = policy
        self.executor = executor
        self.checks = checks or {}
        self.evidence = evidence

    def dispatch(self, task: dict[str, Any], *, security: dict[str, Any] | None = None) -> DispatchResult:
        task_id = str(task.get("task_id", ""))
        try:
            capability = self.registry.get(str(task["capability"]))
            self.policy.authorize(str(task["capability"]), security=security)
            self._record("task.authorized", task, {"capability": capability["id"]})
            result = self.executor(task, capability)
            self._record("task.executed", task, {"result": result})

            verification = task.get("verification", {})
            if verification.get("required", True):
                report = audit_result(task, result, self.checks)
                audit = report.to_dict()
                self._record("task.audited", task, {"audit": audit})
                if not report.passed:
                    return DispatchResult(task_id, "rejected", result, audit, "verification failed")
            else:
                audit = None

            self._record("task.published", task, {"status": "passed"})
            return DispatchResult(task_id, "passed", result, audit)
        except (KeyError, ValueError, PolicyDenied) as exc:
            self._record("task.rejected", task, {"error": str(exc)})
            return DispatchResult(task_id, "rejected", error=str(exc))
        except Exception as exc:
            self._record("task.failed", task, {"error": str(exc)})
            return DispatchResult(task_id, "failed", error=str(exc))

    def dispatch_workflow(
        self,
        plan: WorkflowPlan,
        *,
        security: dict[str, Any] | None = None,
    ) -> WorkflowRunResult:
        """Run every workflow step through the governed task dispatcher."""
        self._record(
            "workflow.started",
            {"task_id": plan.workflow_id},
            {"objective": plan.objective, "steps": len(plan.steps)},
        )
        runner = WorkflowRunner(
            lambda task: self.dispatch(task, security=security),
            evidence=self.evidence,
        )
        result = runner.run(plan)
        self._record(
            "workflow.completed",
            {"task_id": plan.workflow_id},
            {"status": result.status, "escalated": result.escalated},
        )
        return result

    def _record(self, event: str, task: dict[str, Any], data: dict[str, Any]) -> None:
        if self.evidence is not None:
            self.evidence.append({"event": event, "task_id": task.get("task_id"), **data})
