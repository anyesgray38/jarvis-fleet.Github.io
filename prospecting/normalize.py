"""Business candidate normalization and conservative deduplication."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

from .geo import classify_location
from .models import BusinessRecord, Evidence, new_id


PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]\d{4}")
ADDRESS_RE = re.compile(r"\b\d{1,6}\s+(?:[A-Za-z0-9][A-Za-z0-9.'-]*\s+){0,7}(?:street|st|road|rd|avenue|ave|boulevard|blvd|drive|dr|lane|ln|parkway|pkwy|court|ct|circle|cir|highway|hwy|route|(?:u\.?s\.?|highway|hwy|route)[- ]?\d+|\d+\s+(?:highway|hwy))\b", re.I)
SOCIAL_HOSTS = {"facebook.com", "instagram.com", "tiktok.com", "youtube.com", "linkedin.com", "x.com", "twitter.com"}
DIRECTORY_HOSTS = {"yelp.com", "yellowpages.com", "bestprosintown.com", "mapquest.com", "tripadvisor.com", "loopnet.com", "cityofthomaston.com"}


def clean(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split()).strip(" +-|:")


def canonical_key(name: str, address: str = "", phone: str = "", website: str = "") -> str:
    host = urlparse(website).netloc.lower().removeprefix("www.") if website else ""
    raw = "|".join(clean(x).lower() for x in (name, address, re.sub(r"\D", "", phone), host))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def is_social(url: str) -> bool:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return any(host == item or host.endswith("." + item) for item in SOCIAL_HOSTS)


def is_directory(url: str) -> bool:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return any(host == item or host.endswith("." + item) for item in DIRECTORY_HOSTS)


def phone_from(text: str) -> str:
    match = PHONE_RE.search(text)
    return clean(match.group(0)) if match else ""


def address_from(text: str) -> str:
    value = " ".join(text.replace("\xa0", " ").split())
    match = ADDRESS_RE.search(value)
    if not match:
        return ""
    address = match.group(0)
    tail = value[match.end():match.end() + 90]
    locality = re.search(r"(?:,|\)|\s-\s)?\s*([A-Za-z][A-Za-z .'-]{2,30},?\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?)", tail)
    if locality:
        address = f"{address}, {locality.group(1)}"
    return clean(address)


def business_from_parts(name: str, address: str, phone: str, category: str, source: str, target: str, website: str = "", extra: dict | None = None) -> BusinessRecord:
    location_class, location_reason = classify_location(address, target)
    record = BusinessRecord(
        business_id=new_id("biz"),
        business_name=clean(name) or "Unknown business",
        address=clean(address),
        phone=clean(phone),
        category=clean(category),
        website=website,
        discovery_sources=[source] if source else [],
        location_class=location_class,
        location_reason=location_reason,
        confidence="medium" if name and address else "low",
    )
    record.evidence.append(Evidence(source=source or "discovery", observation=f"Candidate discovered as {record.business_name}.", interpretation=location_reason, confidence=record.confidence, data=extra or {}).to_dict())
    return record


def merge_records(records: list[BusinessRecord]) -> list[BusinessRecord]:
    merged: dict[str, BusinessRecord] = {}
    for record in records:
        key = canonical_key(record.business_name, record.address, record.phone, record.website)
        existing = merged.get(key)
        if not existing:
            merged[key] = record
            continue
        existing.discovery_sources = sorted(set(existing.discovery_sources + record.discovery_sources))
        existing.evidence.extend(record.evidence)
        existing.social_profiles = _merge_dicts(existing.social_profiles, record.social_profiles, "url")
        for field in ("address", "phone", "category", "website"):
            if not getattr(existing, field) and getattr(record, field):
                setattr(existing, field, getattr(record, field))
        if existing.location_class == "UNKNOWN" and record.location_class != "UNKNOWN":
            existing.location_class, existing.location_reason = record.location_class, record.location_reason
    return list(merged.values())


def _merge_dicts(first: list[dict], second: list[dict], key: str) -> list[dict]:
    seen = {str(item.get(key)): item for item in first if item.get(key)}
    for item in second:
        if item.get(key):
            seen.setdefault(str(item[key]), item)
    return list(seen.values())
