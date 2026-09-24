"""Explainable digital-opportunity classification and scoring."""
from __future__ import annotations

from .models import BusinessRecord


def score_business(record: BusinessRecord) -> BusinessRecord:
    audit = record.website_audit
    technical = audit.get("technical", {}) if isinstance(audit, dict) else {}
    business_info = audit.get("business_information", {}) if isinstance(audit, dict) else {}
    conversion = audit.get("conversion", {}) if isinstance(audit, dict) else {}
    score = 0
    reasons: list[str] = []
    opportunities: list[str] = []
    if record.website_state == "NOT_FOUND":
        score += 35; reasons.append("No official website was found after independent public search queries."); opportunities.append("website")
    elif record.website_state == "UNKNOWN":
        score += 15; reasons.append("Website existence remains uncertain and needs verification."); opportunities.append("website")
    elif not audit.get("reachable", False):
        score += 30; reasons.append("A candidate website was not reachable during the audit."); opportunities.append("website")
    if record.website_state in {"NOT_FOUND", "UNKNOWN"}:
        if not record.social_profiles:
            score += 5; reasons.append("No likely official public social profile was discovered in the current search."); opportunities.append("social integration")
        record.opportunity_score = min(100, score)
        record.score_reasons = list(dict.fromkeys(reasons))
        record.opportunities = list(dict.fromkeys(opportunities))
        record.classification = "SOCIAL_ONLY" if record.website_state == "NOT_FOUND" and record.social_profiles else "NO_WEBSITE" if record.website_state == "NOT_FOUND" else "UNKNOWN"
        record.confidence = "medium" if record.address and record.discovery_sources else "low"
        return record
    if record.website_state in {"CONFIRMED", "LIKELY"} and not technical.get("https"):
        score += 10; reasons.append("The audited final URL did not use HTTPS."); opportunities.append("security")
    if not technical.get("viewport"):
        score += 15; reasons.append("No viewport meta tag was observed."); opportunities.append("mobile UX")
    if not conversion.get("cta_count"):
        score += 15; reasons.append("No recognizable conversion CTA was observed."); opportunities.append("conversion")
    if not conversion.get("contact_form") and not conversion.get("booking") and not conversion.get("online_ordering"):
        score += 5; reasons.append("No contact, booking, or ordering interaction was observed."); opportunities.append("lead generation")
    if not technical.get("title") or not technical.get("description"):
        score += 8; reasons.append("Title or meta description signals are incomplete."); opportunities.append("SEO")
    if not business_info.get("phone") or not business_info.get("address"):
        score += 7; reasons.append("Verified contact or location information was not observed on the page."); opportunities.append("local SEO")
    if not record.social_profiles:
        score += 5; reasons.append("No likely official public social profile was discovered in the current search."); opportunities.append("social integration")
    score = min(100, score)
    record.opportunity_score = score
    record.score_reasons = list(dict.fromkeys(reasons))
    record.opportunities = list(dict.fromkeys(opportunities))
    if record.website_state == "NOT_FOUND":
        record.classification = "SOCIAL_ONLY" if record.social_profiles else "NO_WEBSITE"
    elif record.website_state in {"CONFIRMED", "LIKELY"}:
        finding_count = len(audit.get("findings", [])) if isinstance(audit, dict) else 0
        record.classification = "OUTDATED_WEBSITE" if finding_count >= 4 and not technical.get("viewport") else "WEAK_WEBSITE" if score >= 35 else "WEBSITE_PLUS_SOCIAL" if record.social_profiles else "STRONG_WEBSITE"
    else:
        record.classification = "UNKNOWN"
    record.confidence = "high" if record.address and record.discovery_sources and (record.website_state != "UNKNOWN") else "medium" if record.address else "low"
    return record
