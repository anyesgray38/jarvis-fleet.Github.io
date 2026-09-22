"""Governed signed transport for remote Fleet execution."""
from __future__ import annotations

from typing import Any, Callable, Mapping
import re

from .auth import FleetAuthError, RequestSigner, RequestVerifier
from .node import FleetNode
from .policy import NetworkPolicy, NetworkRequest

_OPERATION = re.compile(r"^[a-z][A-Za-z0-9_.:-]{0,63}$")


class FleetTransportError(RuntimeError):
    """Raised when a remote execution cannot be admitted or verified."""


class SignedRemoteTransport:
    """Send authenticated operations over an injected private-network sender.

    The sender owns the actual socket/HTTP implementation. This layer owns
    admission, request signing, response authentication, and correlation.
    """

    def __init__(self, secret: str, *, local_node_id: str = "aegis-control-plane",
                 sender: Callable[[FleetNode, dict[str, Any]], Mapping[str, Any]],
                 network_policy: NetworkPolicy | None = None, max_age_seconds: int = 60):
        self.signer = RequestSigner(secret, local_node_id)
        self.secret = secret
        self.sender = sender
        self.network_policy = network_policy or NetworkPolicy()
        self.max_age_seconds = max_age_seconds

    def execute(self, node: FleetNode, operation: str, payload: Mapping[str, Any], *,
                request_id: str, timestamp: int | None = None, now: int | None = None) -> dict[str, Any]:
        if node.network != "tailscale":
            raise FleetTransportError("remote execution requires a Tailscale node")
        if node.trust not in {"trusted", "verified"}:
            raise FleetTransportError("remote execution requires a trusted or verified node")
        if node.status not in {"connected", "healthy", "ready"}:
            raise FleetTransportError("remote node is not live")
        if not isinstance(operation, str) or not _OPERATION.fullmatch(operation):
            raise FleetTransportError("operation is invalid")
        if not isinstance(payload, Mapping):
            raise FleetTransportError("operation payload must be an object")
        try:
            self.network_policy.authorize(NetworkRequest(private_network=True), node=node)
        except PermissionError as exc:
            raise FleetTransportError(str(exc)) from exc
        request = self.signer.sign({"operation": operation, "payload": dict(payload)},
                                   request_id=request_id, timestamp=timestamp)
        try:
            response = self.sender(node, request.to_dict())
        except Exception as exc:
            raise FleetTransportError("remote sender failed") from exc
        if not isinstance(response, Mapping) or response.get("request_id") != request_id:
            raise FleetTransportError("remote response does not match request")
        verifier = RequestVerifier(self.secret, max_age_seconds=self.max_age_seconds,
                                   expected_node_id=node.node_id)
        try:
            return verifier.verify(response, now=now)
        except FleetAuthError as exc:
            raise FleetTransportError(str(exc)) from exc
