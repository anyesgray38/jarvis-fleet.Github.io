"""Capability attestation for Fleet workers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CapabilityAttestation:
    node_id: str
    capabilities: frozenset[str]
    modalities: frozenset[str] = frozenset()
    providers: frozenset[str] = frozenset()
    evidence_id: str | None = None
    verified: bool = False

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "capabilities": sorted(self.capabilities),
            "modalities": sorted(self.modalities),
            "providers": sorted(self.providers),
            "evidence_id": self.evidence_id,
            "verified": self.verified,
        }


def attest_node(node_id: str, capabilities: set[str] | frozenset[str], *,
                modalities: set[str] | frozenset[str] = frozenset(),
                providers: set[str] | frozenset[str] = frozenset(),
                evidence_id: str | None = None,
                verified: bool = False) -> CapabilityAttestation:
    """Build an explicit capability statement; callers decide how to verify it."""
    if not node_id:
        raise ValueError("node_id is required")
    return CapabilityAttestation(
        node_id=node_id,
        capabilities=frozenset(capabilities),
        modalities=frozenset(modalities),
        providers=frozenset(providers),
        evidence_id=evidence_id,
        verified=verified,
    )
