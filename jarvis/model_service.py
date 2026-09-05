"""Governed AEGIS model runtime service.

ModelFabric performs admission/routing. This service validates requests, normalizes
provider responses, runs independent deterministic checks, and appends chained evidence.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from providers.model_fabric import ModelFabric
from providers.routing_policy import RoutingRequest
from jarvis.verification import evidence_digest, verify_inference_response

ROOT = Path(__file__).resolve().parents[1]
MODEL_REGISTRY = ROOT / "capabilities" / "models.json"
PROVIDER_REGISTRY = ROOT / "capabilities" / "providers.json"
EVIDENCE_DIR = ROOT / "evidence"
EVIDENCE_FILE = EVIDENCE_DIR / "inference.jsonl"

class ModelRuntime:
    def __init__(self, *, localai_url: str | None = None, lmstudio_url: str | None = None, timeout: float = 120.0):
        self.fabric = ModelFabric.from_files(
            model_registry_path=MODEL_REGISTRY,
            provider_registry_path=PROVIDER_REGISTRY,
            localai_url=localai_url or os.getenv("AEGIS_LOCALAI_URL", "http://127.0.0.1:8080"),
            lmstudio_url=lmstudio_url or os.getenv("AEGIS_LMSTUDIO_URL", "http://127.0.0.1:1234"),
            timeout=timeout,
        )

    def chat(self, *, messages: list[dict[str, str]], purpose: str = "general", required_tags: set[str] | None = None, modality: str = "text", preferred_provider: str | None = None, local_only: bool = True, allow_external: bool = False, metadata: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        if not messages or not all(isinstance(m, dict) and isinstance(m.get("role"), str) and isinstance(m.get("content"), str) for m in messages):
            raise ValueError("messages must be a non-empty list of role/content objects")
        if len(messages) > 100 or sum(len(m["content"]) for m in messages) > 200_000:
            raise ValueError("message content exceeds limit")
        request_id = uuid.uuid4().hex
        started = time.monotonic()
        request = RoutingRequest(required_tags=frozenset(required_tags or set()), modality=modality, preferred_provider=preferred_provider, local_only=local_only, allow_external=allow_external, purpose=purpose, metadata=metadata or {})
        route = self.fabric.resolve(request=request)
        result = self.fabric.chat(route, messages=messages, **kwargs)
        elapsed_ms = round((time.monotonic() - started) * 1000, 2)
        normalized = self._normalize(result)
        verification = verify_inference_response(normalized)
        evidence = {
            "schema": "aegis.inference.v2",
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "purpose": purpose,
            "route": {"provider": route.provider, "model": route.model, "reason": route.reason, "score": route.score, "constraints": route.constraints},
            "timing_ms": elapsed_ms,
            "response": normalized,
            "verification": verification,
        }
        previous = self._last_digest()
        evidence["previous_digest"] = previous
        evidence["evidence_digest"] = evidence_digest(evidence, previous)
        self._write_evidence(evidence)
        if not verification["verified"]:
            raise ValueError("independent response verification failed")
        return {"ok": True, "request_id": request_id, "route": evidence["route"], "timing_ms": elapsed_ms, "response": normalized, "verification": verification}

    @staticmethod
    def _normalize(result: dict[str, Any]) -> dict[str, Any]:
        choices = result.get("choices") if isinstance(result, dict) else None
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return {"content": message["content"], "finish_reason": choices[0].get("finish_reason"), "usage": result.get("usage")}
        if isinstance(result, dict) and isinstance(result.get("content"), str):
            return {"content": result["content"], "usage": result.get("usage")}
        raise ValueError("provider returned an unsupported response shape")

    @staticmethod
    def _last_digest() -> str:
        if not EVIDENCE_FILE.exists():
            return ""
        try:
            last = ""
            with EVIDENCE_FILE.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        item = json.loads(line)
                        last = item.get("evidence_digest", last)
            return last
        except (OSError, ValueError, json.JSONDecodeError):
            return ""

    @staticmethod
    def _write_evidence(record: dict[str, Any]) -> None:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        with EVIDENCE_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
