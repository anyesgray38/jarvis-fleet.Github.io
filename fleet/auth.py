"""Authenticated Fleet enrollment and replay-resistant request signing."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
import time
from typing import Any, Mapping

from .node import FleetNode

_NODE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class FleetAuthError(ValueError):
    """Raised when an enrollment or signed request fails authentication."""


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _signature(secret: str, value: Mapping[str, Any]) -> str:
    if not isinstance(secret, str) or not secret:
        raise FleetAuthError("signing secret is required")
    return hmac.new(secret.encode("utf-8"), _canonical(value), hashlib.sha256).hexdigest()


def _check_timestamp(timestamp: Any, max_age_seconds: int, now: int | None) -> int:
    if isinstance(timestamp, bool) or not isinstance(timestamp, int):
        raise FleetAuthError("timestamp must be an integer Unix timestamp")
    current = int(time.time()) if now is None else now
    if abs(current - timestamp) > max_age_seconds:
        raise FleetAuthError("request timestamp is outside the allowed age")
    return timestamp


def _check_strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise FleetAuthError(f"{field} must be a list of non-empty strings")
    return tuple(value)


@dataclass(frozen=True)
class SignedRequest:
    node_id: str
    request_id: str
    timestamp: int
    body: dict[str, Any]
    signature: str

    def unsigned(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "body": self.body,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned(), "signature": self.signature}


class RequestSigner:
    """Create signed request envelopes for one enrolled Fleet node."""

    def __init__(self, secret: str, node_id: str):
        if not _NODE_ID.fullmatch(node_id):
            raise FleetAuthError("node_id is invalid")
        self.secret = secret
        self.node_id = node_id

    def sign(self, body: Mapping[str, Any], *, request_id: str, timestamp: int | None = None) -> SignedRequest:
        if not _REQUEST_ID.fullmatch(request_id):
            raise FleetAuthError("request_id is invalid")
        if not isinstance(body, Mapping):
            raise FleetAuthError("request body must be an object")
        envelope = {
            "node_id": self.node_id,
            "request_id": request_id,
            "timestamp": int(time.time()) if timestamp is None else timestamp,
            "body": dict(body),
        }
        return SignedRequest(**envelope, signature=_signature(self.secret, envelope))


class RequestVerifier:
    """Verify signed requests and reject duplicate request IDs."""

    def __init__(self, secret: str, *, max_age_seconds: int = 60, expected_node_id: str | None = None):
        if max_age_seconds < 1:
            raise FleetAuthError("max_age_seconds must be positive")
        if expected_node_id is not None and not _NODE_ID.fullmatch(expected_node_id):
            raise FleetAuthError("expected node_id is invalid")
        self.secret = secret
        self.max_age_seconds = max_age_seconds
        self.expected_node_id = expected_node_id
        self._seen: set[str] = set()

    def verify(self, request: SignedRequest | Mapping[str, Any], *, now: int | None = None) -> dict[str, Any]:
        if isinstance(request, SignedRequest):
            envelope = request.to_dict()
        elif isinstance(request, Mapping):
            envelope = dict(request)
        else:
            raise FleetAuthError("request must be an object")
        required = {"node_id", "request_id", "timestamp", "body", "signature"}
        if set(envelope) != required:
            raise FleetAuthError("signed request fields are invalid")
        node_id = envelope["node_id"]
        request_id = envelope["request_id"]
        if not isinstance(node_id, str) or not _NODE_ID.fullmatch(node_id):
            raise FleetAuthError("node_id is invalid")
        if self.expected_node_id is not None and node_id != self.expected_node_id:
            raise FleetAuthError("request node_id is not admitted")
        if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
            raise FleetAuthError("request_id is invalid")
        _check_timestamp(envelope["timestamp"], self.max_age_seconds, now)
        if not isinstance(envelope["body"], Mapping) or not isinstance(envelope["signature"], str):
            raise FleetAuthError("request body or signature is invalid")
        unsigned = {key: envelope[key] for key in ("node_id", "request_id", "timestamp", "body")}
        expected = _signature(self.secret, unsigned)
        if not hmac.compare_digest(envelope["signature"], expected):
            raise FleetAuthError("request signature is invalid")
        if request_id in self._seen:
            raise FleetAuthError("request has already been seen")
        self._seen.add(request_id)
        return dict(envelope["body"])


class EnrollmentAuthority:
    """Admit nodes with a bootstrap signature, always starting untrusted."""

    def __init__(self, bootstrap_token: str, *, max_age_seconds: int = 60):
        if not bootstrap_token:
            raise FleetAuthError("bootstrap token is required")
        if max_age_seconds < 1:
            raise FleetAuthError("max_age_seconds must be positive")
        self.bootstrap_token = bootstrap_token
        self.max_age_seconds = max_age_seconds
        self._enrolled: set[str] = set()

    def enroll(self, request: SignedRequest | Mapping[str, Any], *, now: int | None = None) -> FleetNode:
        if isinstance(request, SignedRequest):
            envelope = request.to_dict()
        elif isinstance(request, Mapping):
            envelope = dict(request)
        else:
            raise FleetAuthError("enrollment request must be an object")
        body = RequestVerifier(self.bootstrap_token, max_age_seconds=self.max_age_seconds).verify(envelope, now=now)
        node_id = envelope["node_id"]
        if node_id in self._enrolled:
            raise FleetAuthError("node is already enrolled")
        if body.get("network") != "tailscale":
            raise FleetAuthError("only Tailscale enrollment is permitted")
        address = body.get("address")
        if address is not None and (not isinstance(address, str) or not address):
            raise FleetAuthError("address must be a non-empty string when provided")
        capabilities = _check_strings(body.get("capabilities", []), "capabilities")
        modalities = _check_strings(body.get("modalities", []), "modalities")
        labels = _check_strings(body.get("labels", []), "labels")
        self._enrolled.add(node_id)
        return FleetNode(
            node_id=node_id,
            address=address,
            network="tailscale",
            trust="untrusted",
            status="connected",
            capabilities=frozenset(capabilities),
            modalities=frozenset(modalities),
            labels=frozenset(labels),
            metadata={"attestation": "pending", "enrollment_request_id": envelope["request_id"]},
        )
