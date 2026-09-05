#!/usr/bin/env python3
"""Small loopback-only HTTP facade for the governed AEGIS model runtime."""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from jarvis.model_service import ModelRuntime


class Handler(BaseHTTPRequestHandler):
    runtime = ModelRuntime()

    def log_message(self, *_):
        pass

    def _send(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"ok": True, "service": "aegis-model-runtime"})
        return self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if self.path != "/chat":
            return self._send(404, {"ok": False, "error": "not found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 1_000_000:
                return self._send(400, {"ok": False, "error": "invalid request size"})
            body = json.loads(self.rfile.read(size))
            result = self.runtime.chat(
                messages=body.get("messages", []),
                purpose=body.get("purpose", "general"),
                required_tags=set(body.get("required_tags", [])),
                modality=body.get("modality", "text"),
                preferred_provider=body.get("preferred_provider"),
                local_only=body.get("local_only", True),
                allow_external=body.get("allow_external", False),
                metadata=body.get("metadata") or {},
                temperature=body.get("temperature"),
                max_tokens=body.get("max_tokens"),
            )
            return self._send(200, result)
        except (ValueError, LookupError) as exc:
            return self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            return self._send(502, {"ok": False, "error": f"model runtime failure: {exc}"})


if __name__ == "__main__":
    host = os.getenv("AEGIS_MODEL_BIND", "127.0.0.1")
    port = int(os.getenv("AEGIS_MODEL_PORT", "8891"))
    ThreadingHTTPServer((host, port), Handler).serve_forever()
