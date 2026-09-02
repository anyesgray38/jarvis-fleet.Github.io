"""Deterministic scheduling across admitted AEGIS Fleet nodes."""
from __future__ import annotations
from dataclasses import dataclass
from .node import FleetNode
from .policy import NetworkPolicy, NetworkRequest

@dataclass(frozen=True)
class Workload:
    capability: str
    required_labels: frozenset[str] = frozenset()
    required_modalities: frozenset[str] = frozenset()
    network: NetworkRequest = NetworkRequest()
    preferred_node: str | None = None

@dataclass(frozen=True)
class NodeScore:
    node_id: str
    score: float
    reasons: tuple[str, ...]

class FleetScheduler:
    """Select the best admitted node without executing work itself."""
    def __init__(self, nodes: list[FleetNode], *, network_policy: NetworkPolicy | None = None):
        self.nodes = tuple(nodes)
        self.network_policy = network_policy or NetworkPolicy()

    def rank(self, workload: Workload) -> list[NodeScore]:
        ranked: list[NodeScore] = []
        for node in self.nodes:
            if node.status not in {"ready", "connected", "healthy"} or not node.supports(workload.capability):
                continue
            if not workload.required_labels.issubset(node.labels) or not workload.required_modalities.issubset(node.modalities):
                continue
            try:
                self.network_policy.authorize(workload.network, node=node)
            except PermissionError:
                continue
            score = 0.0
            reasons: list[str] = []
            if workload.preferred_node == node.node_id:
                score += 100.0; reasons.append("preferred node")
            score += len(workload.required_labels & node.labels) * 10.0
            score += len(workload.required_modalities & node.modalities) * 5.0
            if node.network == "tailscale":
                score += 2.0; reasons.append("private overlay")
            if node.trust == "verified":
                score += 5.0; reasons.append("verified node")
            ranked.append(NodeScore(node.node_id, score, tuple(reasons)))
        return sorted(ranked, key=lambda x: (-x.score, x.node_id))

    def resolve(self, workload: Workload) -> NodeScore:
        ranked = self.rank(workload)
        if not ranked:
            raise LookupError("No admitted Fleet node satisfies workload constraints")
        return ranked[0]
