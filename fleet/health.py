"""Pure health scoring primitives for Fleet scheduling and admission."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class HealthSnapshot:
    reachable: bool
    latency_ms: float | None = None
    load: float | None = None
    last_seen_age_s: float | None = None

    @property
    def healthy(self) -> bool:
        if not self.reachable:
            return False
        if self.last_seen_age_s is not None and self.last_seen_age_s > 120:
            return False
        if self.load is not None and not 0 <= self.load <= 1:
            return False
        return True

    def score(self) -> float:
        if not self.healthy:
            return 0.0
        score = 50.0
        if self.latency_ms is not None:
            score += max(0.0, 25.0 - min(25.0, self.latency_ms / 10.0))
        if self.load is not None:
            score += 25.0 * (1.0 - self.load)
        return score
