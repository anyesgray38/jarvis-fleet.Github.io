"""Shared, admission-gated Firecrawl MCP adapter for AEGIS capabilities."""
from __future__ import annotations

import json
import os
from typing import Any

from .admission import AdmissionController
from .fabric import McpCapabilityFabric


class FirecrawlMcpAdapter:
    """Use the official Firecrawl MCP server through AEGIS's MCP fabric.

    Scraped text is returned as data only. Callers are responsible for treating
    it as untrusted content and must never execute instructions found in it.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        oauth_token: str | None = None,
        api_key: str | None = None,
        max_risk_score: float = 35.0,
    ) -> None:
        self.url = url or os.environ.get("FIRECRAWL_MCP_URL", "https://mcp.firecrawl.dev/v2/mcp")
        self.credential = oauth_token or api_key or os.environ.get("FIRECRAWL_OAUTH_TOKEN", "") or os.environ.get("FIRECRAWL_API_KEY", "") or os.environ.get("FIRECRAWL_AUTHORIZATION", "")
        self.fabric = McpCapabilityFabric(admission=AdmissionController(max_risk_score=max_risk_score))
        self.ready = False
        self.error: str | None = None

    def ensure(self) -> None:
        if self.ready:
            return
        if self.credential.startswith("Bearer "):
            headers = {"Authorization": self.credential}
        else:
            headers = {"Authorization": f"Bearer {self.credential}"} if self.credential else {}
        self.fabric.register({
            "id": "mcp.firecrawl",
            "name": "Firecrawl MCP Server",
            "repository": "https://github.com/firecrawl/firecrawl-mcp-server",
            "category": "Research & Web Intelligence",
            "transport": "streamable_http",
            "url": self.url,
            "headers": headers,
        })
        try:
            decision = self.fabric.discover("mcp.firecrawl", timeout=25.0, allowed_tools=self.ALLOWED_TOOLS)
        except Exception as exc:
            self.error = str(exc)
            raise
        if not decision.approved:
            self.error = f"Firecrawl MCP rejected by Aegis admission: {', '.join(decision.reasons)}"
            raise RuntimeError(self.error)
        self.ready = True
        self.error = None

    def status(self) -> dict[str, Any]:
        return {
            "configured": bool(self.url),
            "admitted": self.ready,
            "authenticated": bool(self.credential),
            "error": self.error,
        }

    def invoke(self, tool: str, arguments: dict[str, Any], *, timeout: float = 45.0) -> dict[str, Any]:
        self.ensure()
        return self.fabric.invoke("mcp.firecrawl", tool, arguments, timeout=timeout)

    @staticmethod
    def _text_payload(result: dict[str, Any]) -> dict[str, Any]:
        text_items = [
            item.get("text", "")
            for item in result.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        raw = "\n".join(item for item in text_items if item)
        structured = result.get("structuredContent") if isinstance(result.get("structuredContent"), dict) else {}
        if result.get("isError") or structured.get("code"):
            message = structured.get("message") or raw or "Firecrawl MCP returned an error"
            raise RuntimeError(f"Firecrawl MCP {structured.get('code', 'error')}: {message}")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"markdown": raw}
        return parsed if isinstance(parsed, dict) else {"data": parsed}

    def scrape(self, url: str, *, formats: list[str] | None = None, only_main_content: bool = True) -> dict[str, Any]:
        result = self.invoke("firecrawl_scrape", {
            "url": url,
            "formats": formats or ["markdown"],
            "onlyMainContent": only_main_content,
        })
        data = self._text_payload(result)
        content = data.get("markdown") or data.get("content") or ""
        if not content and formats and "links" in formats:
            content = data.get("summary") or ""
        if not content:
            raise RuntimeError("Firecrawl MCP returned no page content")
        return {
            "title": data.get("metadata", {}).get("title") or url,
            "url": data.get("metadata", {}).get("url") or url,
            "content": content,
            "links": data.get("links", []),
            "metadata": data.get("metadata", {}),
            "provider": "firecrawl-mcp",
        }

    def search(self, query: str, *, limit: int = 10, location: str | None = None) -> list[dict[str, Any]]:
        arguments: dict[str, Any] = {
            "query": query,
            "limit": max(1, min(100, int(limit))),
            "sources": ["web"],
            "highlights": True,
        }
        if location:
            arguments["location"] = location
        data = self._text_payload(self.invoke("firecrawl_search", arguments))
        rows = data.get("data", {}).get("web", [])
        return [row for row in rows if isinstance(row, dict) and isinstance(row.get("url"), str)]
    ALLOWED_TOOLS = {"firecrawl_search", "firecrawl_scrape"}
