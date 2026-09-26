"""Bounded, local reverse-engineering of inbound knowledge.

This module treats fetched material as untrusted data. It never executes code,
follows instructions, or promotes arbitrary source text directly into active
memory. The output is a compact, inspectable analysis that can be re-derived
from the archived source.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any

_STOPWORDS = {
    "about", "after", "again", "against", "being", "between", "could", "first", "from",
    "have", "into", "more", "other", "should", "their", "there", "these", "those", "through",
    "under", "using", "which", "while", "with", "would", "your", "this", "that", "were", "when",
    "where", "what", "will", "they", "them", "than", "then", "also", "only", "such", "some",
    "the", "and", "for", "are", "can", "not", "but", "all", "its", "our", "you", "use", "one",
}


def _clean(value: str, limit: int = 500) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"[`*_>#~]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit].rsplit(" ", 1)[0] + ("…" if len(value) > limit else "")


def _sentences(content: str) -> list[str]:
    text = re.sub(r"\s+", " ", content).strip()
    rows = [_clean(row, 360) for row in re.split(r"(?<=[.!?])\s+|\n+", text) if row.strip()]
    return [row for row in rows if len(row) >= 35][:80]


def _concepts(content: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", content.lower())
    counts = Counter(word for word in words if word not in _STOPWORDS and not word.isdigit())
    return [word for word, _count in counts.most_common(24)]


def reverse_engineer_source(*, title: str, url: str, content: str, provider: str) -> dict[str, Any]:
    """Run bounded understanding subtasks before a source can be promoted."""
    raw = str(content or "")
    if not raw.strip():
        raise ValueError("cannot reverse-engineer an empty source")
    headings = [_clean(match.group(1), 160) for match in re.finditer(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", raw, re.MULTILINE)]
    links = []
    for match in re.finditer(r"https?://[^\s)<>\"']+", raw):
        value = match.group(0).rstrip(".,;")
        if value not in links:
            links.append(value)
        if len(links) >= 20:
            break
    code_blocks = re.findall(r"```([\s\S]*?)```", raw)
    claims = _sentences(raw)
    analysis = {
        "schema": "aegis.reverse-engineering.v1",
        "status": "verified_for_compaction",
        "subtasks": {
            "structure": bool(headings or claims),
            "claims": bool(claims),
            "concepts": True,
            "provenance": bool(url and provider),
            "prompt_injection_boundary": True,
            "compact": True,
        },
        "source_fingerprint": hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest(),
        "title": _clean(title, 180),
        "url": url,
        "provider": provider,
        "headings": headings[:20],
        "claims": claims[:12],
        "concepts": _concepts(raw),
        "links": links,
        "code_blocks": min(len(code_blocks), 20),
        "content_chars": len(raw),
        "word_count": len(raw.split()),
    }
    if not analysis["subtasks"]["provenance"]:
        analysis["status"] = "needs_review"
    return analysis
