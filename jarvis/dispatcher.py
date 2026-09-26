"""Domain-agnostic AEGIS task and workflow lifecycle coordinator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .audit import audit_result
from .autonomy import ActivityFeed, AutonomyController, TaskStatus, TrustLevel
from .capabilities import CapabilityRegistry
from .workflow import WorkflowPlan, WorkflowRunResult, WorkflowRunner
from security.policy import Policy, PolicyDenied
from security.safety import SafetyController, SafetySettings, control_for_capability
from routing import SkillRouter


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
        safety: SafetySettings | None = None,
        router: SkillRouter | None = None,
    ):
        self.registry = registry
        self.policy = policy
        self.executor = executor
        self.checks = checks or {}
        self.evidence = evidence
        self.activity = ActivityFeed()
        self.autonomy = AutonomyController()
        self.safety = SafetyController(safety)
        self.router = router

    def dispatch(self, task: dict[str, Any], *, security: dict[str, Any] | None = None) -> DispatchResult:
        task_id = str(task.get("task_id", ""))
        if not task_id:
            return DispatchResult("", TaskStatus.REJECTED, error="task_id is required")
        required = TrustLevel(int(task.get("trust_required", TrustLevel.PREPARE)))
        if not self.autonomy.can_execute(required, external=required >= TrustLevel.EXECUTE_EXTERNAL):
            return DispatchResult(task_id, TaskStatus.REJECTED, error="trust level does not permit execution")
        self.activity.emit("task.received", task_id, capability=task.get("capability"))
        try:
            task = self._resolve_task(task)
            capability_id = str(task["capability"])
            control = task.get("safety_control") or control_for_capability(capability_id)
            self.safety.require(control) if control else None
            capability = self.registry.get(capability_id)
            self.policy.authorize(capability_id, security=security)
            self._record("task.authorized", task, {"capability": capability["id"], "safety_control": control})
            self.activity.emit("task.authorized", task_id, capability=capability["id"], safety_control=control)
            result = self.executor(task, capability)
            self._record("task.executed", task, {"result": result})
            self.activity.emit("task.executed", task_id)

            verification = task.get("verification", {})
            if verification.get("required", True):
                report = audit_result(task, result, self.checks)
                audit = report.to_dict()
                self._record("task.audited", task, {"audit": audit})
                if not report.passed:
                    self.activity.emit("task.rejected", task_id, reason="verification failed")
                    return DispatchResult(task_id, "rejected", result, audit, "verification failed")
            else:
                audit = None

            self._record("task.published", task, {"status": "passed"})
            self.activity.emit("task.passed", task_id)
            return DispatchResult(task_id, "passed", result, audit)
        except (KeyError, ValueError, PolicyDenied, PermissionError) as exc:
            self._record("task.rejected", task, {"error": str(exc)})
            return DispatchResult(task_id, "rejected", error=str(exc))
        except Exception as exc:
            self._record("task.failed", task, {"error": str(exc)})
            return DispatchResult(task_id, "failed", error=str(exc))

    def _resolve_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Resolve an objective only when the caller did not select a capability."""
        if task.get("capability"):
            return task
        objective = str(task.get("objective", "")).strip()
        if not objective:
            raise ValueError("capability or objective is required")
        if self.router is None:
            raise ValueError("capability is required; no skill router configured")
        routes = self.router.route(objective, limit=1)
        if not routes:
            raise ValueError("no registered capability matches objective")
        route = routes[0]
        resolved = dict(task)
        resolved["capability"] = route.capability_id
        resolved["route"] = {
            "skill": route.skill,
            "score": route.score,
            "matched_terms": list(route.matched_terms),
            "verification": list(route.verification),
            "requires_authorization": route.requires_authorization,
        }
        self._record("task.routed", resolved, {"route": resolved["route"], "capability": route.capability_id})
        self.activity.emit("task.routed", str(task.get("task_id", "")), capability=route.capability_id, skill=route.skill)
        return resolved

    def dispatch_workflow(
        self,
        plan: WorkflowPlan,
        *,
        security: dict[str, Any] | None = None,
    ) -> WorkflowRunResult:
        """Run every workflow step through the governed task dispatcher."""
        self._record("workflow.started", {"task_id": plan.workflow_id},
                     {"objective": plan.objective, "steps": len(plan.steps)})
        runner = WorkflowRunner(lambda task: self.dispatch(task, security=security), evidence=self.evidence)
        result = runner.run(plan)
        self._record("workflow.completed", {"task_id": plan.workflow_id},
                     {"status": result.status, "escalated": result.escalated})
        return result

    def _record(self, event: str, task: dict[str, Any], data: dict[str, Any]) -> None:
        if self.evidence is not None:
            self.evidence.append({"event": event, "task_id": task.get("task_id"), **data})
