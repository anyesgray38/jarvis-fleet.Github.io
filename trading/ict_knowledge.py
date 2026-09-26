"""ICT knowledge layer derived from the user-provided Practical ICT Strategies — 7th Edition PDF.

This module is descriptive and research-only. It exposes deterministic rule metadata
for AEGIS and deliberately separates source claims from engine interpretation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_KNOWLEDGE_PATH = Path(__file__).with_name("ict_knowledge.json")

def load_ict_knowledge() -> dict[str, Any]:
    with _KNOWLEDGE_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)

def foundation_sequence() -> tuple[str, ...]:
    return tuple(load_ict_knowledge()["framework"]["foundation_sequence"])

def strategy_rules(strategy_id: str) -> dict[str, Any]:
    strategies = load_ict_knowledge()["strategies"]
    if strategy_id not in strategies:
        raise KeyError(f"unknown ICT strategy: {strategy_id}")
    return strategies[strategy_id]

def liquidity_first_roles() -> dict[str, str]:
    return dict(load_ict_knowledge()["framework"]["liquidity_first_interpretation"])


def term_definitions() -> dict[str, dict[str, str]]:
    """Return the local meaning/function dictionary used by Trading agents."""
    return dict(load_ict_knowledge().get("term_definitions", {}))


def _normalized_term(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().replace("_", " ").replace("-", " ")).strip()


def term_definition(term: str) -> dict[str, str] | None:
    """Resolve a local definition by canonical name, phrase, or glossary alias."""
    requested = _normalized_term(term)
    definitions = term_definitions()
    for canonical, definition in definitions.items():
        if _normalized_term(canonical) == requested:
            return dict(definition)

    aliases = {
        "market structure shift": "MSS",
        "change in state of delivery": "CISD",
        "fair value gap": "FVG",
        "buy side liquidity": "BSL",
        "sell side liquidity": "SSL",
        "external range liquidity": "ERL",
        "internal range liquidity": "IRL",
        "order block": "OB",
        "optimal trade entry": "OTE",
        "inverted fair value gap": "IFVG",
        "balanced price range": "BPR",
        "smart money technique divergence": "SMT",
    }
    canonical = aliases.get(requested)
    if canonical and canonical in definitions:
        return dict(definitions[canonical])
    return None
