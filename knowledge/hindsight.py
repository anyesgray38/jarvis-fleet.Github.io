"""Small dependency-free client for a self-hosted Hindsight memory server."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


class HindsightError(RuntimeError):
    pass


class HindsightClient:
    def __init__(self, base_url: str, *, api_key: str = "", timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.timeout = timeout

    def _request(self, path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Accept": "application/json", "User-Agent": "AEGIS-Memory/1.0"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(f"{self.base_url}{path}", data=data, method=method, headers=headers)
        try:
            with urlopen(req, timeout=self.timeout) as response:
                body = response.read(4_000_000)
        except Exception as exc:
            raise HindsightError(f"Hindsight request failed: {exc}") from exc
        if not body:
            return {}
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HindsightError("Hindsight returned invalid JSON") from exc
        return value if isinstance(value, dict) else {"result": value}

    @staticmethod
    def _bank(bank_id: str) -> str:
        bank = bank_id.strip()
        if not bank or len(bank) > 128:
            raise ValueError("bank_id is required and must be <= 128 characters")
        return quote(bank, safe="-_.")

    def ready(self) -> dict[str, Any]:
        return self._request("/health/ready")

    def retain(self, bank_id: str, content: str, *, context: str = "", document_id: str = "", timestamp: str = "", asynchronous: bool = True) -> dict[str, Any]:
        if not content.strip():
            raise ValueError("content is required")
        item: dict[str, Any] = {"content": content}
        if context:
            item["context"] = context
        if document_id:
            item["document_id"] = document_id
        if timestamp:
            item["timestamp"] = timestamp
        return self._request(
            f"/v1/default/banks/{self._bank(bank_id)}/memories",
            method="POST",
            payload={"async": bool(asynchronous), "items": [item]},
        )

    def recall(self, bank_id: str, query: str, *, max_tokens: int | None = None) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("query is required")
        payload: dict[str, Any] = {"query": query}
        if max_tokens is not None:
            payload["max_tokens"] = max(64, min(32768, int(max_tokens)))
        return self._request(
            f"/v1/default/banks/{self._bank(bank_id)}/memories/recall",
            method="POST",
            payload=payload,
        )

    def reflect(self, bank_id: str, query: str) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("query is required")
        return self._request(
            f"/v1/default/banks/{self._bank(bank_id)}/reflect",
            method="POST",
            payload={"query": query},
        )

    def mcp_url(self, bank_id: str) -> str:
        return f"{self.base_url}/mcp/{self._bank(bank_id)}/"
