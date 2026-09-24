#!/usr/bin/env python3
"""Authenticated HTTP runtime for the AEGIS business prospecting capability."""
from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from mcp.firecrawl import FirecrawlMcpAdapter
from prospecting.models import ScanRequest
from prospecting.store import ProspectStore
from prospecting.workflow import BusinessProspectingAgent
from prospecting.web import ResilientWebResearch


BIND = os.environ.get("AEGIS_PROSPECT_BIND", "127.0.0.1")
PORT = int(os.environ.get("AEGIS_PROSPECT_PORT", "8893"))
TOKEN = os.environ.get("AEGIS_PROSPECT_TOKEN", "")
DB = os.environ.get("AEGIS_PROSPECT_DB", "/app/prospect-data/prospects.db")
MAX_BODY = 64 * 1024
STORE = ProspectStore(DB)
FIRECRAWL = FirecrawlMcpAdapter()
AGENT = BusinessProspectingAgent(store=STORE, firecrawl=FIRECRAWL)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        supplied = header[7:].strip() if header.startswith("Bearer ") else ""
        return bool(TOKEN and supplied and hmac.compare_digest(supplied, TOKEN))

    def guard(self) -> bool:
        if not TOKEN:
            self.send_json(503, {"ok": False, "error": "prospecting token is not configured"})
            return False
        if not self.authorized():
            self.send_json(401, {"ok": False, "error": "prospecting service unauthorized"})
            return False
        return True

    def body(self) -> dict:
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        if size <= 0 or size > MAX_BODY:
            raise ValueError("invalid body size")
        payload = json.loads(self.rfile.read(size).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("request body must be an object")
        return payload

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/health":
            self.send_json(200, {"ok": True, "service": "aegis-prospecting-runtime", "research": AGENT.discovery.researcher.status() if hasattr(AGENT.discovery, "researcher") else {"primary": FIRECRAWL.status()}, "database": str(STORE.path)})
            return
        if not self.guard():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/scans":
            self.send_json(200, {"ok": True, "scans": STORE.list_scans(int(parse_qs(parsed.query).get("limit", [20])[0]))})
        elif parsed.path == "/businesses":
            values = parse_qs(parsed.query)
            self.send_json(200, {"ok": True, "businesses": [item.to_dict() for item in STORE.list_businesses(min_score=int(values.get("min_score", [0])[0]), limit=int(values.get("limit", [100])[0]))]})
        elif parsed.path.startswith("/scan/"):
            result = STORE.get_scan(parsed.path.rsplit("/", 1)[-1])
            self.send_json(200 if result else 404, {"ok": bool(result), "scan": result} if result else {"ok": False, "error": "scan not found"})
        elif parsed.path.startswith("/business/"):
            business = STORE.get_business(parsed.path.rsplit("/", 1)[-1])
            self.send_json(200 if business else 404, {"ok": bool(business), "business": business.to_dict() if business else None} if business else {"ok": False, "error": "business not found"})
        else:
            self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if not self.guard():
            return
        path = self.path.split("?", 1)[0]
        try:
            body = self.body()
            if path == "/scan":
                target = str(body.get("target", "")).strip()
                if not target or len(target) > 500:
                    raise ValueError("target is required and must be <= 500 characters")
                raw_sources = body.get("source_urls", [])
                source_urls = tuple(str(item).strip() for item in raw_sources if isinstance(item, str) and str(item).strip()) if isinstance(raw_sources, list) else tuple(item.strip() for item in os.environ.get("AEGIS_PROSPECT_SOURCE_URLS", "").split(",") if item.strip())
                request = ScanRequest(target=target, category=str(body.get("category", "")).strip(), radius_miles=float(body["radius_miles"]) if body.get("radius_miles") is not None else None, max_results=max(1, min(100, int(body.get("max_results", 30)))), generate_limit=max(0, min(10, int(body.get("generate_limit", 0)))), output_root=str(body.get("output_root", "/app/prospect-data/demos")), source_urls=source_urls)
                result = AGENT.scan(request)
                self.send_json(200, {"ok": True, "result": result.to_dict()})
            elif path.startswith("/business/") and path.endswith("/research"):
                business_id = path.split("/")[2]
                result = AGENT.research_business(business_id)
                self.send_json(200, {"ok": True, "business": result.to_dict()})
            elif path.startswith("/business/") and path.endswith("/demo"):
                business_id = path.split("/")[2]
                result = AGENT.generate_business_demo(business_id, output_root=str(body.get("output_root", "/app/prospect-data/demos")))
                self.send_json(200, {"ok": True, "result": result})
            else:
                self.send_json(404, {"ok": False, "error": "not found"})
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})


def main() -> None:
    if not TOKEN:
        raise SystemExit("AEGIS_PROSPECT_TOKEN is required")
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"[*] AEGIS prospecting runtime on {BIND}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
