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
from urllib.parse import parse_qs, quote, urlencode
from urllib.request import Request, urlopen

from knowledge.brain import KnowledgeBrain, load_department_plans
from mcp.firecrawl import FirecrawlMcpAdapter

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
FIRECRAWL_AUTHORIZATION = os.environ.get("FIRECRAWL_AUTHORIZATION", "")
FIRECRAWL_MCP_URL = os.environ.get("FIRECRAWL_MCP_URL", "https://mcp.firecrawl.dev/v2/mcp")
WIKI_TOPICS = [item.strip() for item in os.environ.get("AEGIS_KNOWLEDGE_WIKI_TOPICS", "").split(",") if item.strip()]
WEB_SOURCES = [item.strip() for item in os.environ.get("AEGIS_KNOWLEDGE_WEB_SOURCES", "").split(",") if item.strip()]
INTERVAL_MINUTES = max(5, int(os.environ.get("AEGIS_KNOWLEDGE_INTERVAL_MINUTES", "360")))
RESEARCH_ENABLED = os.environ.get("AEGIS_KNOWLEDGE_RESEARCH_ENABLED", "1").lower() not in {"0", "false", "no", "off"}
MAX_JOBS_PER_CYCLE = max(1, int(os.environ.get("AEGIS_KNOWLEDGE_MAX_JOBS_PER_CYCLE", "4")))
MAX_SEARCH_RESULTS = max(1, int(os.environ.get("AEGIS_KNOWLEDGE_MAX_SEARCH_RESULTS", "3")))
MAX_EXTERNAL_CALLS = max(1, int(os.environ.get("AEGIS_KNOWLEDGE_MAX_EXTERNAL_CALLS", "4")))
SOURCE_REFRESH_MINUTES = max(30, int(os.environ.get("AEGIS_KNOWLEDGE_SOURCE_REFRESH_MINUTES", "1440")))
DEPARTMENTS_CONFIG = os.environ.get("AEGIS_KNOWLEDGE_DEPARTMENTS_CONFIG", str(Path(__file__).resolve().parent / "config" / "knowledge_departments.json"))


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


FIRECRAWL = FirecrawlMcpAdapter(url=FIRECRAWL_MCP_URL, oauth_token=FIRECRAWL_OAUTH_TOKEN, api_key=FIRECRAWL_KEY)


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
                "firecrawl_authenticated": bool(FIRECRAWL_KEY or FIRECRAWL_OAUTH_TOKEN or FIRECRAWL_AUTHORIZATION),
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
            "departments": BRAIN.snapshot()["departments"] if "BRAIN" in globals() else [],
            "research": BRAIN.snapshot()["research"] if "BRAIN" in globals() else {"due_departments": [], "cycles": []},
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
        return self.ingest_source(source, kind=kind, manager=manager, department="web-intelligence", query=value)

    def ingest_source(self, source: dict, *, kind: str, manager: str, department: str, query: str = "") -> dict:
        if not str(source.get("content", "")).strip():
            raise ValueError("source content is empty")
        content = str(source["content"])
        source_id = hashlib.sha256(f"{source['provider']}|{source['url']}".encode("utf-8")).hexdigest()[:16]
        archive_path = ARCHIVE_ROOT / f"{source_id}.md"
        archive_path.write_text(content, encoding="utf-8")
        created_at = utc_now()
        content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
        packet = {
            "id": source_id,
            "kind": kind,
            "provider": source["provider"],
            "title": str(source["title"]),
            "url": str(source["url"]),
            "manager": manager or ("Scribe" if kind == "wiki" else "Atlas"),
            "department": department or "web-intelligence",
            "research_query": query,
            "summary": distill(content),
            "word_count": len(content.split()),
            "content_hash": content_hash,
            "archive_path": str(archive_path.relative_to(DATA_ROOT)),
            "updated_at": created_at,
            "full_source_available": True,
        }
        with self.lock:
            sources = self.data.setdefault("sources", [])
            previous = next((item for item in sources if item.get("id") == source_id), None)
            changed = bool(previous and previous.get("content_hash") != content_hash)
            if previous:
                packet["first_seen"] = previous.get("first_seen", created_at)
                packet["version"] = int(previous.get("version", 1)) + (1 if changed else 0)
                sources[:] = [item for item in sources if item.get("id") != source_id]
            else:
                packet["first_seen"] = created_at
                packet["version"] = 1
            sources.append(packet)
            if not previous or changed:
                self.data.setdefault("events", []).append({
                    "type": "source_changed" if previous else "source_ingested",
                    "source_id": source_id,
                    "title": packet["title"],
                    "provider": packet["provider"],
                    "manager": packet["manager"],
                    "department": packet["department"],
                    "version": packet["version"],
                    "created_at": created_at,
                })
            self.data["events"] = self.data["events"][-500:]
            self._save()
        return packet

    def search(self, query: str, *, department: str = "", limit: int = 8, include_content: bool = False) -> list[dict]:
        """Search active local packets; full archives are opt-in and bounded."""
        terms = {term.lower() for term in re.findall(r"[a-z0-9]{3,}", query.lower())}
        if not terms:
            return []
        with self.lock:
            candidates = list(self.data.get("sources", []))
        ranked: list[tuple[int, dict]] = []
        for source in candidates:
            if department and source.get("department") != department:
                continue
            haystack = " ".join(str(source.get(key, "")) for key in ("title", "summary", "research_query", "department")).lower()
            score = sum(1 for term in terms if term in haystack)
            if not score:
                continue
            item = dict(source)
            item["relevance"] = score
            if include_content:
                archive = DATA_ROOT / str(source.get("archive_path", ""))
                if archive.resolve().is_relative_to(DATA_ROOT.resolve()) and archive.exists():
                    item["content"] = archive.read_text(encoding="utf-8")[:200_000]
            ranked.append((score, item))
        ranked.sort(key=lambda pair: (pair[0], pair[1].get("updated_at", "")), reverse=True)
        return [item for _, item in ranked[: max(1, min(50, int(limit)))]]

    def source_is_fresh(self, url: str, refresh_minutes: int) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(30, int(refresh_minutes)))
        with self.lock:
            source = next((item for item in self.data.get("sources", []) if item.get("url") == url), None)
        return bool(source and _parse_time(source.get("updated_at")) >= cutoff)

    def cached_search(self, query: str, ttl_minutes: int) -> list[dict] | None:
        with self.lock:
            item = self.data.setdefault("research", {}).setdefault("search_cache", {}).get(query)
        if not isinstance(item, dict) or _parse_time(item.get("cached_at")) < datetime.now(timezone.utc) - timedelta(minutes=max(30, int(ttl_minutes))):
            return None
        hits = item.get("hits", [])
        return hits if isinstance(hits, list) else None

    def cache_search(self, query: str, hits: list[dict]) -> None:
        if not hits:
            return
        with self.lock:
            research = self.data.setdefault("research", {})
            cache = research.setdefault("search_cache", {})
            cache[query] = {"cached_at": utc_now(), "hits": [hit for hit in hits if isinstance(hit, dict)][:20]}
            if len(cache) > 200:
                for key in sorted(cache, key=lambda value: cache[value].get("cached_at", ""))[:-200]:
                    cache.pop(key, None)
            self._save()


def _parse_time(value: str | None) -> datetime:
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


STORE = KnowledgeStore()
PLANS = load_department_plans(DEPARTMENTS_CONFIG, wiki_topics=WIKI_TOPICS, web_sources=WEB_SOURCES)


def search_firecrawl(query: str, limit: int) -> list[dict]:
    return FIRECRAWL.search(query, limit=limit)


BRAIN = KnowledgeBrain(
    STORE,
    plans=PLANS,
    wiki_fetcher=wiki_source,
    web_fetcher=firecrawl_source,
    web_searcher=search_firecrawl,
    max_jobs_per_cycle=MAX_JOBS_PER_CYCLE,
    max_search_results=MAX_SEARCH_RESULTS,
    max_external_calls=MAX_EXTERNAL_CALLS,
    source_refresh_minutes=SOURCE_REFRESH_MINUTES,
)


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
        path, _, query = self.path.partition("?")
        if path == "/health":
            provider_status = FIRECRAWL.status()
            if "deep=1" in query.split("&") and FIRECRAWL_MCP_URL:
                try:
                    FIRECRAWL.ensure()
                except Exception:
                    pass
                provider_status = FIRECRAWL.status()
            self.send_json(200, {"ok": True, "service": "aegis-knowledge-runtime", "providers": {"wikipedia": True, "firecrawl": bool(FIRECRAWL_MCP_URL), "firecrawl_authenticated": bool(FIRECRAWL_KEY or FIRECRAWL_OAUTH_TOKEN or FIRECRAWL_AUTHORIZATION)}, "firecrawl_mcp": provider_status, "research": {"enabled": RESEARCH_ENABLED, "interval_minutes": INTERVAL_MINUTES, "due_departments": BRAIN.due_departments()}})
        elif path == "/snapshot":
            self.send_json(200, STORE.snapshot())
        elif path == "/search":
            params = {key: values[-1] for key, values in parse_qs(query, keep_blank_values=True).items()}
            search_query = params.get("q", "").strip()
            if not search_query or len(search_query) > 500:
                self.send_json(400, {"ok": False, "error": "q is required and must be <= 500 characters"})
                return
            try:
                limit = int(params.get("limit", "8"))
            except ValueError:
                limit = 8
            include_content = params.get("full", "0").lower() in {"1", "true", "yes"}
            self.send_json(200, {"ok": True, "query": search_query, "department": params.get("department", ""), "results": STORE.search(search_query, department=params.get("department", ""), limit=limit, include_content=include_content)})
        elif path == "/departments":
            self.send_json(200, {"ok": True, **BRAIN.snapshot()})
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
        path = self.path.split("?", 1)[0]
        if path not in {"/ingest", "/research"}:
            self.send_json(404, {"ok": False, "error": "not found"})
            return
        if path == "/research":
            try:
                body = json.loads(self.rfile.read(min(MAX_BODY, int(self.headers.get("Content-Length", "0")))).decode("utf-8") or "{}")
                result = BRAIN.run_due_cycle(force=bool(body.get("force", False))) if RESEARCH_ENABLED else {"status": "disabled", "jobs": 0, "packets": 0, "errors": []}
                self.send_json(200, {"ok": result.get("status") in {"ok", "degraded", "already_running", "disabled"}, "result": result, "snapshot": STORE.snapshot()})
            except Exception as error:
                self.send_json(400, {"ok": False, "error": str(error)})
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
    if not RESEARCH_ENABLED:
        return
    BRAIN.run_due_cycle()


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
