#!/usr/bin/env python3
"""Governed inbound knowledge intake for the AEGIS operations floor.

Active memory stores compact distilled packets. Full source text is kept in the
persistent archive volume and is only loaded when a downstream worker requests it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from mcp.admission import AdmissionController
from mcp.fabric import McpCapabilityFabric

BIND = os.environ.get("AEGIS_KNOWLEDGE_BIND", "127.0.0.1")
PORT = int(os.environ.get("AEGIS_KNOWLEDGE_PORT", "8892"))
TOKEN = os.environ.get("AEGIS_KNOWLEDGE_TOKEN", "")
DATA_ROOT = Path(os.environ.get("AEGIS_KNOWLEDGE_DATA", "/app/knowledge-data"))
ARCHIVE_ROOT = DATA_ROOT / "archive"
STORE_PATH = DATA_ROOT / "knowledge.json"
MAX_BODY = 32 * 1024
REQUEST_TIMEOUT = 20
FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
FIRECRAWL_OAUTH_TOKEN = os.environ.get("FIRECRAWL_OAUTH_TOKEN", "")
FIRECRAWL_MCP_URL = os.environ.get("FIRECRAWL_MCP_URL", "https://mcp.firecrawl.dev/v2/mcp")
WIKI_TOPICS = [item.strip() for item in os.environ.get("AEGIS_KNOWLEDGE_WIKI_TOPICS", "").split(",") if item.strip()]
WEB_SOURCES = [item.strip() for item in os.environ.get("AEGIS_KNOWLEDGE_WEB_SOURCES", "").split(",") if item.strip()]
INTERVAL_MINUTES = max(5, int(os.environ.get("AEGIS_KNOWLEDGE_INTERVAL_MINUTES", "360")))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_text(value: str, limit: int = 1600) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"[#>*_~-]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit].rsplit(" ", 1)[0] + ("…" if len(value) > limit else "")


def distill(markdown: str) -> str:
    paragraphs = [compact_text(part, 500) for part in re.split(r"\n\s*\n", markdown) if part.strip()]
    paragraphs = [part for part in paragraphs if len(part) > 45]
    return compact_text(" ".join(paragraphs[:4]) or markdown, 1600)


def request_json(url: str, *, method: str = "GET", payload: dict | None = None, headers: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"Accept": "application/json", "User-Agent": "AegisKnowledge/1.0 (private control center)", **(headers or {})}
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, method=method, headers=request_headers)
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read(2_000_000).decode("utf-8"))


def wiki_source(query: str) -> dict:
    search_url = "https://en.wikipedia.org/w/api.php?" + urlencode({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": "5",
        "format": "json",
        "utf8": "1",
    })
    result = request_json(search_url)
    hits = result.get("query", {}).get("search", [])
    if not hits:
        raise RuntimeError("Wikipedia returned no matching pages")
    page = hits[0]
    title = str(page.get("title") or query)
    details_url = "https://en.wikipedia.org/w/api.php?" + urlencode({
        "action": "query",
        "prop": "extracts|info",
        "exintro": "1",
        "explaintext": "1",
        "inprop": "url",
        "titles": title,
        "format": "json",
        "redirects": "1",
    })
    details = request_json(details_url)
    pages = details.get("query", {}).get("pages", {})
    page_data = next(iter(pages.values()), {})
    return {
        "title": title,
        "url": page_data.get("fullurl") or "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_")),
        "content": page_data.get("extract") or page.get("snippet") or "",
        "provider": "wikipedia",
    }


class FirecrawlMcpAdapter:
    def __init__(self) -> None:
        self.fabric = McpCapabilityFabric(admission=AdmissionController(max_risk_score=35.0))
        self.ready = False
        self.error: str | None = None

    def ensure(self) -> None:
        if self.ready:
            return
        headers = {}
        credential = FIRECRAWL_OAUTH_TOKEN or FIRECRAWL_KEY
        if credential:
            headers["Authorization"] = f"Bearer {credential}"
        self.fabric.register({
            "id": "mcp.firecrawl",
            "name": "Firecrawl MCP Server",
            "repository": "https://github.com/firecrawl/firecrawl-mcp-server",
            "category": "Research & Web Intelligence",
            "transport": "streamable_http",
            "url": FIRECRAWL_MCP_URL,
            "headers": headers,
        })
        decision = self.fabric.discover("mcp.firecrawl", timeout=25.0)
        if not decision.approved:
            raise RuntimeError(f"Firecrawl MCP rejected by Aegis admission: {', '.join(decision.reasons)}")
        self.ready = True
        self.error = None

    def scrape(self, url: str) -> dict:
        self.ensure()
        result = self.fabric.invoke("mcp.firecrawl", "firecrawl_scrape", {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
        }, timeout=45.0)
        text_items = [item.get("text", "") for item in result.get("content", []) if isinstance(item, dict) and item.get("type") == "text"]
        raw = "\n".join(item for item in text_items if item)
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"markdown": raw}
        content = data.get("markdown") or data.get("content") or raw
        if not content:
            raise RuntimeError("Firecrawl MCP returned no markdown content")
        return {
            "title": data.get("metadata", {}).get("title") or url,
            "url": url,
            "content": content,
            "provider": "firecrawl-mcp",
        }


FIRECRAWL = FirecrawlMcpAdapter()


def firecrawl_source(url: str) -> dict:
    source = FIRECRAWL.scrape(url)
    return {
        "title": source["title"],
        "url": source["url"],
        "content": source["content"],
        "provider": source["provider"],
    }


class KnowledgeStore:
    def __init__(self) -> None:
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.data = self._load()

    def _load(self) -> dict:
        if not STORE_PATH.exists():
            return {"version": 1, "sources": [], "events": []}
        try:
            return json.loads(STORE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "sources": [], "events": []}

    def _save(self) -> None:
        temporary = STORE_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(STORE_PATH)

    def snapshot(self) -> dict:
        with self.lock:
            sources = list(self.data.get("sources", []))
            events = list(self.data.get("events", []))
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent = [event for event in events if _parse_time(event.get("created_at")) >= week_ago]
        total_words = sum(int(source.get("word_count", 0)) for source in sources)
        return {
            "ok": True,
            "configured": bool(TOKEN),
            "providers": {
                "wikipedia": True,
                "firecrawl": bool(FIRECRAWL_MCP_URL),
                "firecrawl_mcp": bool(FIRECRAWL_MCP_URL),
                "firecrawl_authenticated": bool(FIRECRAWL_KEY or FIRECRAWL_OAUTH_TOKEN),
            },
            "metrics": {
                "sources_ingested": len(sources),
                "packets_ready": len(sources),
                "full_sources_archived": len(sources),
                "events_7d": len(recent),
                "words_archived": total_words,
                "active_memory_mode": "distilled_packets",
            },
            "sources": sorted(sources, key=lambda item: item.get("updated_at", ""), reverse=True)[:30],
            "events": sorted(events, key=lambda item: item.get("created_at", ""), reverse=True)[:20],
            "fetchedAt": utc_now(),
            "error": None,
        }

    def ingest(self, kind: str, value: str, manager: str) -> dict:
        if kind == "wiki":
            source = wiki_source(value)
        elif kind == "web":
            source = firecrawl_source(value)
        else:
            raise ValueError("kind must be wiki or web")
        content = str(source["content"])
        source_id = hashlib.sha256(f"{source['provider']}|{source['url']}".encode("utf-8")).hexdigest()[:16]
        archive_path = ARCHIVE_ROOT / f"{source_id}.md"
        archive_path.write_text(content, encoding="utf-8")
        created_at = utc_now()
        packet = {
            "id": source_id,
            "kind": kind,
            "provider": source["provider"],
            "title": str(source["title"]),
            "url": str(source["url"]),
            "manager": manager or ("Scribe" if kind == "wiki" else "Atlas"),
            "summary": distill(content),
            "word_count": len(content.split()),
            "archive_path": str(archive_path.relative_to(DATA_ROOT)),
            "updated_at": created_at,
            "full_source_available": True,
        }
        with self.lock:
            sources = self.data.setdefault("sources", [])
            previous = next((item for item in sources if item.get("id") == source_id), None)
            if previous:
                packet["first_seen"] = previous.get("first_seen", created_at)
                sources[:] = [item for item in sources if item.get("id") != source_id]
            else:
                packet["first_seen"] = created_at
            sources.append(packet)
            self.data.setdefault("events", []).append({
                "type": "source_ingested",
                "source_id": source_id,
                "title": packet["title"],
                "provider": packet["provider"],
                "manager": packet["manager"],
                "created_at": created_at,
            })
            self.data["events"] = self.data["events"][-500:]
            self._save()
        return packet


def _parse_time(value: str | None) -> datetime:
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


STORE = KnowledgeStore()


def authorized(handler: BaseHTTPRequestHandler) -> bool:
    if not TOKEN:
        return False
    header = handler.headers.get("Authorization", "")
    return header.startswith("Bearer ") and header[7:].strip() == TOKEN


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
        if not authorized(self):
            self.send_json(401, {"ok": False, "error": "knowledge service unauthorized"})
            return False
        return True

    def do_GET(self) -> None:
        if not self.guard():
            return
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self.send_json(200, {"ok": True, "service": "aegis-knowledge-runtime", "providers": {"wikipedia": True, "firecrawl": bool(FIRECRAWL_MCP_URL), "firecrawl_authenticated": bool(FIRECRAWL_KEY or FIRECRAWL_OAUTH_TOKEN)}})
        elif path == "/snapshot":
            self.send_json(200, STORE.snapshot())
        elif path.startswith("/source/"):
            source_id = path.rsplit("/", 1)[-1]
            if not re.fullmatch(r"[0-9a-f]{16}", source_id):
                self.send_json(400, {"ok": False, "error": "invalid source id"})
                return
            source_path = ARCHIVE_ROOT / f"{source_id}.md"
            if not source_path.exists():
                self.send_json(404, {"ok": False, "error": "source not found"})
                return
            self.send_json(200, {"ok": True, "id": source_id, "content": source_path.read_text(encoding="utf-8")})
        else:
            self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if not self.guard():
            return
        if self.path.split("?", 1)[0] != "/ingest":
            self.send_json(404, {"ok": False, "error": "not found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_BODY:
                raise ValueError("invalid body size")
            body = json.loads(self.rfile.read(size).decode("utf-8"))
            kind = str(body.get("kind", "wiki")).strip().lower()
            value = str(body.get("query" if kind == "wiki" else "url", "")).strip()
            if not value or len(value) > 2000:
                raise ValueError("query or URL is required")
            packet = STORE.ingest(kind, value, str(body.get("manager", "")).strip())
            self.send_json(200, {"ok": True, "packet": packet, "snapshot": STORE.snapshot()})
        except Exception as error:
            self.send_json(400, {"ok": False, "error": str(error)})


def run_scheduled_intake() -> None:
    for topic in WIKI_TOPICS:
        try:
            STORE.ingest("wiki", topic, "Scribe")
        except Exception:
            continue
    if FIRECRAWL_KEY:
        for url in WEB_SOURCES:
            try:
                STORE.ingest("web", url, "Atlas")
            except Exception:
                continue


def scheduled_intake() -> None:
    run_scheduled_intake()
    while True:
        time.sleep(INTERVAL_MINUTES * 60)
        run_scheduled_intake()


def main() -> None:
    if not TOKEN:
        raise SystemExit("AEGIS_KNOWLEDGE_TOKEN is required")
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    threading.Thread(target=scheduled_intake, daemon=True, name="knowledge-scheduler").start()
    print(f"[*] AEGIS knowledge runtime on {BIND}:{PORT}; interval={INTERVAL_MINUTES}m")
    server.serve_forever()


if __name__ == "__main__":
    main()
