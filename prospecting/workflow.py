"""End-to-end governed business prospecting workflow."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.firecrawl import FirecrawlMcpAdapter

from .discovery import BusinessDiscovery
from .generator import generate_demo
from .models import BusinessRecord, ScanRequest, ScanResult, now
from .research import BusinessResearcher
from .store import ProspectStore
from .verify import verify_static_site
from .web import ResilientWebResearch


class BusinessProspectingAgent:
    """Discover, research, score, persist, generate, and verify prospect assets.

    External communication, production deployment, and publishing are deliberately
    absent from this autonomous path. They require a separate authorized action.
    """

    def __init__(self, *, store: ProspectStore | None = None, firecrawl: FirecrawlMcpAdapter | None = None) -> None:
        client = firecrawl or FirecrawlMcpAdapter()
        research = ResilientWebResearch(client)
        self.store = store or ProspectStore()
        self.discovery = BusinessDiscovery(research)
        self.researcher = BusinessResearcher(research)

    def scan(self, request: ScanRequest, *, generate: bool | None = None) -> ScanResult:
        started = now()
        discovery = self.discovery.discover(request)
        businesses: list[BusinessRecord] = []
        errors = list(discovery.errors)
        for record in discovery.businesses:
            try:
                businesses.append(self.researcher.research(record, request))
            except Exception as exc:
                record.status = "research_failed"
                record.evidence.append({"source": "AEGIS workflow", "observation": "Research failed", "interpretation": "Record retained with uncertainty; no positive claim was made.", "confidence": "low", "data": {"error": str(exc)}})
                errors.append(f"research failed for {record.business_name}: {exc}")
                businesses.append(record)
        result = ScanResult(request.scan_id, asdict(request), businesses, started, completed_at=now(), errors=errors)
        should_generate = request.generate_limit > 0 if generate is None else generate
        if should_generate:
            candidates = sorted((business for business in businesses if business.location_class in {"DIRECTLY_ON_TARGET", "NEARBY"} and business.classification in {"NO_WEBSITE", "SOCIAL_ONLY", "WEAK_WEBSITE", "OUTDATED_WEBSITE"} and business.opportunity_score >= 40), key=lambda business: business.opportunity_score, reverse=True)[: max(0, request.generate_limit)]
            for business in candidates:
                try:
                    generated = generate_demo(business, Path(request.output_root) / request.scan_id)
                    build = verify_static_site(generated["project_dir"])
                    business.landing_page = {**generated, "build": build}
                    business.status = "demo_static_verified" if build.get("status") == "PASS" else "demo_build_failed"
                    result.generated.append(business.business_id)
                except Exception as exc:
                    business.status = "demo_failed"
                    errors.append(f"demo failed for {business.business_name}: {exc}")
                self.store.save_business(business)
            result.completed_at = now()
        self.store.save_scan(result)
        return result

    def research_business(self, business_id: str, request: ScanRequest | None = None) -> BusinessRecord:
        record = self.store.get_business(business_id)
        if not record:
            raise KeyError(f"unknown business: {business_id}")
        request = request or ScanRequest(target=record.address or record.business_name)
        updated = self.researcher.research(record, request)
        self.store.save_business(updated)
        return updated

    def generate_business_demo(self, business_id: str, *, output_root: str = ".jarvis/prospects") -> dict[str, Any]:
        record = self.store.get_business(business_id)
        if not record:
            raise KeyError(f"unknown business: {business_id}")
        generated = generate_demo(record, Path(output_root) / "manual")
        build = verify_static_site(generated["project_dir"])
        record.landing_page = {**generated, "build": build}
        record.status = "demo_static_verified" if build.get("status") == "PASS" else "demo_build_failed"
        self.store.save_business(record)
        return {"business": record.to_dict(), "generation": generated, "build": build}
