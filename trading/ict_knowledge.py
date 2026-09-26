"""ICT knowledge layer derived from the user-provided Practical ICT Strategies — 7th Edition PDF.

This module is descriptive and research-only. It exposes deterministic rule metadata
for AEGIS and deliberately separates source claims from engine interpretation.
"""
from __future__ import annotations

import json
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
