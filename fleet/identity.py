"""Authenticated identity and request-signing primitives for Fleet nodes.

Secrets are deployment-local. This module never persists bootstrap credentials.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any


class IdentityError(PermissionError):
    """Raised when a Fleet identity or signature cannot be trusted."""


@dataclass(frozen=True)
class NodeIdentity:
    node_id: str
    public_name: str
    network: str = "tailscale"
    key_id: str = ""
    trust: str = "untrusted"
    enrolled_at: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "public_name": self.public_name,
            "network": self.network,
            "key_id": self.key_id,
            "trust": self.trust,
            "enrolled_at": self.enrolled_at,
        }


def canonical_json(value: Any) -> bytes:
    """Serialize protocol data deterministically before signing."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sign_request(secret: bytes, *, node_id: str, request_id: str, payload: Any,
                 timestamp: int | None = None) -> dict[str, Any]:
    """Create an HMAC-SHA256 envelope for a Fleet request."""
    ts = int(time.time()) if timestamp is None else int(timestamp)
    envelope = {"node_id": node_id, "request_id": request_id, "timestamp": ts, "payload": payload}
    signature = hmac.new(secret, canonical_json(envelope), hashlib.sha256).hexdigest()
    return {**envelope, "signature": signature}


def verify_request(secret: bytes, envelope: dict[str, Any], *, max_age_seconds: int = 60,
                   now: int | None = None) -> bool:
    """Verify authenticity, freshness and required envelope fields."""
    required = {"node_id", "request_id", "timestamp", "payload", "signature"}
    if not required.issubset(envelope):
        return False
    try:
        timestamp = int(envelope["timestamp"])
    except (TypeError, ValueError):
        return False
    current = int(time.time()) if now is None else int(now)
    if abs(current - timestamp) > max_age_seconds:
        return False
    unsigned = {key: envelope[key] for key in required if key != "signature"}
    expected = hmac.new(secret, canonical_json(unsigned), hashlib.sha256).hexdigest()
    return hmac.compare_digest(str(envelope["signature"]), expected)


def new_request_id() -> str:
    return secrets.token_urlsafe(18)
