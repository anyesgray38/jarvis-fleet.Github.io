"""Explicit network policy for distributed AEGIS execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class NetworkPolicyDenied(PermissionError):
    """Raised when a workload violates its network constraints."""


@dataclass(frozen=True)
class NetworkRequest:
    internet: bool = False
    private_network: bool = True
    exit_node: str | None = None
    public_bind: bool = False
    destination_classes: frozenset[str] = frozenset()


class NetworkPolicy:
    """Fail-closed network admission independent of the transport provider."""

    def __init__(self, *, allow_internet: bool = True, allow_exit_nodes: bool = True,
                 allow_public_bind: bool = False, approved_exit_nodes: set[str] | None = None):
        self.allow_internet = allow_internet
        self.allow_exit_nodes = allow_exit_nodes
        self.allow_public_bind = allow_public_bind
        self.approved_exit_nodes = frozenset(approved_exit_nodes or set())

    def authorize(self, request: NetworkRequest, *, node: Any | None = None) -> None:
        if request.internet and not self.allow_internet:
            raise NetworkPolicyDenied("internet access is disabled by Fleet policy")
        if request.exit_node:
            if not self.allow_exit_nodes:
                raise NetworkPolicyDenied("exit-node routing is disabled by Fleet policy")
            if self.approved_exit_nodes and request.exit_node not in self.approved_exit_nodes:
                raise NetworkPolicyDenied(f"exit node {request.exit_node!r} is not approved")
        if request.public_bind and not self.allow_public_bind:
            raise NetworkPolicyDenied("public binds are disabled by Fleet policy")
        if node is not None:
            trust = str(getattr(node, "trust", "untrusted"))
            if trust not in {"trusted", "verified"}:
                raise NetworkPolicyDenied("remote node is not trusted for network execution")

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "NetworkPolicy":
        return NetworkPolicy(
            allow_internet=bool(data.get("allow_internet", True)),
            allow_exit_nodes=bool(data.get("allow_exit_nodes", True)),
            allow_public_bind=bool(data.get("allow_public_bind", False)),
            approved_exit_nodes=set(str(x) for x in data.get("approved_exit_nodes", [])),
        )
