"""Native Ollama provider for governed local inference."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    """Raised when the local Ollama service cannot be used."""


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str
    timeout: float = 120.0

    @property
    def api_base(self) -> str:
        return self.base_url.rstrip("/") + "/api"


class OllamaProvider:
    """Dependency-free adapter for Ollama's native local API."""

    provider_id = "ollama"

    def __init__(self, config: OllamaConfig) -> None:
        self.config = config

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.config.api_base + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.config.timeout) as response:
                raw = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise OllamaError(f"ollama request failed: {exc}") from exc
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaError("ollama returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise OllamaError("ollama returned a non-object response")
        return result

    def models(self) -> list[dict[str, Any]]:
        models = self._request("GET", "/tags").get("models", [])
        if not isinstance(models, list):
            return []
        return [{"id": item["name"]} for item in models if isinstance(item, dict) and isinstance(item.get("name"), str)]

    def chat(self, *, model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if isinstance(kwargs.get("temperature"), (int, float)):
            options["temperature"] = kwargs["temperature"]
        if isinstance(kwargs.get("max_tokens"), int):
            options["num_predict"] = kwargs["max_tokens"]
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
        }
        if options:
            payload["options"] = options
        result = self._request("POST", "/chat", payload)
        message = result.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return {"content": message["content"], "done": result.get("done"), "usage": result.get("eval_count")}
        raise OllamaError("ollama returned an unsupported chat response shape")
