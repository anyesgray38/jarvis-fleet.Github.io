"""Normalize large MCP catalogs into AEGIS capability records.

The catalog parser intentionally preserves source URLs and raw descriptions so
AEGIS can re-review entries instead of treating a directory listing as trust.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Iterable


CATEGORY_CAPABILITIES = {
    "Aggregators": ["integration", "discovery"],
    "Agreements & Coordination": ["coordination", "agents"],
    "Art & Culture": ["culture", "media"],
    "Architecture & Design": ["design", "visualization"],
    "Browser Automation": ["browser", "automation"],
    "Biology Medicine and Bioinformatics": ["science", "biomedical"],
    "Cloud Platforms": ["cloud", "infrastructure"],
    "Code Execution": ["code_execution", "sandbox"],
    "Coding Agents": ["coding", "software_engineering"],
    "Command Line": ["shell", "automation"],
    "Communication": ["communications", "messaging"],
    "Conversational AI": ["conversation", "llm"],
    "Cryptography": ["cryptography", "security"],
    "Customer Data Platforms": ["customer_data", "crm"],
    "Databases": ["database", "data"],
    "Data Platforms": ["data", "analytics"],
    "Delivery": ["delivery", "logistics"],
    "Developer Tools": ["development", "devops"],
    "Data Science Tools": ["statistics", "data_science"],
    "Data Visualization": ["visualization", "analytics"],
    "Embedded system": ["embedded", "iot"],
    "Education": ["education", "learning"],
    "E-Commerce": ["commerce", "shopping"],
    "Environment & Nature": ["environment", "research"],
    "File Systems": ["filesystem", "storage"],
    "Finance & Fintech": ["finance", "fintech"],
    "Gaming": ["gaming", "media"],
    "Home Automation": ["home_automation", "iot"],
    "Industrial & IoT": ["industrial", "iot"],
    "Knowledge & Memory": ["knowledge", "memory", "retrieval"],
    "Legal": ["legal", "research"],
    "Location Services": ["geospatial", "location"],
    "Marketing": ["marketing", "analytics"],
    "Monitoring": ["monitoring", "observability"],
    "Multimedia Process": ["multimedia", "media"],
    "OS Automation": ["os_automation", "automation"],
    "Podcasts": ["podcasts", "media"],
    "Product Management": ["product", "project_management"],
    "Real Estate": ["real_estate", "property"],
    "Research": ["research", "evidence"],
    "Search & Data Extraction": ["search", "extraction"],
    "Security": ["security", "compliance"],
    "Social Media": ["social", "publishing"],
    "Spirituality & Esoterica": ["knowledge", "culture"],
    "Sports": ["sports", "analytics"],
    "Support & Service Management": ["support", "service"],
    "Translation Services": ["translation", "language"],
    "Text-to-Speech": ["tts", "audio"],
    "Speech-to-Text": ["stt", "audio"],
    "Travel & Transportation": ["travel", "transportation"],
    "Version Control": ["git", "software_engineering"],
    "Workplace & Productivity": ["productivity", "workflow"],
    "Other Tools and Integrations": ["integration", "automation"],
}


@dataclass(frozen=True)
class MCPServerRecord:
    name: str
    url: str
    category: str
    tags: tuple[str, ...] = ()
    scope: tuple[str, ...] = ()
    language: str | None = None
    description: str = ""
    source: str = "punkpeye/awesome-mcp-servers"
    trust: str = "unreviewed"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_catalog(markdown: str, *, source: str = "punkpeye/awesome-mcp-servers") -> list[MCPServerRecord]:
    category = "Other Tools and Integrations"
    records: list[MCPServerRecord] = []
    seen: set[tuple[str, str]] = set()
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        heading = _heading_name(line)
        if heading:
            category = heading
            continue
        if not line.startswith("-") or "](http" not in line:
            continue
        match = re.match(r"-\s+\[([^\]]+)\]\((https?://[^)]+)\)(.*)", line)
        if not match:
            continue
        name, url, suffix = match.groups()
        key = (name.strip(), url.strip())
        if key in seen:
            continue
        seen.add(key)
        records.append(_record(name.strip(), url.strip(), category, suffix, source))
    return records


def _heading_name(line: str) -> str | None:
    match = re.match(r"###\s+(?:.\s+)?<a name=\"[^\"]+\"></a>(.+)$", line)
    if match:
        value = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        return _strip_emoji(value)
    match = re.match(r"###\s+(.+)$", line)
    if match and not match.group(1).lower().startswith("<a name="):
        value = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        return _strip_emoji(value)
    return None


def _record(name: str, url: str, category: str, suffix: str, source: str) -> MCPServerRecord:
    description = re.sub(r"\s+", " ", re.sub(r"\[[^\]]+\]\([^)]*\)", "", suffix)).strip(" -")
    language = _language_from_suffix(suffix)
    scope = tuple(x for x in ("cloud" if "☁️" in suffix else None, "local" if "🏠" in suffix else None, "embedded" if "📟" in suffix else None) if x)
    tags = tuple(dict.fromkeys(CATEGORY_CAPABILITIES.get(category, ["integration"])))
    return MCPServerRecord(name=name, url=url, category=category, tags=tags, scope=scope, language=language, description=description, source=source)


def _language_from_suffix(suffix: str) -> str | None:
    for marker, language in (("🐍", "python"), ("📇", "typescript"), ("🏎️", "go"), ("🦀", "rust"), ("#️⃣", "csharp"), ("☕", "java"), ("🌊", "cpp"), ("💎", "ruby")):
        if marker in suffix:
            return language
    return None


def _strip_emoji(value: str) -> str:
    return re.sub(r"^[^A-Za-z0-9]+", "", value).strip()


def group_by_capability(records: Iterable[MCPServerRecord]) -> dict[str, list[MCPServerRecord]]:
    grouped: dict[str, list[MCPServerRecord]] = {}
    for record in records:
        for tag in record.tags:
            grouped.setdefault(tag, []).append(record)
    return grouped
