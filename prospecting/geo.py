"""Conservative corridor and location classification without invented geocodes."""
from __future__ import annotations

import re


_WORD_RE = re.compile(r"[a-z0-9]+")
_ROAD_RE = re.compile(r"\b(?:us|u\.?s\.?)\s*[- ]?\s*(\d+)\b|\b(?:highway|hwy|route)\s*[- ]?(\d+)\b", re.I)


def normalize_text(value: str) -> str:
    return " ".join(_WORD_RE.findall(value.lower()))


def _city_tokens(target: str) -> set[str]:
    tokens = normalize_text(target).split()
    state_codes = {"ga", "georgia", "al", "fl", "tn", "nc", "sc", "va", "ny", "tx", "ca"}
    return {token for token in tokens if token not in state_codes and not token.isdigit() and token not in {"us", "highway", "hwy", "route", "on", "in", "near", "downtown", "of"}}


def corridor_terms(target: str) -> set[str]:
    normalized = normalize_text(target)
    terms: set[str] = set()
    match = _ROAD_RE.search(target)
    if match:
        number = match.group(1) or match.group(2)
        terms.update({f"us {number}", f"highway {number}", f"hwy {number}", f"route {number}", number})
    words = normalized.split()
    for i, word in enumerate(words):
        if word in {"street", "st", "avenue", "ave", "road", "rd", "boulevard", "blvd", "drive", "dr", "lane", "ln", "parkway", "pkwy"} and i:
            terms.add(" ".join(words[max(0, i - 2):i + 1]))
    return terms


def classify_location(address: str, target: str) -> tuple[str, str]:
    if not address.strip():
        return "UNKNOWN", "No address was available to verify against the target."
    address_text = normalize_text(address)
    target_text = normalize_text(target)
    city_tokens = _city_tokens(target)
    city_match = bool(city_tokens) and any(token in address_text.split() for token in city_tokens)
    terms = corridor_terms(target)
    matched_term = next((term for term in terms if _contains_term(address_text, term)), "")
    if matched_term:
        return "DIRECTLY_ON_TARGET", f"Address contains a target corridor term: {matched_term}."
    if city_match:
        return "NEARBY", "Address matches the target locality but does not contain a verified corridor term."
    if any(token in address_text for token in normalize_text(target).split() if len(token) > 3):
        return "UNKNOWN", "Address partially overlaps the target text; corridor placement is not verified."
    if target_text and address_text:
        return "IRRELEVANT", "Available address does not match the target locality or corridor evidence."
    return "UNKNOWN", "Insufficient location evidence."


def _contains_term(address: str, term: str) -> bool:
    if term.isdigit():
        return bool(re.search(rf"(?<!\d){re.escape(term)}(?!\d)", address))
    return term in address
