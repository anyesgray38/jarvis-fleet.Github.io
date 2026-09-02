"""Network-neutral Fleet node identity and capability inventory."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FleetNode:
    """A remotely executable AEGIS worker.

    Network membership never implies execution trust. Admission/trust are
    explicit fields so a private overlay cannot silently become a privilege.
    """

    node_id: str
    address: str | None = None
    network: str = "tailscale"
    role: str = "worker"
    trust: str = "untrusted"
    status: str = "unknown"
    capabilities: frozenset[str] = frozenset()
    modalities: frozenset[str] = frozenset()
    labels: frozenset[str] = frozenset()
    metadata: dict[str, Any] = field(default_factory=dict)

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "address": self.address,
            "network": self.network,
            "role": self.role,
            "trust": self.trust,
            "status": self.status,
            "capabilities": sorted(self.capabilities),
            "modalities": sorted(self.modalities),
            "labels": sorted(self.labels),
            "metadata": dict(self.metadata),
        }
