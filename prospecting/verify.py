"""Build-like and local preview checks for generated static prospecting sites."""
from __future__ import annotations

import http.server
import os
import socket
import subprocess
import threading
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen


class _DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.html = False
        self.title = False
        self.viewport = False
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        self.html = self.html or tag == "html"
        self.title = self.title or tag == "title"
        if tag == "meta" and (attrs_map.get("name") or "").lower() == "viewport":
            self.viewport = True
        if tag == "link" and attrs_map.get("href"):
            self.links.append(attrs_map["href"] or "")


def verify_static_site(project_dir: str | Path) -> dict:
    root = Path(project_dir).resolve()
    required = [root / "index.html", root / "styles.css", root / "script.js", root / "README.md"]
    missing = [str(path.name) for path in required if not path.is_file()]
    if missing:
        return {"status": "FAIL", "checks": {"required_files": False}, "errors": [f"missing files: {', '.join(missing)}"]}
    parser = _DocumentParser()
    parser.feed((root / "index.html").read_text(encoding="utf-8"))
    errors: list[str] = []
    checks = {"required_files": True, "html_document": parser.html, "title": parser.title, "viewport": parser.viewport}
    if not parser.html:
        errors.append("index.html has no html element")
    if not parser.title:
        errors.append("index.html has no title")
    if not parser.viewport:
        errors.append("index.html has no viewport meta tag")
    checks["local_assets"] = all(link in {"styles.css", "script.js"} for link in parser.links if link and not link.startswith("#"))
    if not checks["local_assets"]:
        errors.append("page references an unexpected local asset")
    http_check = _serve_and_fetch(root)
    checks["local_preview"] = http_check["ok"]
    if not http_check["ok"]:
        if http_check.get("error"):
            errors.append(http_check["error"])
    visual = {"status": "NOT_AVAILABLE", "reason": "No Playwright/Chromium or connected browser surface is installed in this runtime."}
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "preview": http_check, "visual_check": visual, "errors": errors}


def _serve_and_fetch(root: Path) -> dict:
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, *_):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        with urlopen(f"http://127.0.0.1:{port}/index.html", timeout=5) as response:
            body = response.read(200_000).decode("utf-8", errors="replace")
            return {"ok": response.status == 200 and "concept-banner" in body, "url": f"http://127.0.0.1:{port}/", "status_code": response.status, "error": None if response.status == 200 else f"preview returned HTTP {response.status}"}
    except Exception as exc:
        return {"ok": False, "url": f"http://127.0.0.1:{port}/", "status_code": None, "error": str(exc)}
    finally:
        server.shutdown()
        server.server_close()
