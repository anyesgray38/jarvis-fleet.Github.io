"""Transport-independent remote execution contract for AEGIS Fleet."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .identity import sign_request, verify_request, new_request_id


class TransportDenied(PermissionError):
    """Raised when a remote request fails authentication or policy."""


@dataclass(frozen=True)
class ExecutionRequest:
    task_id: str
    capability: str
    input: Any
    verification: dict[str, Any]
    network: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "capability": self.capability,
            "input": self.input,
            "verification": self.verification,
            "network": self.network or {},
        }


class SignedTransport:
    """Small protocol contract that can sit over Tailscale, HTTPS, or another overlay.

    It deliberately does not open sockets. Deployment adapters provide ``send``.
    """

    def __init__(self, *, node_id: str, secret: bytes, send: Callable[[dict[str, Any]], dict[str, Any]], max_age_seconds: int = 60):
        self.node_id = node_id
        self.secret = secret
        self.send = send
        self.max_age_seconds = max_age_seconds

    def dispatch(self, request: ExecutionRequest) -> dict[str, Any]:
        envelope = sign_request(
            self.secret,
            node_id=self.node_id,
            request_id=new_request_id(),
            payload=request.to_dict(),
        )
        response = self.send(envelope)
        if not isinstance(response, dict):
            raise TransportDenied("remote response is not a structured object")
        return response

    @staticmethod
    def verify(envelope: dict[str, Any], *, secret: bytes, max_age_seconds: int = 60) -> bool:
        return verify_request(secret, envelope, max_age_seconds=max_age_seconds)
