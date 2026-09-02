"""Context-budget aware storage for large MCP tool results."""
from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResultEnvelope:
    inline: Any | None
    handle: str | None
    sha256: str
    serialized_bytes: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "inline": self.inline,
            "handle": self.handle,
            "sha256": self.sha256,
            "serialized_bytes": self.serialized_bytes,
            "truncated": self.truncated,
        }


class MCPResultStore:
    """Keep full results private while returning only a bounded model payload."""

    def __init__(self, *, max_inline_chars: int = 12000):
        if max_inline_chars < 256:
            raise ValueError("max_inline_chars must be >= 256")
        self.max_inline_chars = max_inline_chars
        self._results: dict[str, str] = {}

    def envelope(self, result: Any) -> ResultEnvelope:
        serialized = json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        if len(serialized) <= self.max_inline_chars:
            return ResultEnvelope(result, None, digest, len(serialized.encode("utf-8")), False)
        handle = secrets.token_urlsafe(18)
        self._results[handle] = serialized
        preview = serialized[: self.max_inline_chars]
        return ResultEnvelope(preview, handle, digest, len(serialized.encode("utf-8")), True)

    def read_more(self, handle: str, *, offset: int = 0, length: int | None = None) -> str:
        if handle not in self._results:
            raise KeyError("unknown result handle")
        if offset < 0:
            raise ValueError("offset must be >= 0")
        value = self._results[handle]
        return value[offset:] if length is None else value[offset : offset + max(0, length)]

    def discard(self, handle: str) -> None:
        self._results.pop(handle, None)
