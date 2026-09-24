"""Durable contracts for business prospecting records and scans."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:16]}"


@dataclass(frozen=True)
class Evidence:
    source: str
    observation: str
    interpretation: str = ""
    confidence: str = "medium"
    captured_at: str = field(default_factory=now)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BusinessRecord:
    business_id: str
    business_name: str
    address: str = ""
    phone: str = ""
    category: str = ""
    website: str = ""
    website_state: str = "UNKNOWN"
    social_profiles: list[dict[str, Any]] = field(default_factory=list)
    discovery_sources: list[str] = field(default_factory=list)
    research_timestamp: str = ""
    location_class: str = "UNKNOWN"
    location_reason: str = ""
    website_audit: dict[str, Any] = field(default_factory=dict)
    social_audit: dict[str, Any] = field(default_factory=dict)
    classification: str = "UNKNOWN"
    opportunities: list[str] = field(default_factory=list)
    confidence: str = "low"
    opportunity_score: int = 0
    score_reasons: list[str] = field(default_factory=list)
    landing_page: dict[str, Any] = field(default_factory=dict)
    deployment: dict[str, Any] = field(default_factory=dict)
    research_history: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    status: str = "discovered"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScanRequest:
    target: str
    category: str = ""
    radius_miles: float | None = None
    max_results: int = 30
    generate_limit: int = 0
    output_root: str = ".jarvis/prospects"
    source_urls: tuple[str, ...] = ()
    scan_id: str = field(default_factory=lambda: new_id("scan"))


@dataclass
class ScanResult:
    scan_id: str
    request: dict[str, Any]
    businesses: list[BusinessRecord]
    started_at: str
    completed_at: str = ""
    errors: list[str] = field(default_factory=list)
    generated: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for business in self.businesses:
            counts[business.classification] = counts.get(business.classification, 0) + 1
        return {
            "scan_id": self.scan_id,
            "target": self.request.get("target", ""),
            "businesses_discovered": len(self.businesses),
            "location_classes": {
                key: sum(1 for b in self.businesses if b.location_class == key)
                for key in ("DIRECTLY_ON_TARGET", "NEARBY", "IRRELEVANT", "UNKNOWN")
            },
            "classifications": counts,
            "high_opportunity": sum(1 for b in self.businesses if b.opportunity_score >= 60 and b.classification != "UNKNOWN"),
            "landing_pages_generated": len(self.generated),
            "errors": len(self.errors),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "request": self.request,
            "businesses": [business.to_dict() for business in self.businesses],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "errors": self.errors,
            "generated": self.generated,
            "summary": self.summary(),
        }
