"""Provider adapter for local OpenAI-compatible inference servers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OpenAICompatibleError(RuntimeError):
    """Raised when an OpenAI-compatible local server cannot be used."""


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url: str
    api_key: str | None = None
    timeout: float = 120.0

    @property
    def api_base(self) -> str:
        return self.base_url.rstrip("/") + "/v1"


class OpenAICompatibleProvider:
    """Small dependency-free adapter for local OpenAI-compatible servers."""

    def __init__(self, provider_id: str, config: OpenAICompatibleConfig) -> None:
        self.provider_id = provider_id
        self.config = config

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
            raise OpenAICompatibleError(f"{self.provider_id} request failed: {exc}") from exc
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OpenAICompatibleError(f"{self.provider_id} returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise OpenAICompatibleError(f"{self.provider_id} returned a non-object response")
        return result

    def models(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/models").get("data", [])
        return data if isinstance(data, list) else []

    def chat(self, *, model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": model, "messages": messages}
        payload.update(kwargs)
        return self._request("POST", "/chat/completions", payload)
