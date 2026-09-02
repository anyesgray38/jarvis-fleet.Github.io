"""LocalAI inference provider for AEGIS.

LocalAI is an infrastructure provider, not the AEGIS cognitive core.  The
adapter intentionally speaks the OpenAI-compatible HTTP surface so AEGIS can
route to local inference without coupling the control plane to LocalAI's
internal implementation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LocalAIError(RuntimeError):
    """Raised when a LocalAI request cannot be completed or decoded."""


@dataclass(frozen=True)
class LocalAIConfig:
    base_url: str = "http://127.0.0.1:8080"
    api_key: str | None = None
    timeout: float = 60.0

    @property
    def api_base(self) -> str:
        return self.base_url.rstrip("/") + "/v1"


class LocalAIProvider:
    """Small, dependency-free adapter around LocalAI's OpenAI-compatible API."""

    provider_id = "localai"

    def __init__(self, config: LocalAIConfig | None = None) -> None:
        self.config = config or LocalAIConfig()

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        request = Request(self.config.api_base + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.config.timeout) as response:
                raw = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise LocalAIError(f"LocalAI request failed: {exc}") from exc

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LocalAIError("LocalAI returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise LocalAIError("LocalAI returned a non-object response")
        return result

    def health(self) -> dict[str, Any]:
        """Return model inventory; a successful response is the provider health signal."""
        return self._request("GET", "/models")

    def models(self) -> list[dict[str, Any]]:
        """List models exposed by the LocalAI instance."""
        data = self.health().get("data", [])
        return data if isinstance(data, list) else []

    def chat(self, *, model: str, messages: list[dict[str, str]], temperature: float | None = None,
             max_tokens: int | None = None) -> dict[str, Any]:
        """Run a chat completion and return the provider response unchanged."""
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        return self._request("POST", "/chat/completions", payload)
