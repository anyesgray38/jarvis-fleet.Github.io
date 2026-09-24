"""Resilient public research transport: admitted Firecrawl first, HTTP fallback second."""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from mcp.firecrawl import FirecrawlMcpAdapter

from .website_audit import PageParser, fetch_html


class _SearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key: value or "" for key, value in attrs}
        classes = set(data.get("class", "").split())
        if tag == "a" and "result__a" in classes:
            self._current = {"url": data.get("href", ""), "title": "", "description": ""}
            self._capture = "title"
        elif self._current and "result__snippet" in classes:
            self._capture = "description"

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current:
            if self._current.get("url") and self._current.get("title"):
                self.rows.append(self._current)
            self._current = None
            self._capture = ""

    def handle_data(self, data: str) -> None:
        if self._current and self._capture:
            self._current[self._capture] += " ".join(data.split())


class HttpSearchFallback:
    """Small dependency-free fallback for public search when an MCP quota is unavailable."""

    def search(self, query: str, *, limit: int = 10, location: str | None = None) -> list[dict[str, str]]:
        full_query = f"{query} {location}" if location else query
        request = Request(f"https://html.duckduckgo.com/html/?q={quote(full_query)}", headers={"User-Agent": "AEGIS public prospect research/1.0"})
        with urlopen(request, timeout=15) as response:
            markup = response.read(1_500_000).decode("utf-8", errors="replace")
        parser = _SearchParser()
        parser.feed(markup)
        return parser.rows[: max(1, min(100, limit))]

    def scrape(self, url: str, *, formats: list[str] | None = None, only_main_content: bool = True) -> dict:
        observed = fetch_html(url)
        if not observed.get("html"):
            raise RuntimeError(observed.get("error") or "HTTP fallback returned no HTML")
        parser = PageParser()
        parser.feed(observed["html"])
        return {"title": parser.title or url, "url": observed.get("final_url") or url, "content": "\n".join(parser.text_parts), "links": parser.links, "metadata": {"title": parser.title, "statusCode": observed.get("status_code")}, "provider": "direct-http"}


class ResilientWebResearch:
    def __init__(self, primary: FirecrawlMcpAdapter | None = None) -> None:
        self.primary = primary or FirecrawlMcpAdapter()
        self.fallback = HttpSearchFallback()
        self.last_transport = "none"
        self.last_error: str | None = None

    def search(self, query: str, *, limit: int = 10, location: str | None = None) -> list[dict]:
        try:
            rows = self.primary.search(query, limit=limit, location=location)
            self.last_transport = "firecrawl-mcp"
            self.last_error = None
            return rows
        except Exception as primary_error:
            self.last_error = str(primary_error)
            try:
                rows = self.fallback.search(query, limit=limit, location=location)
                self.last_transport = "direct-http-search"
                return rows
            except Exception as fallback_error:
                raise RuntimeError(f"research search failed via Firecrawl MCP and HTTP fallback: {primary_error}; fallback: {fallback_error}") from fallback_error

    def scrape(self, url: str, *, formats: list[str] | None = None, only_main_content: bool = True) -> dict:
        try:
            result = self.primary.scrape(url, formats=formats, only_main_content=only_main_content)
            self.last_transport = "firecrawl-mcp"
            self.last_error = None
            return result
        except Exception as primary_error:
            self.last_error = str(primary_error)
            try:
                result = self.fallback.scrape(url, formats=formats, only_main_content=only_main_content)
                self.last_transport = "direct-http"
                return result
            except Exception as fallback_error:
                raise RuntimeError(f"research scrape failed via Firecrawl MCP and HTTP fallback: {primary_error}; fallback: {fallback_error}") from fallback_error

    def status(self) -> dict:
        return {"primary": self.primary.status(), "last_transport": self.last_transport, "last_error": self.last_error, "fallback": "direct-http"}
