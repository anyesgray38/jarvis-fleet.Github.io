"""Deterministic public website and social audits with bounded network reads."""
from __future__ import annotations

import html
import re
import ssl
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from mcp.firecrawl import FirecrawlMcpAdapter

from .models import BusinessRecord, Evidence, now
from .normalize import is_social


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.viewport = ""
        self.h1_count = 0
        self.nav_count = 0
        self.forms = 0
        self.links: list[str] = []
        self.text_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() == "meta" and data.get("name", "").lower() == "description":
            self.description = data.get("content", "")
        if tag.lower() == "meta" and data.get("name", "").lower() == "viewport":
            self.viewport = data.get("content", "")
        if tag.lower() == "link" and data.get("rel", "").lower() == "canonical":
            self.canonical = data.get("href", "")
        if tag.lower() == "h1":
            self.h1_count += 1
        if tag.lower() == "nav":
            self.nav_count += 1
        if tag.lower() == "form":
            self.forms += 1
        if tag.lower() == "a" and data.get("href"):
            self.links.append(data["href"])

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if not value:
            return
        self.text_parts.append(value)
        if self._in_title:
            self.title += value


def fetch_html(url: str, *, timeout: float = 12.0, limit: int = 1_500_000) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("website URL must be an absolute http(s) URL")
    request = Request(url, headers={"User-Agent": "AEGIS public prospect research/1.0", "Accept": "text/html,application/xhtml+xml"})
    try:
        with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise ValueError("website response exceeds bounded audit size")
            return {"status_code": response.status, "final_url": response.geturl(), "content_type": content_type, "html": raw.decode("utf-8", errors="replace")}
    except HTTPError as exc:
        return {"status_code": exc.code, "final_url": url, "content_type": exc.headers.get("Content-Type", ""), "html": "", "error": str(exc)}
    except (URLError, TimeoutError, OSError) as exc:
        return {"status_code": None, "final_url": url, "content_type": "", "html": "", "error": str(exc)}


def audit_website(url: str, *, business: BusinessRecord | None = None) -> dict[str, Any]:
    observed = fetch_html(url)
    markup = observed.get("html", "")
    parser = PageParser()
    if markup:
        parser.feed(markup)
    text = " ".join(parser.text_parts).lower()
    final_url = str(observed.get("final_url") or url)
    links_lower = [link.lower() for link in parser.links]
    ctas = [keyword for keyword in ("book", "appointment", "request a quote", "get a quote", "contact", "call", "order online", "directions") if keyword in text or any(keyword in link for link in links_lower)]
    phone = business.phone if business else ""
    phone_digits = re.sub(r"\D", "", phone)
    has_phone = bool(phone_digits and phone_digits[-7:] in re.sub(r"\D", "", text)) or bool(re.search(r"\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}", text))
    address_text = (business.address.lower() if business else "").strip()
    has_address = bool(address_text and all(token in text for token in address_text.lower().split()[:2]))
    has_hours = any(token in text for token in ("hours", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"))
    has_services = any(token in text for token in ("services", "menu", "repairs", "maintenance", "products", "what we do"))
    findings: list[str] = []
    if not parser.viewport:
        findings.append("No viewport meta tag was observed; mobile readiness is unverified.")
    if not parser.title:
        findings.append("No HTML title was observed.")
    if not parser.description:
        findings.append("No meta description was observed.")
    if parser.h1_count == 0:
        findings.append("No h1 heading was observed.")
    if not ctas:
        findings.append("No recognizable conversion CTA was observed in page text or links.")
    if not has_phone:
        findings.append("The verified business phone was not observed in the page text.")
    if not has_address:
        findings.append("The verified business address was not observed in the page text.")
    technical = {
        "https": final_url.startswith("https://"),
        "status_code": observed.get("status_code"),
        "redirected": final_url.rstrip("/") != url.rstrip("/"),
        "content_type": observed.get("content_type", ""),
        "title": parser.title.strip(),
        "description": parser.description.strip(),
        "canonical": parser.canonical,
        "viewport": parser.viewport,
        "h1_count": parser.h1_count,
        "nav_count": parser.nav_count,
        "form_count": parser.forms,
        "links_checked": 0,
        "broken_links": [],
    }
    audit = {
        "audited_at": now(),
        "url": url,
        "reachable": bool(observed.get("status_code") and 200 <= int(observed["status_code"]) < 400 and markup),
        "error": observed.get("error"),
        "technical": technical,
        "business_information": {"phone": has_phone, "address": has_address, "hours": has_hours, "services": has_services},
        "conversion": {"cta_count": len(ctas), "ctas": ctas, "contact_form": parser.forms > 0, "booking": "book" in ctas or "appointment" in ctas, "online_ordering": "order online" in ctas, "directions": "directions" in ctas},
        "findings": findings,
        "evidence": [Evidence(source=url, observation=f"Fetched HTTP {observed.get('status_code')}; parsed {len(markup)} HTML characters.", interpretation="Website characteristics below are parser observations, not commercial predictions.", confidence="high", data={"final_url": final_url, "content_type": observed.get("content_type", "")}).to_dict()],
    }
    if not audit["reachable"] and observed.get("error"):
        audit["findings"].insert(0, f"Fetch failed: {observed['error']}")
    return audit


def audit_social(client: FirecrawlMcpAdapter, business: BusinessRecord) -> dict[str, Any]:
    query = f'"{business.business_name}" "{business.address}"'
    try:
        rows = client.search(query, limit=12)
    except Exception as exc:
        return {"checked_at": now(), "profiles": [], "confidence": "low", "error": str(exc), "evidence": []}
    profiles: list[dict[str, Any]] = []
    for row in rows:
        url = str(row.get("url", ""))
        if not is_social(url):
            continue
        profiles.append({"platform": urlparse(url).netloc.lower().removeprefix("www.").split(".")[0], "url": url, "officiality": "likely_official", "title": row.get("title", ""), "description": row.get("description", "")})
    return {"checked_at": now(), "profiles": profiles[:10], "confidence": "medium" if profiles else "low", "search_query": query, "evidence": [Evidence(source="Firecrawl web search", observation=f"Found {len(profiles)} public social result(s) matching the business name and address query.", interpretation="Profiles are likely official, not verified ownership.", confidence="medium" if profiles else "low").to_dict()]}
