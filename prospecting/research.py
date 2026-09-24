"""Business website and social research with explicit uncertainty states."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from mcp.firecrawl import FirecrawlMcpAdapter

from .models import BusinessRecord, Evidence, ScanRequest, now
from .normalize import is_directory, is_social
from .scoring import score_business
from .website_audit import audit_social, audit_website


class BusinessResearcher:
    def __init__(self, client: FirecrawlMcpAdapter | None = None) -> None:
        self.client = client or FirecrawlMcpAdapter()

    def research(self, record: BusinessRecord, request: ScanRequest) -> BusinessRecord:
        record.status = "researching"
        record.research_timestamp = now()
        search_rows: list[dict[str, Any]] = []
        queries = [
            f'"{record.business_name}" "{record.address}" official website',
            f'"{record.business_name}" "{record.phone}"',
        ]
        for query in queries:
            try:
                rows = self.client.search(query, limit=10)
                search_rows.extend(rows)
                record.evidence.append(Evidence(source="Firecrawl web search", observation=f"Ran public website discovery query: {query}", interpretation="Search results are candidates, not proof of ownership.", confidence="medium", data={"result_count": len(rows)}).to_dict())
            except Exception as exc:
                record.evidence.append(Evidence(source="Firecrawl web search", observation=f"Search query failed: {query}", interpretation="Website state remains uncertain because a research source failed.", confidence="low", data={"error": str(exc)}).to_dict())

        if not record.website:
            record.website = self._select_official_candidate(record, search_rows)
        if record.website:
            try:
                record.website_audit = audit_website(record.website, business=record)
                record.website_state = "CONFIRMED" if record.website_audit.get("reachable") else "LIKELY"
                record.evidence.extend(record.website_audit.get("evidence", []))
            except Exception as exc:
                record.website_state = "LIKELY"
                record.website_audit = {"audited_at": now(), "url": record.website, "reachable": False, "findings": [f"Website audit failed: {exc}"], "evidence": []}
        else:
            # An empty or rate-limited search is not evidence of absence. Only
            # use NOT_FOUND when public search returned corroborating rows but
            # no official domain candidate; otherwise preserve UNKNOWN.
            record.website_state = "NOT_FOUND" if record.discovery_sources and search_rows else "UNKNOWN"
            record.website_audit = {"audited_at": now(), "status": "not_found" if record.website_state == "NOT_FOUND" else "unknown", "findings": ["No official domain was identified in the bounded public searches; this is not proof that no website exists."], "evidence": []}

        record.social_audit = audit_social(self.client, record)
        record.social_profiles = record.social_audit.get("profiles", [])
        if record.social_audit.get("evidence"):
            record.evidence.extend(record.social_audit["evidence"])
        score_business(record)
        record.research_history.append({"timestamp": record.research_timestamp, "website": record.website, "website_state": record.website_state, "classification": record.classification, "opportunity_score": record.opportunity_score})
        record.status = "researched"
        return record

    @staticmethod
    def _select_official_candidate(record: BusinessRecord, rows: list[dict[str, Any]]) -> str:
        name_tokens = {token for token in record.business_name.lower().split() if len(token) > 2}
        for row in rows:
            url = str(row.get("url", ""))
            if not url or is_directory(url) or is_social(url):
                continue
            text = f"{row.get('title', '')} {row.get('description', '')}".lower()
            overlap = sum(1 for token in name_tokens if token in text or token in url.lower())
            if overlap >= max(1, min(2, len(name_tokens))):
                return url
        return ""
