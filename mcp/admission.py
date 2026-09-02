"""Security admission for external MCP capabilities.

Admission is deliberately separate from transport. A server can be reachable
and protocol-correct while still being unsafe to expose to an agent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class AdmissionDecision:
    approved: bool
    server_id: str
    risk_score: float
    reasons: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    scanner: str = "builtin"
    scan_complete: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "server_id": self.server_id,
            "risk_score": self.risk_score,
            "reasons": list(self.reasons),
            "permissions": list(self.permissions),
            "scanner": self.scanner,
            "execution_successful": self.scan_complete,
        }


Scanner = Callable[[dict[str, Any], list[dict[str, Any]]], dict[str, Any]]


class AdmissionController:
    """Evaluate an MCP server before tool exposure or invocation."""

    def __init__(self, *, max_risk_score: float = 35.0, scanners: dict[str, Scanner] | None = None):
        self.max_risk_score = max_risk_score
        self.scanners = scanners or {}

    def inspect(self, server: dict[str, Any], tools: list[dict[str, Any]], *, scanner: str | None = None) -> AdmissionDecision:
        server_id = str(server.get("id") or server.get("name") or "unknown")
        reasons: list[str] = []
        permissions: set[str] = set()
        risk = 0.0

        for tool in tools:
            name = str(tool.get("name", ""))
            description = str(tool.get("description", ""))
            schema = tool.get("inputSchema")
            blob = (name + " " + description).lower()
            if any(token in blob for token in ("delete", "destroy", "drop database", "shutdown", "kill", "wipe")):
                risk += 8
                permissions.add("destructive")
                reasons.append(f"destructive tool surface: {name}")
            if any(token in blob for token in ("shell", "exec", "command", "terminal", "powershell")):
                risk += 10
                permissions.add("command_execution")
                reasons.append(f"command execution surface: {name}")
            if any(token in blob for token in ("write file", "filesystem", "upload", "modify file")):
                risk += 6
                permissions.add("filesystem_write")
                reasons.append(f"filesystem write surface: {name}")
            if not isinstance(schema, dict) or schema.get("type") != "object":
                risk += 2
                reasons.append(f"weak input schema: {name}")
            if _looks_like_prompt_injection(description):
                risk += 15
                permissions.add("prompt_injection_risk")
                reasons.append(f"instruction-bearing tool description: {name}")

        custom_result = None
        scanner_name = scanner or (next(iter(self.scanners), None))
        if scanner_name:
            scan = self.scanners.get(scanner_name)
            if scan is None:
                return AdmissionDecision(False, server_id, 100.0, ("requested scanner is unavailable",), scanner=scanner_name, scan_complete=False)
            try:
                custom_result = scan(server, tools)
            except Exception as exc:
                return AdmissionDecision(False, server_id, 100.0, (f"security scanner failed: {exc}",), scanner=scanner_name, scan_complete=False)
            if not isinstance(custom_result, dict) or custom_result.get("execution_successful") is not True:
                return AdmissionDecision(False, server_id, 100.0, ("security scanner returned incomplete results",), scanner=scanner_name, scan_complete=False)
            if isinstance(custom_result.get("risk_score"), (int, float)):
                risk = max(risk, float(custom_result["risk_score"]))
            if custom_result.get("approved") is False:
                reasons.append("external scanner rejected server")
            reasons.extend(str(x) for x in custom_result.get("reasons", []) if x)

        approved = risk <= self.max_risk_score and not (custom_result and custom_result.get("approved") is False)
        if not tools:
            reasons.append("server exposed no tools")
        return AdmissionDecision(
            approved=approved,
            server_id=server_id,
            risk_score=min(100.0, risk),
            reasons=tuple(dict.fromkeys(reasons)),
            permissions=tuple(sorted(permissions)),
            scanner=scanner_name or "builtin",
            scan_complete=True,
        )


def _looks_like_prompt_injection(text: str) -> bool:
    lowered = text.lower()
    patterns = (
        "ignore previous instructions",
        "ignore all previous",
        "system message",
        "do not tell the user",
        "secret instruction",
        "must obey",
        "reveal the prompt",
    )
    return any(pattern in lowered for pattern in patterns)
