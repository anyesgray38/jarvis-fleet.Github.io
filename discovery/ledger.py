"""Append-only epistemic ledger for scientific discovery.

The ledger preserves claim state transitions and provenance. It deliberately does
not mutate or delete historical observations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .models import KnowledgeCandidate, KnowledgeState


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class LedgerEntry:
    entry_id: str
    claim: str
    state: KnowledgeState
    confidence: float
    evidence_ids: tuple[str, ...] = ()
    independent_groups: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    reason: str = ""
    created_at: str = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)


class EpistemicLedger:
    """Append-only knowledge state with monotonic provenance preservation."""

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        return tuple(self._entries)

    def record(self, candidate: KnowledgeCandidate, *, reason: str = "", metadata: dict[str, Any] | None = None) -> LedgerEntry:
        entry = LedgerEntry(
            entry_id=f"ledger-{len(self._entries) + 1:08d}",
            claim=candidate.claim,
            state=candidate.state,
            confidence=max(0.0, min(1.0, candidate.confidence)),
            evidence_ids=candidate.evidence_ids,
            independent_groups=candidate.independent_groups,
            conflicts=candidate.conflicts,
            dependencies=candidate.dependencies,
            reason=reason,
            metadata=dict(metadata or {}),
        )
        self._entries.append(entry)
        return entry

    def latest(self, claim: str) -> LedgerEntry | None:
        for entry in reversed(self._entries):
            if entry.claim == claim:
                return entry
        return None

    def promoteable(self, claim: str, *, min_confidence: float = 0.8, min_independence: int = 2) -> bool:
        entry = self.latest(claim)
        return bool(
            entry
            and entry.state is KnowledgeState.VERIFIED
            and entry.confidence >= min_confidence
            and len(entry.independent_groups) >= min_independence
            and not entry.conflicts
            and entry.evidence_ids
        )
