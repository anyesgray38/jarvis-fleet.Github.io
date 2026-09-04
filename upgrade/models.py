"""Contracts for bounded, auditable AEGIS upgrades."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class UpgradeStage(str, Enum):
    PROPOSED = "proposed"
    ADMITTED = "admitted"
    STAGED = "staged"
    TESTED = "tested"
    AUDITED = "audited"
    READY = "ready"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True)
class UpgradePlan:
    upgrade_id: str
    objective: str
    base_ref: str
    files: tuple[str, ...]
    change_summary: str
    tests: tuple[str, ...] = ()
    require_human_approval: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpgradeResult:
    upgrade_id: str
    stage: UpgradeStage
    approved: bool
    commit_ref: str | None = None
    evidence: tuple[dict[str, Any], ...] = ()
    errors: tuple[str, ...] = ()


ALLOWED_PATH_PREFIXES = (
    "jarvis/", "discovery/", "upgrade/", "mcp/", "fleet/", "actions/",
    "security/", "providers/", "capabilities/", "contracts/", "tests/", "docs/", "web/",
)

BLOCKED_PATH_PREFIXES = (".github/", ".git/", ".ssh/", "secrets/", "credentials/")
BLOCKED_PATHS = {"agent.py", "orchestrator.py"}
