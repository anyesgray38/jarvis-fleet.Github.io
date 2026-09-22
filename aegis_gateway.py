#!/usr/bin/env python3
"""Authenticated local gateway between the AEGIS UI and the private orchestrator."""
from __future__ import annotations
import hmac, json, os
from http.client import RemoteDisconnected
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

TOKEN = os.environ.get("AEGIS_GATEWAY_TOKEN", "")
UPSTREAM = os.environ.get("AEGIS_ORCHESTRATOR_URL", "http://127.0.0.1:8888").rstrip("/") + "/"
BIND = os.environ.get("AEGIS_GATEWAY_BIND", "127.0.0.1")
PORT = int(os.environ.get("AEGIS_GATEWAY_PORT", "8877"))
MAX_BODY = 64 * 1024
TIMEOUT = 8
ALLOWED_GET = {"/health", "/agents", "/jobs"}
ALLOWED_POST_PREFIXES = ("/queue", "/agents/")
ALLOWED_AGENT_ACTIONS = {"/tag", "/pine"}

def _authorized(header: str | None) -> bool:
    if not TOKEN or not header or not header.startswith("Bearer "):
        return False
    supplied = header[7:].strip()
    return bool(supplied) and hmac.compare_digest(supplied, TOKEN)

def _valid_path(method: str, path: str) -> bool:
    if method == "GET":
        return path in ALLOWED_GET
    if method != "POST":
        return False
    if path == "/queue":
        return True
    parts = path.strip("/").split("/")
    return len(parts) == 3 and parts[0] == "agents" and parts[1].isdigit() and ("/" + parts[2]) in ALLOWED_AGENT_ACTIONS

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def _send(self, status: int, payload: dict):
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def _guard(self, path: str, method: str) -> bool:
        if not TOKEN:
            self._send(503, {"ok": False, "error": "gateway token is not configured"})
            return False
        if not _authorized(self.headers.get("Authorization")):
            self._send(401, {"ok": False, "error": "unauthorized"})
            return False
        if not _valid_path(method, path):
            self._send(404, {"ok": False, "error": "not found"})
            return False
        return True
    def _forward(self, method: str, path: str, body: bytes | None = None):
        request = Request(urljoin(UPSTREAM, path.lstrip("/")), data=body, method=method, headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                raw = response.read(MAX_BODY + 1)
                if len(raw) > MAX_BODY:
                    return self._send(502, {"ok": False, "error": "upstream response too large"})
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    payload = {"ok": False, "error": "invalid upstream response"}
                return self._send(response.status, payload)
        except HTTPError as exc:
            try:
                raw = exc.read(MAX_BODY)
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                payload = {"ok": False, "error": f"upstream returned {exc.code}"}
            return self._send(exc.code, payload)
        except (URLError, RemoteDisconnected, TimeoutError, OSError) as exc:
            return self._send(502, {"ok": False, "error": f"orchestrator unavailable: {exc}"})
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if self._guard(path, "GET"):
            self._forward("GET", path)
    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if not self._guard(path, "POST"):
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._send(400, {"ok": False, "error": "invalid content length"})
        if size < 0 or size > MAX_BODY:
            return self._send(413, {"ok": False, "error": "request body too large"})
        body = self.rfile.read(size)
        if size and not body:
            return self._send(400, {"ok": False, "error": "empty request body"})
        self._forward("POST", path, body or b"{}")

def main():
    if not TOKEN:
        raise SystemExit("AEGIS_GATEWAY_TOKEN is required")
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"[*] AEGIS gateway on {BIND}:{PORT} -> {UPSTREAM}")
    server.serve_forever()

if __name__ == "__main__":
    main()
