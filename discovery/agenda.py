"""Prioritize autonomous research without granting execution authority."""
from __future__ import annotations

from dataclasses import dataclass
from .autonomy import ResearchOpportunity


@dataclass(frozen=True)
class Agenda:
    opportunities: tuple[ResearchOpportunity, ...]


class AgendaBuilder:
    """Apply deterministic bounds to the autonomous research queue."""

    def __init__(self, max_items: int = 4):
        if max_items < 1:
            raise ValueError("max_items must be positive")
        self.max_items = max_items

    def build(self, opportunities: tuple[ResearchOpportunity, ...]) -> Agenda:
        ranked = sorted(opportunities, key=lambda item: (-item.priority, item.opportunity_id))
        return Agenda(tuple(ranked[: self.max_items]))
