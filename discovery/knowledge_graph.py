"""Domain-agnostic knowledge graph for discovery provenance and relationships."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    kind: str
    label: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class GraphEdge:
    source: str
    relation: str
    target: str


class KnowledgeGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []

    def add_node(self, node: GraphNode) -> GraphNode:
        if node.node_id in self.nodes:
            raise ValueError(f"duplicate graph node: {node.node_id}")
        self.nodes[node.node_id] = node
        return node

    def relate(self, source: str, relation: str, target: str) -> GraphEdge:
        if source not in self.nodes or target not in self.nodes:
            raise ValueError("graph edge references unknown node")
        edge = GraphEdge(source, relation, target)
        if edge not in self.edges:
            self.edges.append(edge)
        return edge

    def neighbors(self, node_id: str, relation: str | None = None) -> tuple[GraphNode, ...]:
        targets = [e.target for e in self.edges if e.source == node_id and (relation is None or e.relation == relation)]
        return tuple(self.nodes[target] for target in targets)

    def connected_claims(self, claim_id: str) -> tuple[GraphNode, ...]:
        return tuple(node for node in self.neighbors(claim_id) if node.kind == "claim")
