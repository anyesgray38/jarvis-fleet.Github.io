"""Public business discovery with corridor evidence and duplicate removal."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from mcp.firecrawl import FirecrawlMcpAdapter

from .models import BusinessRecord, ScanRequest
from .geo import classify_location
from .normalize import ADDRESS_RE, PHONE_RE, address_from, business_from_parts, is_directory, is_social, merge_records, phone_from


@dataclass
class DiscoveryReport:
    businesses: list[BusinessRecord]
    sources: list[str]
    errors: list[str]


class BusinessDiscovery:
    def __init__(self, researcher: FirecrawlMcpAdapter | None = None) -> None:
        self.researcher = researcher or FirecrawlMcpAdapter()

    def discover(self, request: ScanRequest) -> DiscoveryReport:
        queries = self._queries(request)
        hits: list[dict[str, Any]] = []
        sources: list[str] = []
        errors: list[str] = []
        for query in queries:
            try:
                rows = self.researcher.search(query, limit=min(20, request.max_results))
                hits.extend(rows)
                sources.extend(str(row.get("url")) for row in rows if row.get("url"))
                if not rows and getattr(self.researcher, "last_error", None):
                    errors.append(f"search transport degraded for {query!r}: {self.researcher.last_error}")
            except Exception as exc:
                errors.append(f"search failed for {query!r}: {exc}")

        records: list[BusinessRecord] = []
        directory_urls = list(request.source_urls) + [str(row.get("url", "")) for row in hits if self._looks_like_directory(row)]
        for url in list(dict.fromkeys(directory_urls))[:5]:
            try:
                page = self.researcher.scrape(url, formats=["markdown", "links"])
                records.extend(parse_directory_page(page.get("content", ""), url, request))
                sources.append(url)
            except Exception as exc:
                errors.append(f"directory scrape failed for {url}: {exc}")

        for row in hits:
            records.extend(self._candidate_from_hit(row, request))

        records = merge_records(records)
        if not records and not errors:
            errors.append("No candidate businesses were returned by the configured public sources.")
        records = [record for record in records if record.location_class != "IRRELEVANT"]
        records.sort(key=lambda record: (record.location_class != "DIRECTLY_ON_TARGET", record.business_name.lower()))
        return DiscoveryReport(records[: max(1, request.max_results)], sorted(set(sources)), errors)

    @staticmethod
    def _queries(request: ScanRequest) -> list[str]:
        suffix = f" {request.category}" if request.category else ""
        target = request.target.strip()
        return [
            f'"{target}" businesses{suffix}',
            f'"{target}" business directory{suffix}',
            f'{target} local businesses{suffix}',
        ]

    @staticmethod
    def _looks_like_directory(row: dict[str, Any]) -> bool:
        url = str(row.get("url", "")).lower()
        title = str(row.get("title", "")).lower()
        return any(token in url or token in title for token in ("directory", "yellowpages", "yelp", "chamber", "resource", "businesses", "business-directory"))

    def _candidate_from_hit(self, row: dict[str, Any], request: ScanRequest) -> list[BusinessRecord]:
        url = str(row.get("url", ""))
        if not url or is_directory(url) or is_social(url):
            return []
        text = " ".join(str(row.get(key, "")) for key in ("title", "description"))
        address = address_from(text)
        if not address:
            return []
        title = str(row.get("title", "")).split(" - ")[0].split(" | ")[0].strip()
        lowered = title.lower()
        if not title or len(title) > 120 or any(token in lowered for token in ("businesses in", "business directory", "property for sale", "real estate listing", "directory", "listings", "shopping", "restaurants in")):
            return []
        location_class, _ = classify_location(address, request.target)
        if location_class not in {"DIRECTLY_ON_TARGET", "NEARBY"}:
            return []
        return [business_from_parts(title, address, phone_from(text), request.category, url, request.target, website=url, extra={"title": row.get("title"), "description": row.get("description", "")})]


def parse_directory_page(markdown: str, source: str, request: ScanRequest) -> list[BusinessRecord]:
    """Parse common public directory markdown without treating every line as a business."""
    lines = [" ".join(line.replace("\xa0", " ").split()).strip().lstrip("+- ") for line in markdown.splitlines()]
    lines = [line for line in lines if line and not line.startswith("![")]
    records: list[BusinessRecord] = []
    for index, line in enumerate(lines):
        if not _street_line(line):
            continue
        city_line = next((candidate for candidate in lines[index + 1:index + 3] if _city_line(candidate)), "")
        address = f"{line}, {city_line}" if city_line else line
        window = lines[max(0, index - 5): index + 7]
        phone = next((PHONE_RE.search(candidate).group(0) for candidate in lines[index:index + 7] if PHONE_RE.search(candidate)), "")
        if not phone:
            phone = next((PHONE_RE.search(candidate).group(0) for candidate in lines[max(0, index - 3):index] if PHONE_RE.search(candidate)), "")
        if not phone:
            continue
        name = next((candidate for candidate in reversed(lines[max(0, index - 4):index]) if _usable_name(candidate) and not _looks_person(candidate)), "")
        if not name:
            continue
        category = next((candidate for candidate in lines[index + 2:index + 7] if _category_line(candidate)), request.category)
        links = _urls(" ".join(window))
        website = next((link for link in links if not is_social(link) and not _directory_source(link, source)), "")
        records.append(business_from_parts(name, address, phone, category, source, request.target, website=website, extra={"directory_window": window, "source_type": "public_directory"}))
    return _dedupe_page_records(records)


def _street_line(value: str) -> bool:
    return bool(re.match(r"^\d{1,6}\s+[^:]{2,100}$", value)) and not value.lower().startswith(("1 - ", "phone", "view map")) and "http" not in value.lower()


def _city_line(value: str) -> bool:
    return bool(re.search(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b", value))


def _usable_name(value: str) -> bool:
    lowered = value.lower()
    if len(value) < 2 or len(value) > 100 or _city_line(value):
        return False
    if any(token in lowered for token in ("phone", "view map", "email", "search", "category", "loading", "resource directory", "http", "mailto:")):
        return False
    return not bool(PHONE_RE.search(value) or ADDRESS_RE.search(value))


def _looks_person(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][a-z]+(?:['-][A-Za-z]+)?\s+[A-Z][a-z]+(?:['-][A-Za-z]+)?", value.strip()))


def _category_line(value: str) -> bool:
    return bool(value and len(value) < 70 and not ADDRESS_RE.search(value) and not PHONE_RE.search(value) and value[0].isupper())


def _urls(value: str) -> list[str]:
    return re.findall(r"https?://[^\s)\]]+", value)


def _directory_source(url: str, source: str) -> bool:
    return is_directory(url) or urlparse(url).netloc == urlparse(source).netloc


def _dedupe_page_records(records: list[BusinessRecord]) -> list[BusinessRecord]:
    seen: set[tuple[str, str]] = set()
    result: list[BusinessRecord] = []
    for record in records:
        key = (record.business_name.lower(), re.sub(r"\W", "", record.address.lower()))
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result
