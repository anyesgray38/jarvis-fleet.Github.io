"""Fail-closed execution policy for Jarvis."""
import json
from pathlib import Path
from typing import Any


class PolicyDenied(PermissionError):
    """Raised when a task is not permitted to proceed."""


class Policy:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def rules_for(self, capability: str) -> dict[str, Any]:
        default = dict(self.data.get("default", {}))
        override = self.data.get("capabilities", {}).get(capability, {})
        default.update(override)
        return default

    def authorize(self, capability: str, *, security: dict[str, Any] | None = None) -> None:
        rules = self.rules_for(capability)
        if not rules.get("require_security_scan", True):
            return
        if security is None:
            raise PolicyDenied("security admission result is required")
        if rules.get("block_incomplete_scan", True) and security.get("execution_successful") is not True:
            raise PolicyDenied("security scan is incomplete or unsuccessful")
        score = security.get("risk_score")
        if not isinstance(score, (int, float)):
            raise PolicyDenied("security scan has no valid risk score")
        if score > rules.get("max_risk_score", 50):
            raise PolicyDenied(f"risk score {score} exceeds policy maximum")
        severity = str(security.get("severity", "")).upper()
        if severity in {str(x).upper() for x in rules.get("blocked_severities", [])}:
            raise PolicyDenied(f"severity {severity} is blocked")
        if security.get("approved") is False:
            raise PolicyDenied("security scanner did not approve execution")
