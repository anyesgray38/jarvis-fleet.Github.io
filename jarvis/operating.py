"""Domain-independent operating loop over the existing governed dispatcher."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import time
from threading import RLock
from uuid import uuid4

from .autonomy import FailureDoctor, MemoryStore, TrustLevel
from .dispatcher import DispatchResult, Dispatcher
from .evaluation import ARTIFACT_KINDS, EvaluationEngine, KnowledgeLedger, Metric, cicd_selection
from .procedures import ACTIVITIES, SOPRegistry
from .verification import evidence_digest
from .workflow import WorkflowPlan, WorkflowRunner, WorkflowStep
from routing import SkillRouter

ROOT = Path(__file__).resolve().parents[1]


def snapshot(value):
    return json.loads(json.dumps(value, allow_nan=False))


def task_contract(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("task must be an object")
    allowed = {"task_id", "objective", "capability", "input", "activity", "artifact_kind",
               "constraints", "environment", "criteria", "max_attempts", "max_calls", "timeout_seconds"}
    if set(raw) - allowed:
        raise ValueError(f"unknown task fields: {sorted(set(raw) - allowed)}")
    task = {"capability": "", "input": {}, "activity": "unknown", "artifact_kind": None,
            "constraints": [], "environment": {}, "max_attempts": 1, "max_calls": 3,
            "timeout_seconds": 60, **snapshot(raw)}
    for key in ("task_id", "objective"):
        if not isinstance(task.get(key), str) or not task[key].strip():
            raise ValueError(f"{key} is required")
    if not isinstance(task["capability"], str) or not isinstance(task["input"], dict) or not isinstance(task["environment"], dict):
        raise ValueError("invalid capability, input or environment")
    if task["activity"] not in ACTIVITIES or task["artifact_kind"] not in ARTIFACT_KINDS | {None}:
        raise ValueError("invalid activity or artifact_kind")
    if not isinstance(task["constraints"], list) or not all(isinstance(c, str) and c.strip() for c in task["constraints"]):
        raise ValueError("constraints must be nonempty strings")
    for key in ("max_attempts", "max_calls", "timeout_seconds"):
        if type(task[key]) is not int or task[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    criteria = task.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("measurable success criteria are required")
    names = set()
    for item in criteria:
        if not isinstance(item, dict) or set(item) != {"name", "field", "operator", "expected"}:
            raise ValueError("invalid criterion fields")
        if not all(isinstance(item[k], str) for k in ("name", "field", "operator")):
            raise ValueError("criterion names, fields and operators must be strings")
        Metric(**item).validate()
        if item["name"] in names:
            raise ValueError("duplicate criterion name")
        names.add(item["name"])
    if len(json.dumps(task)) > 100_000:
        raise ValueError("task exceeds the 100 KB contract limit")
    return task


class ApprovalLedger:
    """Trusted operator API, not a task/model-facing tool or identity service."""
    def __init__(self, *, clock=time.monotonic):
        self.clock, self._grants, self._lock = clock, {}, RLock()

    def grant(self, fingerprint: str, *, actor: str, ttl_seconds: int = 300) -> str:
        if not actor.strip() or not fingerprint or not 1 <= ttl_seconds <= 3600:
            raise ValueError("approval requires an actor, plan fingerprint and bounded expiry")
        token = uuid4().hex
        with self._lock:
            self._grants[token] = (fingerprint, actor, self.clock() + ttl_seconds)
        return token

    def consume(self, token: str | None, fingerprint: str) -> str:
        with self._lock:
            grant = self._grants.get(token)
            if not grant or grant[0] != fingerprint or self.clock() >= grant[2]:
                raise PermissionError("missing, expired, used or mismatched plan approval")
            del self._grants[token]
            return grant[1]


class SafeEvents:
    """Reuse EvidenceStore while hashing tool payloads instead of logging secrets."""
    def __init__(self, store):
        self.store = store

    def append(self, event):
        record = deepcopy(event)
        for key in ("result", "input", "error"):
            if key in record:
                record[f"{key}_digest"] = evidence_digest({key: record.pop(key)})
        return self.store.append(record)


class OperatingEngine:
    def __init__(self, dispatcher: Dispatcher, *, allowed_capabilities: frozenset[str],
                 evidence, sops: SOPRegistry | None = None, policy: dict | None = None,
                 approvals: ApprovalLedger | None = None, memory: MemoryStore | None = None,
                 clock=time.monotonic):
        self.dispatcher = dispatcher
        self.allowed = frozenset(allowed_capabilities)
        self.events = SafeEvents(evidence)
        self.sops = sops or SOPRegistry.from_file(ROOT / "config/sops.json")
        self.policy = snapshot(policy if policy is not None else json.loads((ROOT / "config/operating_policy.json").read_text()))
        self._validate_policy()
        self.approvals = approvals or ApprovalLedger(clock=clock)
        self.clock = clock
        self.evaluator = EvaluationEngine()
        self.knowledge = KnowledgeLedger(memory or MemoryStore(), self.evaluator)
        self._runs, self._lock = set(), RLock()

    def _validate_policy(self):
        if self.policy.get("version") != 1 or not isinstance(self.policy.get("capabilities"), dict):
            raise ValueError("invalid operating policy")
        for field in ("max_attempts", "max_calls", "max_seconds"):
            if type(self.policy.get(field)) is not int or self.policy[field] < 1:
                raise ValueError("invalid policy resource bounds")
        for rule in self.policy["capabilities"].values():
            if rule.get("effect") not in {"read", "write", "external", "privileged"}:
                raise ValueError("invalid capability effect")
            if type(rule.get("trust")) is not int or rule["trust"] not in set(TrustLevel):
                raise ValueError("invalid capability trust")
            if type(rule.get("idempotent")) is not bool or not isinstance(rule.get("controls"), list):
                raise ValueError("invalid capability retry/control policy")
            if any(c not in self.dispatcher.safety.settings.controls for c in rule["controls"]):
                raise ValueError("unknown safety control in operating policy")
            if not isinstance(rule.get("action"), str) or not rule["action"]:
                raise ValueError("trusted capability action identity is required")
            if rule.get("artifact_kind") not in ARTIFACT_KINDS | {None}:
                raise ValueError("invalid capability artifact kind")

    def plan(self, raw: dict) -> dict:
        task = task_contract(raw)
        blockers = []
        capability_id = task["capability"]
        route_reason = "Explicit capability selected; permissions are checked separately."
        if not capability_id:
            routes = SkillRouter(self.dispatcher.registry.path).route(task["objective"])
            if routes and (len(routes) == 1 or routes[0].score > routes[1].score):
                capability_id = routes[0].capability_id
                route_reason = f"Matched registered capability terms: {', '.join(routes[0].matched_terms)}."
            else:
                blockers.append("No unambiguous capability match; clarify the objective or select a capability.")
        try:
            capability = self.dispatcher.registry.get(capability_id)
        except ValueError:
            capability = {"id": capability_id or "unresolved"}
            blockers.append("The capability is not registered.")
        rule = self.policy["capabilities"].get(capability_id)
        if rule is None:
            blockers.append("No trusted effect/permission contract for this capability.")
        elif rule["action"] != capability.get("action", capability_id):
            blockers.append("Capability action differs from its trusted permission contract.")
        if capability_id not in self.allowed:
            blockers.append("Capability is outside the operator's execution allowlist.")
        for field, limit in (("max_attempts", "max_attempts"), ("max_calls", "max_calls"), ("timeout_seconds", "max_seconds")):
            if task[field] > self.policy[limit]:
                blockers.append(f"{field} exceeds the operating policy limit.")
        if task["max_attempts"] > task["max_calls"]:
            blockers.append("Retry budget exceeds the call budget.")
        if rule and task["max_attempts"] > 1 and not rule["idempotent"]:
            blockers.append("Retries require a trusted idempotent capability.")
        artifact = task["artifact_kind"] or (rule or {}).get("artifact_kind")
        activity = "change" if artifact else task["activity"]
        if activity == "unknown" and rule:
            activity = "inspect" if rule["effect"] == "read" else "operate"
        procedure, sop_reason = self.sops.select(activity, capability["id"])
        cicd = cicd_selection(artifact)
        checks = sorted(set(capability.get("verification", ())) | set(cicd["checks"]))
        if not checks:
            blockers.append("No independent capability checks are registered.")
        missing = sorted(set(checks) - self.dispatcher.checks.keys())
        if missing:
            blockers.append(f"Required evaluation adapters are unavailable: {', '.join(missing)}.")
        review = procedure.status != "reviewed" or bool(task["constraints"]) or (rule or {}).get("effect") != "read"
        data = {"task": task, "capability": capability["id"], "activity": activity,
                "route_reason": route_reason, "classification_reason": "Activity follows explicit intent, artifact changes and trusted capability effects, not domain names.",
                "sop": procedure.to_dict(), "sop_reason": sop_reason, "cicd": cicd,
                "evaluation": {"checks": checks, "criteria": task["criteria"], "reason": "Combine independent capability checks with the task's measurable success criteria."},
                "governance": {"rule": rule, "approval_required": review,
                               "reason": "Allowlist, existing policy/safety and trust always apply; provisional procedures, effects and textual constraints additionally require review.",
                               "policy_digest": evidence_digest({"operating": self.policy, "admission": self.dispatcher.policy.data, "capability": capability})},
                "blockers": blockers}
        data = snapshot(data)
        return {**data, "fingerprint": evidence_digest(data)}

    def _event(self, event, task_id, **data):
        record = {"event": event, "task_id": task_id, "event_id": uuid4().hex, **data}
        self.events.append(record)
        return record["event_id"]

    def run(self, plan: dict, *, approval: str | None = None, security: dict | None = None) -> dict:
        # Re-plan from the task contract: edited plans, stale policies or SOPs cannot reuse approval.
        plan = snapshot(plan)
        task_id = plan["task"]["task_id"]
        fresh = self.plan(plan["task"])
        if plan != fresh or fresh["blockers"]:
            self._event("operating.blocked", task_id, reason="invalid, stale or blocked plan")
            return {"status": "blocked", "verified": False, "reasons": fresh["blockers"] or ["Plan changed; re-plan and re-authorize."]}
        rule = fresh["governance"]["rule"]
        try:
            for control in rule["controls"]:
                self.dispatcher.safety.require(control)
            self.dispatcher.policy.authorize(fresh["capability"], security=security)
            trust = max(rule["trust"], int(TrustLevel.EXECUTE_EXTERNAL) if rule["effect"] in {"external", "privileged"} else 0)
            if not self.dispatcher.autonomy.can_execute(TrustLevel(trust), external=rule["effect"] in {"external", "privileged"}):
                raise PermissionError("configured autonomy does not permit this capability")
            with self._lock:
                if task_id in self._runs:
                    raise PermissionError("task id has already executed; create a new reviewed task")
                actor = self.approvals.consume(approval, fresh["fingerprint"]) if fresh["governance"]["approval_required"] else None
                self._event("operating.authorized", task_id, fingerprint=fresh["fingerprint"], actor=actor,
                            sop_id=fresh["sop"]["id"], sop_version=fresh["sop"]["version"])
                self._runs.add(task_id)
        except (PermissionError, ValueError) as exc:
            self._event("operating.blocked", task_id, error=str(exc))
            return {"status": "blocked", "verified": False, "reasons": [str(exc)]}

        task = fresh["task"]
        deadline, calls = self.clock() + task["timeout_seconds"], 0
        doctor = FailureDoctor()

        def dispatch(step):
            nonlocal calls
            if calls >= task["max_calls"] or self.clock() >= deadline:
                return DispatchResult(step["task_id"], "escalated", error="resource budget exhausted")
            if self.plan(task) != fresh:
                return DispatchResult(step["task_id"], "rejected", error="policy, capability or SOP changed during execution")
            # Recheck controls each attempt. Approval never modifies policy, safety or trust.
            try:
                for control in rule["controls"]:
                    self.dispatcher.safety.require(control)
            except PermissionError as exc:
                return DispatchResult(step["task_id"], "rejected", error=str(exc))
            calls += 1
            self._event("operating.tool_call", task_id, capability=step["capability"], attempt=calls)
            result = self.dispatcher.dispatch(step, security=security)
            self._event("operating.tool_result", task_id, attempt=calls, status=result.status,
                        result=result.result, error=result.error)
            if self.clock() >= deadline:
                return DispatchResult(step["task_id"], "escalated", error="execution exceeded wall-time budget")
            if result.status == "failed":
                decision = doctor.diagnose(result.error or "unknown failure", calls, task["max_attempts"])
                self._event("operating.recovery", task_id, action=decision.action, reason=decision.reason)
                if decision.action != "retry":
                    return DispatchResult(step["task_id"], "escalated", error="failure requires operator review")
            return result

        workflow = WorkflowPlan(task_id, task["objective"], [WorkflowStep(
            id="execute", capability=fresh["capability"], input=task["input"],
            verification={"required": True, "checks": fresh["evaluation"]["checks"]},
            max_attempts=task["max_attempts"], on_failure="escalate", trust_required=trust,
            constraints={"timeout_seconds": task["timeout_seconds"], "max_calls": task["max_calls"]},
        )])
        try:
            outcome = WorkflowRunner(dispatch, evidence=self.events).run(workflow)
            step = outcome.steps["execute"]
            ref = self._event("operating.executed", task_id, status=outcome.status, calls=calls)
            report = self.evaluator.evaluate(task_id, task["objective"], tuple(Metric(**c) for c in task["criteria"]),
                                             step.result or {}, audit_passed=outcome.status == "passed", evidence_ref=ref)
            self._event("operating.evaluated", task_id, report_id=report["id"], passed=report["passed"],
                        checks=report["checks"], result_digest=report["result_digest"])
            if report["passed"]:
                lesson = self.knowledge.learn(report["id"])
                self._event("operating.learned", task_id, report_id=report["id"])
                return {"status": "passed", "verified": True, "workflow": asdict(outcome), "evaluation": report, "lesson": lesson}
            self.knowledge.note(task_id, "Task success is not established; inspect execution and evaluation evidence.",
                                kind="unknown", source=ref)
            self._event("operating.escalated", task_id, reason="execution or evaluation failed")
            return {"status": "escalated", "verified": False, "workflow": asdict(outcome), "evaluation": report}
        except Exception as exc:
            self._event("operating.escalated", task_id, error=str(exc))
            return {"status": "escalated", "verified": False, "reasons": [str(exc)]}


def local_read_engine(workspace: Path, *, evidence, safety=None) -> OperatingEngine:
    """Small real vertical slice; no shell, network, deployment or approval UI."""
    from actions.fabric import ActionContext, _safe_path, default_fabric
    from .capabilities import CapabilityRegistry
    from security.policy import Policy

    workspace = workspace.resolve(strict=True)
    fabric = default_fabric()

    def target(task):
        path = _safe_path(workspace, task["input"].get("path", ""))
        if not path.is_file() or path.stat().st_size > 1_000_000:
            raise ValueError("read requires a regular workspace file of at most 1 MB")
        return path

    def execute(task, capability):
        if capability["id"] != "terminal.read" or capability.get("action") != "filesystem.read":
            raise PermissionError("local operating adapter only permits filesystem reads")
        target(task)
        return fabric.execute("filesystem.read", task["input"], ActionContext(task["task_id"], workspace)).output

    def verify_content(task, result):
        return (result.get("content") == target(task).read_text(encoding="utf-8"), "independent file-content comparison")

    dispatcher = Dispatcher(CapabilityRegistry(ROOT / "capabilities/registry.json"),
                            Policy(ROOT / "security/policy.json"), execute,
                            checks={"evidence": verify_content,
                                    "scope_check": lambda task, result: (str(target(task).relative_to(workspace)) == result.get("path"), "workspace containment")},
                            evidence=SafeEvents(evidence), safety=safety)
    return OperatingEngine(dispatcher, allowed_capabilities=frozenset({"terminal.read"}), evidence=evidence)
