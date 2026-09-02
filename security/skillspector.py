"""Adapter for NVIDIA SkillSpector security admission results.

SkillSpector remains an external dependency. This adapter deliberately treats
missing, malformed, failed, or incomplete scans as unsafe.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Sequence


class SecurityScanError(RuntimeError):
    pass


@dataclass(frozen=True)
class SecurityDecision:
    approved: bool
    result: dict[str, Any]


def parse_result(payload: str) -> dict[str, Any]:
    try:
        result = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SecurityScanError("SkillSpector returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise SecurityScanError("SkillSpector result must be a JSON object")
    return result


def admit(result: dict[str, Any], *, max_risk_score: float = 50) -> SecurityDecision:
    if result.get("execution_successful") is not True:
        return SecurityDecision(False, result)
    score = result.get("risk_score")
    if not isinstance(score, (int, float)):
        return SecurityDecision(False, result)
    severity = str(result.get("severity", "")).upper()
    blocked = severity in {"HIGH", "CRITICAL"}
    approved = score <= max_risk_score and not blocked and result.get("approved") is not False
    return SecurityDecision(approved, result)


def scan(target: str, *, executable: str = "skillspector", extra_args: Sequence[str] = ()) -> SecurityDecision:
    """Run an installed SkillSpector CLI and consume its JSON result.

    CLI flags are intentionally supplied by the caller because installations
    may expose different wrappers/versions. The adapter only defines the
    trust boundary and result contract.
    """
    command = [executable, *extra_args, target]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SecurityScanError(f"SkillSpector execution failed: {exc}") from exc
    if completed.returncode != 0:
        raise SecurityScanError(f"SkillSpector exited with code {completed.returncode}")
    return admit(parse_result(completed.stdout))
