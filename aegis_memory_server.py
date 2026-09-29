#!/usr/bin/env python3
"""Authenticated AEGIS memory facade backed by self-hosted Hindsight."""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from knowledge.hindsight import HindsightClient, HindsightError

BIND = os.environ.get("AEGIS_MEMORY_BIND", "127.0.0.1")
PORT = int(os.environ.get("AEGIS_MEMORY_PORT", "8894"))
TOKEN = os.environ.get("AEGIS_MEMORY_TOKEN", "")
HINDSIGHT_URL = os.environ.get("AEGIS_HINDSIGHT_URL", "http://127.0.0.1:8895")
HINDSIGHT_API_KEY = os.environ.get("AEGIS_HINDSIGHT_API_KEY", "")
DEFAULT_BANK = os.environ.get("AEGIS_MEMORY_DEFAULT_BANK", "aegis-core")
MAX_BODY = 256 * 1024
CLIENT = HindsightClient(HINDSIGHT_URL, api_key=HINDSIGHT_API_KEY)


def authorized(handler: BaseHTTPRequestHandler) -> bool:
    header = handler.headers.get("Authorization", "")
    return bool(TOKEN) and header.startswith("Bearer ") and header[7:].strip() == TOKEN


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def guard(self) -> bool:
        if authorized(self):
            return True
        self.send_json(401, {"ok": False, "error": "memory service unauthorized"})
        return False

    def read_body(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        if size <= 0 or size > MAX_BODY:
            raise ValueError("invalid body size")
        value = json.loads(self.rfile.read(size).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        return value

    def do_GET(self) -> None:
        if not self.guard():
            return
        path = self.path.split("?", 1)[0]
        if path == "/health":
            try:
                upstream = CLIENT.ready()
                self.send_json(200, {"ok": True, "service": "aegis-memory-runtime", "backend": "hindsight", "upstream": upstream})
            except HindsightError as exc:
                self.send_json(503, {"ok": False, "service": "aegis-memory-runtime", "backend": "hindsight", "error": str(exc)})
        elif path == "/mcp":
            bank = DEFAULT_BANK
            self.send_json(200, {"ok": True, "bank_id": bank, "mcp_url": CLIENT.mcp_url(bank)})
        else:
            self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if not self.guard():
            return
        path = self.path.split("?", 1)[0]
        if path not in {"/retain", "/recall", "/reflect"}:
            self.send_json(404, {"ok": False, "error": "not found"})
            return
        try:
            body = self.read_body()
            bank = str(body.get("bank_id") or DEFAULT_BANK).strip()
            if path == "/retain":
                content = str(body.get("content", ""))
                result = CLIENT.retain(
                    bank,
                    content,
                    context=str(body.get("context", "")),
                    document_id=str(body.get("document_id", "")),
                    timestamp=str(body.get("timestamp", "")),
                    asynchronous=bool(body.get("async", True)),
                )
            elif path == "/recall":
                max_tokens = body.get("max_tokens")
                result = CLIENT.recall(bank, str(body.get("query", "")), max_tokens=int(max_tokens) if max_tokens is not None else None)
            else:
                result = CLIENT.reflect(bank, str(body.get("query", "")))
            self.send_json(200, {"ok": True, "bank_id": bank, "result": result})
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
        except HindsightError as exc:
            self.send_json(502, {"ok": False, "error": str(exc)})


def main() -> None:
    if not TOKEN:
        raise SystemExit("AEGIS_MEMORY_TOKEN is required")
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"[*] AEGIS memory runtime on {BIND}:{PORT}; backend={HINDSIGHT_URL}")
    server.serve_forever()


if __name__ == "__main__":
    main()
