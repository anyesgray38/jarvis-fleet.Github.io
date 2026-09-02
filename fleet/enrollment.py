"""Deployment-local Fleet enrollment policy.

Enrollment establishes an identity; it does not automatically grant trust.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any

from .identity import NodeIdentity


class EnrollmentDenied(PermissionError):
    """Raised when a node cannot be enrolled."""


@dataclass(frozen=True)
class EnrollmentRequest:
    node_id: str
    public_name: str
    bootstrap_token: str
    network: str = "tailscale"
    requested_capabilities: frozenset[str] = frozenset()


class EnrollmentAuthority:
    """Issue identities from a deployment-local bootstrap secret.

    The raw bootstrap token is never stored; only a SHA-256 digest is retained.
    Newly enrolled nodes remain untrusted until a separate attestation step.
    """

    def __init__(self, bootstrap_token: str, *, allowed_networks: set[str] | None = None):
        if not bootstrap_token:
            raise ValueError("bootstrap token is required")
        self._token_digest = hashlib.sha256(bootstrap_token.encode()).digest()
        self.allowed_networks = frozenset(allowed_networks or {"tailscale"})

    def enroll(self, request: EnrollmentRequest) -> NodeIdentity:
        if request.network not in self.allowed_networks:
            raise EnrollmentDenied("network is not approved for enrollment")
        if not request.node_id or not request.public_name:
            raise EnrollmentDenied("node identity fields are required")
        supplied = hashlib.sha256(request.bootstrap_token.encode()).digest()
        if not hmac.compare_digest(supplied, self._token_digest):
            raise EnrollmentDenied("invalid bootstrap credential")
        key_id = hashlib.sha256(f"{request.node_id}:{request.public_name}".encode()).hexdigest()[:24]
        return NodeIdentity(
            node_id=request.node_id,
            public_name=request.public_name,
            network=request.network,
            key_id=key_id,
            trust="untrusted",
            enrolled_at=int(time.time()),
        )

    @staticmethod
    def metadata(identity: NodeIdentity) -> dict[str, Any]:
        return {"identity": identity.to_dict(), "trust_transition_required": True}
