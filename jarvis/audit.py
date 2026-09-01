"""Deterministic self-audit primitives for Jarvis task results."""
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AuditCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class AuditReport:
    task_id: str
    checks: list[AuditCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "passed": self.passed,
            "checks": [c.__dict__ for c in self.checks],
        }


def audit_result(
    task: dict[str, Any],
    result: dict[str, Any],
    checks: dict[str, Callable[[dict[str, Any], dict[str, Any]], tuple[bool, str]]],
) -> AuditReport:
    """Run named independent checks without mutating the task result."""
    report = AuditReport(task_id=str(task["task_id"]))
    for name in task.get("verification", {}).get("checks", []):
        fn = checks.get(name)
        if fn is None:
            report.checks.append(AuditCheck(name, False, "verification check not registered"))
            continue
        try:
            passed, detail = fn(task, result)
        except Exception as exc:
            passed, detail = False, f"check raised: {exc}"
        report.checks.append(AuditCheck(name, bool(passed), str(detail)))
    return report
