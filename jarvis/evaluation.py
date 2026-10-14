"""Task-specific metrics and provenance, layered over existing audit and memory."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import math
from uuid import uuid4

from .autonomy import MemoryStore
from .verification import evidence_digest


ARTIFACT_KINDS = {"code", "prompt", "model", "configuration", "workflow"}
SUITES = {
    "code": ("tests", "diff_review"),
    "prompt": ("prompt_regression", "safety_regression"),
    "model": ("model_regression", "resource_regression"),
    "configuration": ("schema_validation", "startup_regression"),
    "workflow": ("workflow_dry_run", "policy_regression"),
}


def cicd_selection(artifact_kind: str | None) -> dict:
    if artifact_kind is None:
        return {"applicable": False, "reason": "No versioned artifact change was declared or required by the capability.", "checks": []}
    if artifact_kind not in ARTIFACT_KINDS:
        raise ValueError("unsupported artifact kind")
    return {"applicable": True, "reason": f"A versioned {artifact_kind} change needs validation and controlled release.",
            "checks": list(SUITES[artifact_kind]),
            "stages": ["propose", "test", "compare", "approve", "promote", "monitor", "rollback"]}


@dataclass(frozen=True)
class Metric:
    name: str
    field: str
    operator: str
    expected: object

    def validate(self):
        if not self.name.strip() or not self.field.strip() or any(not p for p in self.field.split(".")):
            raise ValueError("metrics require names and dotted result fields")
        if self.operator not in {"equals", "at_least", "at_most", "contains"}:
            raise ValueError("unsupported metric operator")
        if not isinstance(self.expected, (str, int, float, bool)) or (
            isinstance(self.expected, float) and not math.isfinite(self.expected)
        ):
            raise ValueError("metric expectations must be finite JSON scalar values")
        if self.operator in {"at_least", "at_most"} and type(self.expected) not in {int, float}:
            raise ValueError("numeric metrics require numeric expectations")
        if self.operator == "contains" and not isinstance(self.expected, str):
            raise ValueError("contains requires a string expectation")

    def check(self, result: dict) -> dict:
        self.validate()
        actual = result
        try:
            for key in self.field.split("."):
                actual = actual[key]
            if self.operator == "equals":
                passed = type(actual) is type(self.expected) and actual == self.expected
            elif self.operator == "contains":
                passed = isinstance(actual, str) and self.expected in actual
            else:
                passed = (type(actual) in {int, float} and math.isfinite(actual)
                          and (actual >= self.expected if self.operator == "at_least" else actual <= self.expected))
        except (KeyError, TypeError, IndexError):
            passed = False
        return {"name": self.name, "passed": bool(passed), "field": self.field, "operator": self.operator}


class EvaluationEngine:
    """Only this evaluator issues receipts consumed by verified memory."""
    def __init__(self):
        self._reports = {}

    def evaluate(self, task_id: str, objective: str, criteria: tuple[Metric, ...], result: dict,
                 *, audit_passed: bool, evidence_ref: str) -> dict:
        checks = [metric.check(result) for metric in criteria]
        report = {"id": uuid4().hex, "task_id": task_id, "objective": objective,
                  "passed": audit_passed is True and bool(checks) and all(c["passed"] for c in checks) and bool(evidence_ref),
                  "checks": checks, "evidence_ref": evidence_ref,
                  "result_digest": evidence_digest(result)}
        self._reports[report["id"]] = deepcopy(report)
        return report

    def get(self, report_id: str) -> dict:
        return deepcopy(self._reports[report_id])


class KnowledgeLedger:
    """Facts are scoped evaluation conclusions, not arbitrary model assertions."""
    def __init__(self, memory: MemoryStore, evaluator: EvaluationEngine):
        self.memory, self.evaluator = memory, evaluator

    def note(self, key: str, statement: str, *, kind: str, source: str):
        if kind not in {"assumption", "hypothesis", "unknown"} or not source.strip() or not statement.strip():
            raise ValueError("unverified knowledge needs an epistemic kind and source")
        self.memory.put("knowledge", f"{kind}:{key}", {"kind": kind, "statement": statement, "source": source}, source=source)

    def learn(self, report_id: str):
        report = self.evaluator.get(report_id)
        if not report["passed"]:
            raise ValueError("failed or unverified outcomes cannot become verified facts")
        fact = {"kind": "verified_fact", "statement": "The named task met its recorded evaluation criteria.",
                "task_id": report["task_id"], "objective": report["objective"],
                "report_id": report_id, "evidence_ref": report["evidence_ref"],
                "result_digest": report["result_digest"]}
        self.memory.put("knowledge", f"verified_fact:{report_id}", fact, source=report["evidence_ref"])
        return fact
