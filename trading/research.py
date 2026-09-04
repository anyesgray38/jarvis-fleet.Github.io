"""Deterministic planning primitives for broad trading research."""
from __future__ import annotations

from dataclasses import dataclass
from .strategies import StrategySpec, STRATEGY_CATALOG
from .universe import AssetClass, Instrument, DEFAULT_UNIVERSE


@dataclass(frozen=True)
class ResearchTarget:
    instrument: Instrument
    strategy: StrategySpec
    horizons: tuple[str, ...]
    validation: tuple[str, ...]


DEFAULT_HORIZONS = ("1m", "3m", "5m", "15m", "1h", "4h", "1d")
DEFAULT_VALIDATION = (
    "in_sample",
    "walk_forward",
    "out_of_sample",
    "permutation_test",
    "monte_carlo",
    "independent_reproduction",
    "regime_analysis",
)


class TradingResearchPlanner:
    """Create bounded research targets; it never places orders."""

    def __init__(self, instruments: tuple[Instrument, ...] = DEFAULT_UNIVERSE,
                 strategies: tuple[StrategySpec, ...] = STRATEGY_CATALOG,
                 max_targets: int = 32):
        if max_targets < 1:
            raise ValueError("max_targets must be positive")
        self.instruments = instruments
        self.strategies = strategies
        self.max_targets = max_targets

    def build(self, *, asset_class: AssetClass | None = None, strategy_family: str | None = None) -> tuple[ResearchTarget, ...]:
        instruments = tuple(i for i in self.instruments if asset_class is None or i.asset_class is asset_class)
        strategies = tuple(s for s in self.strategies if strategy_family is None or s.family == strategy_family)
        targets = []
        for instrument in instruments:
            for strategy in strategies:
                targets.append(ResearchTarget(instrument, strategy, DEFAULT_HORIZONS, DEFAULT_VALIDATION))
                if len(targets) >= self.max_targets:
                    return tuple(targets)
        return tuple(targets)
