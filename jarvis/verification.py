"""Independent, deterministic checks for AEGIS model results."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def verify_inference_response(response: dict[str, Any]) -> dict[str, Any]:
    content = response.get("content")
    checks = {
        "response_object": isinstance(response, dict),
        "content_string": isinstance(content, str),
        "content_nonempty": isinstance(content, str) and bool(content.strip()),
        "content_bounded": isinstance(content, str) and len(content) <= 1_000_000,
    }
    return {"verified": all(checks.values()), "checks": checks}


def evidence_digest(record: dict[str, Any], previous_digest: str = "") -> str:
    """Create a deterministic chain digest without persisting secrets."""
    payload = dict(record)
    payload.pop("evidence_digest", None)
    canonical = json.dumps({"previous_digest": previous_digest, "record": payload}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
