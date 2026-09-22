"""Independent verification on a separate trusted Fleet node."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from .node import FleetNode
from .transport import FleetTransportError, SignedRemoteTransport


def artifact_digest(artifact: Mapping[str, Any]) -> str:
    if not isinstance(artifact, Mapping):
        raise ValueError("artifact must be an object")
    canonical = json.dumps(dict(artifact), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    verifier_node_id: str
    task_id: str
    artifact_digest: str
    checks: dict[str, bool]
    error: str | None = None


class IndependentVerifier:
    """Require a distinct verified node for high-risk result verification."""

    def __init__(self, transport: SignedRemoteTransport):
        self.transport = transport

    def verify(self, *, execution_node: FleetNode, verifier_node: FleetNode, task_id: str,
               artifact: Mapping[str, Any], request_id: str, timestamp: int | None = None,
               now: int | None = None) -> VerificationResult:
        digest = artifact_digest(artifact)
        if execution_node.node_id == verifier_node.node_id:
            return VerificationResult(False, verifier_node.node_id, task_id, digest,
                                     {"distinct_node": False}, "verification node must be distinct")
        if verifier_node.trust != "verified":
            return VerificationResult(False, verifier_node.node_id, task_id, digest,
                                     {"verified_node": False}, "verification node is not verified")
        try:
            response = self.transport.execute(
                verifier_node, "verification.run",
                {"task_id": task_id, "artifact": dict(artifact), "artifact_digest": digest},
                request_id=request_id, timestamp=timestamp, now=now,
            )
        except FleetTransportError as exc:
            return VerificationResult(False, verifier_node.node_id, task_id, digest,
                                     {"transport": False}, str(exc))
        checks = {
            "distinct_node": True,
            "verified_node": True,
            "remote_verified": response.get("verified") is True,
            "task_id": response.get("task_id") == task_id,
            "artifact_digest": response.get("artifact_digest") == digest,
        }
        return VerificationResult(all(checks.values()), verifier_node.node_id, task_id, digest, checks,
                                  None if all(checks.values()) else "independent verification failed")
