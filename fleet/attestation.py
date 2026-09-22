"""Capability attestation for promoting enrolled Fleet nodes."""
from __future__ import annotations

from dataclasses import replace
import re
from typing import Any, Mapping

from .auth import FleetAuthError, RequestSigner, RequestVerifier, SignedRequest
from .node import FleetNode

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class AttestationError(FleetAuthError):
    """Raised when a capability attestation is invalid."""


def _items(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 256 or not all(isinstance(item, str) and item for item in value):
        raise AttestationError(f"{field} must be a bounded list of non-empty strings")
    return tuple(value)


def create_attestation(signer: RequestSigner, *, capabilities: list[str], modalities: list[str],
                       inventory_digest: str, request_id: str, timestamp: int | None = None) -> SignedRequest:
    if not _DIGEST.fullmatch(inventory_digest):
        raise AttestationError("inventory_digest must be a SHA-256 hex digest")
    return signer.sign({
        "kind": "capability_attestation",
        "capabilities": capabilities,
        "modalities": modalities,
        "inventory_digest": inventory_digest,
    }, request_id=request_id, timestamp=timestamp)


class AttestationAuthority:
    """Verify worker attestations and return a newly verified node identity."""

    def __init__(self, secret: str, *, max_age_seconds: int = 60):
        self.verifier = RequestVerifier(secret, max_age_seconds=max_age_seconds)

    def accept(self, node: FleetNode, attestation: SignedRequest | Mapping[str, Any], *, now: int | None = None) -> FleetNode:
        if node.network != "tailscale":
            raise AttestationError("only Tailscale nodes can be attested")
        body = self.verifier.verify(attestation, now=now)
        envelope_node_id = attestation.node_id if isinstance(attestation, SignedRequest) else attestation.get("node_id")
        if envelope_node_id != node.node_id:
            raise AttestationError("attestation node_id does not match enrolled node")
        if set(body) != {"kind", "capabilities", "modalities", "inventory_digest"}:
            raise AttestationError("attestation fields are invalid")
        if body["kind"] != "capability_attestation":
            raise AttestationError("attestation kind is invalid")
        capabilities = _items(body["capabilities"], "capabilities")
        modalities = _items(body["modalities"], "modalities")
        digest = body["inventory_digest"]
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise AttestationError("inventory_digest must be a SHA-256 hex digest")
        metadata = dict(node.metadata)
        metadata.update({"attestation": "verified", "inventory_digest": digest,
                         "attestation_request_id": attestation.request_id if isinstance(attestation, SignedRequest) else attestation["request_id"]})
        return replace(node, trust="verified", capabilities=frozenset(capabilities),
                       modalities=frozenset(modalities), metadata=metadata)
