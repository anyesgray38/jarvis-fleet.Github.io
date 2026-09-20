"""Autonomy primitives for the Jarvis control plane.

The module is intentionally dependency-free so the safety/control layer can be
used by every Jarvis domain without depending on a model provider or UI.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from threading import RLock
from typing import Any, Callable
from uuid import uuid4

class TrustLevel(IntEnum):
    OBSERVE=0; SUGGEST=1; PREPARE=2; EXECUTE_LOCAL=3; EXECUTE_EXTERNAL=4; AUTONOMOUS=5

class TaskStatus:
    QUEUED="queued"; AUTHORIZED="authorized"; RUNNING="running"; VERIFYING="verifying"
    PASSED="passed"; FAILED="failed"; REJECTED="rejected"; ESCALATED="escalated"; SKIPPED="skipped"

@dataclass(frozen=True)
class TaskEnvelope:
    task_id: str
    objective: str
    capability: str
    input: dict[str, Any] = field(default_factory=dict)
    trust_required: TrustLevel = TrustLevel.PREPARE
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, objective: str, capability: str, input: dict[str, Any] | None=None, **kwargs: Any) -> "TaskEnvelope":
        if not objective.strip() or not capability.strip(): raise ValueError("objective and capability are required")
        return cls(uuid4().hex, objective, capability, dict(input or {}), **kwargs)

    def as_task(self) -> dict[str, Any]:
        return {"task_id":self.task_id,"objective":self.objective,"capability":self.capability,
                "input":self.input,"metadata":self.metadata}

@dataclass
class Job:
    envelope: TaskEnvelope
    status: str = TaskStatus.QUEUED
    attempts: int = 0
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class JobQueue:
    """Durable-by-interface queue; storage can be replaced without changing callers."""
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}; self._lock=RLock()
    def enqueue(self, envelope: TaskEnvelope) -> Job:
        with self._lock:
            if envelope.task_id in self._jobs: raise ValueError("duplicate task_id")
            job=Job(envelope); self._jobs[envelope.task_id]=job; return job
    def get(self, task_id: str) -> Job | None: return self._jobs.get(task_id)
    def transition(self, task_id: str, status: str, *, result=None, error=None) -> Job:
        if status not in {TaskStatus.QUEUED,TaskStatus.AUTHORIZED,TaskStatus.RUNNING,TaskStatus.VERIFYING,TaskStatus.PASSED,TaskStatus.FAILED,TaskStatus.REJECTED,TaskStatus.ESCALATED,TaskStatus.SKIPPED}:
            raise ValueError("invalid task status")
        with self._lock:
            job=self._jobs[task_id]; job.status=status; job.result=result; job.error=error
            job.updated_at=datetime.now(timezone.utc).isoformat(); return job
    def list(self, status: str | None=None) -> list[Job]:
        with self._lock: return [j for j in self._jobs.values() if status is None or j.status==status]

class MemoryStore:
    """Layered memory: personal, project, procedural, knowledge, evidence."""
    LAYERS=("personal","project","procedural","knowledge","evidence")
    def __init__(self) -> None: self._data={k:{} for k in self.LAYERS}; self._lock=RLock()
    def put(self, layer: str, key: str, value: Any, *, source: str="") -> None:
        if layer not in self._data: raise ValueError("unknown memory layer")
        with self._lock: self._data[layer][key]={"value":value,"source":source,"updated_at":datetime.now(timezone.utc).isoformat()}
    def get(self, layer: str, key: str, default=None) -> Any:
        if layer not in self._data: raise ValueError("unknown memory layer")
        item=self._data[layer].get(key); return default if item is None else item["value"]
    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock: return {k:dict(v) for k,v in self._data.items()}

@dataclass(frozen=True)
class CapabilityContract:
    id: str
    description: str
    inputs: tuple[str,...] = ()
    outputs: tuple[str,...] = ()
    permissions: tuple[str,...] = ()
    risk: str = "low"
    verification: tuple[str,...] = ()
    rollback: str | None = None
    requirements: tuple[str,...] = ()

class CapabilityMatcher:
    def __init__(self, contracts: list[CapabilityContract]): self.contracts={c.id:c for c in contracts}
    def get(self, capability: str) -> CapabilityContract: return self.contracts[capability]
    def compatible(self, capability: str, available: set[str]) -> list[CapabilityContract]:
        c=self.get(capability); return [c] if set(c.requirements).issubset(available) else []

class ActivityFeed:
    def __init__(self) -> None: self._events=[]; self._lock=RLock()
    def emit(self, event: str, task_id: str, **data: Any) -> dict[str, Any]:
        record={"event":event,"task_id":task_id,"timestamp":datetime.now(timezone.utc).isoformat(),**data}
        with self._lock: self._events.append(record)
        return record
    def list(self, task_id: str | None=None) -> list[dict[str,Any]]:
        with self._lock: return [e for e in self._events if task_id is None or e["task_id"]==task_id]

class RollbackRegistry:
    def __init__(self) -> None: self._actions: dict[str,Callable[[],Any]]={}
    def register(self, task_id: str, rollback: Callable[[],Any]) -> None: self._actions[task_id]=rollback
    def rollback(self, task_id: str) -> Any:
        action=self._actions.get(task_id)
        if action is None: raise KeyError(f"no rollback registered: {task_id}")
        return action()

@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    reason: str
    next_attempt: int

class FailureDoctor:
    """Turns failures into bounded recovery decisions; it never executes a fix itself."""
    def diagnose(self, error: str, attempt: int, max_attempts: int) -> RecoveryDecision:
        text=error.lower()
        if "timeout" in text or "tempor" in text:
            action="retry"; reason="transient failure"
        elif "provider" in text or "unavailable" in text:
            action="failover"; reason="execution provider unavailable"
        elif "verification" in text or "audit" in text:
            action="replan"; reason="output failed independent verification"
        else:
            action="escalate"; reason="failure cause is not safely recoverable"
        if action in {"retry","failover","replan"} and attempt < max_attempts:
            return RecoveryDecision(action,reason,attempt+1)
        return RecoveryDecision("escalate",f"{reason}; retry budget exhausted",attempt)

class AutonomyController:
    def __init__(self, level: TrustLevel=TrustLevel.PREPARE): self.level=level
    def can_execute(self, required: TrustLevel, *, external: bool=False) -> bool:
        if self.level < required: return False
        if external and self.level < TrustLevel.EXECUTE_EXTERNAL: return False
        return True

@dataclass(frozen=True)
class SimulationResult:
    task_id: str
    would_execute: bool
    side_effects: tuple[str,...]
    reason: str

def simulate(envelope: TaskEnvelope, controller: AutonomyController) -> SimulationResult:
    allowed=controller.can_execute(envelope.trust_required, external=envelope.trust_required>=TrustLevel.EXECUTE_EXTERNAL)
    effects=("execution",) if allowed else ()
    return SimulationResult(envelope.task_id, allowed, effects, "policy permits execution" if allowed else "trust level requires approval")
