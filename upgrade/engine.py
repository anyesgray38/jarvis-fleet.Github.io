"""Self-upgrade control plane.

AEGIS may prepare and validate its own changes, but the engine never executes
arbitrary generated code, writes secrets, changes CI/security controls, or
silently promotes a release. Repository mutation is supplied by an external
adapter after the plan passes these gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Callable, Iterable

from .models import (
    ALLOWED_PATH_PREFIXES, BLOCKED_PATH_PREFIXES, BLOCKED_PATHS,
    UpgradePlan, UpgradeResult, UpgradeStage,
)


@dataclass(frozen=True)
class UpgradePolicy:
    max_files: int = 25
    max_change_bytes: int = 250_000
    require_tests: bool = True
    require_audit: bool = True
    require_human_approval: bool = True


class UpgradeDenied(PermissionError):
    """Raised when an upgrade violates the self-upgrade policy."""


class SelfUpgradeEngine:
    def __init__(self, policy: UpgradePolicy | None = None):
        self.policy = policy or UpgradePolicy()

    def admit(self, plan: UpgradePlan) -> None:
        if not plan.upgrade_id.strip() or not plan.objective.strip():
            raise UpgradeDenied("upgrade id and objective are required")
        if not plan.base_ref.strip():
            raise UpgradeDenied("base ref is required")
        if not plan.files or len(plan.files) > self.policy.max_files:
            raise UpgradeDenied("upgrade file count is outside policy")
        if self.policy.require_tests and not plan.tests:
            raise UpgradeDenied("at least one validation test is required")
        if self.policy.require_human_approval and not plan.require_human_approval:
            raise UpgradeDenied("human approval cannot be disabled by an upgrade plan")
        for raw in plan.files:
            path = PurePosixPath(raw)
            normalized = path.as_posix()
            if path.is_absolute() or ".." in path.parts:
                raise UpgradeDenied(f"unsafe upgrade path: {raw}")
            if normalized in BLOCKED_PATHS or any(normalized.startswith(p) for p in BLOCKED_PATH_PREFIXES):
                raise UpgradeDenied(f"protected path cannot be self-modified: {raw}")
            if not any(normalized.startswith(p) for p in ALLOWED_PATH_PREFIXES):
                raise UpgradeDenied(f"path outside self-upgrade scope: {raw}")

    def stage(self, plan: UpgradePlan, *, changed_bytes: int) -> UpgradeResult:
        self.admit(plan)
        if changed_bytes < 0 or changed_bytes > self.policy.max_change_bytes:
            return UpgradeResult(plan.upgrade_id, UpgradeStage.REJECTED, False,
                                  errors=("change size exceeds policy",))
        digest = sha256(
            (plan.upgrade_id + plan.base_ref + "\n" + "\n".join(plan.files) + "\n" + plan.change_summary).encode()
        ).hexdigest()
        return UpgradeResult(
            plan.upgrade_id, UpgradeStage.STAGED, False,
            evidence=({"kind": "upgrade_plan_hash", "sha256": digest},),
        )

    def validate(
        self,
        staged: UpgradeResult,
        *,
        tests_passed: bool,
        audit_passed: bool,
    ) -> UpgradeResult:
        if staged.stage is not UpgradeStage.STAGED:
            return UpgradeResult(staged.upgrade_id, UpgradeStage.REJECTED, False,
                                 errors=("upgrade is not staged",))
        if not tests_passed:
            return UpgradeResult(staged.upgrade_id, UpgradeStage.FAILED, False,
                                 evidence=staged.evidence, errors=("validation tests failed",))
        if self.policy.require_audit and not audit_passed:
            return UpgradeResult(staged.upgrade_id, UpgradeStage.REJECTED, False,
                                 evidence=staged.evidence, errors=("self-audit failed",))
        return UpgradeResult(staged.upgrade_id, UpgradeStage.READY, False,
                             evidence=staged.evidence + (
                                 {"kind": "tests", "passed": True},
                                 {"kind": "self_audit", "passed": audit_passed},
                             ))

    def approve(self, ready: UpgradeResult, approval: bool) -> UpgradeResult:
        if ready.stage is not UpgradeStage.READY:
            return UpgradeResult(ready.upgrade_id, UpgradeStage.REJECTED, False,
                                 evidence=ready.evidence, errors=("upgrade is not ready",))
        if not approval:
            return UpgradeResult(ready.upgrade_id, UpgradeStage.REJECTED, False,
                                 evidence=ready.evidence, errors=("human approval denied",))
        return UpgradeResult(ready.upgrade_id, UpgradeStage.AUDITED, True,
                             evidence=ready.evidence + ({"kind": "approval", "approved": True},))

    def execute_approved(
        self,
        approved: UpgradeResult,
        *,
        apply: Callable[[str], str],
    ) -> UpgradeResult:
        """Apply only an already-approved staged change through a trusted adapter."""
        if approved.stage is not UpgradeStage.AUDITED or not approved.approved:
            return UpgradeResult(approved.upgrade_id, UpgradeStage.REJECTED, False,
                                 evidence=approved.evidence, errors=("upgrade lacks approval",))
        try:
            commit_ref = apply(approved.upgrade_id)
        except Exception as exc:
            return UpgradeResult(approved.upgrade_id, UpgradeStage.FAILED, False,
                                 evidence=approved.evidence, errors=(str(exc),))
        if not commit_ref or not isinstance(commit_ref, str):
            return UpgradeResult(approved.upgrade_id, UpgradeStage.FAILED, False,
                                 evidence=approved.evidence, errors=("apply adapter returned no commit ref",))
        return UpgradeResult(approved.upgrade_id, UpgradeStage.TESTED, True,
                             commit_ref=commit_ref, evidence=approved.evidence + (
                                 {"kind": "commit", "ref": commit_ref},
                             ))
