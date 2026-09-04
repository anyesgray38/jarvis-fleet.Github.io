"""Provider-neutral strategy families for broad trading research."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    family: str
    description: str
    required_features: tuple[str, ...]
    research_only: bool = True


STRATEGY_CATALOG: tuple[StrategySpec, ...] = (
    StrategySpec("smc", "structure", "Liquidity, imbalance, displacement and structure-based trading", ("ohlcv", "swing_structure", "liquidity")),
    StrategySpec("trend_following", "trend", "Systematic directional participation after trend confirmation", ("ohlcv", "trend_features")),
    StrategySpec("mean_reversion", "reversion", "Statistical reversion toward a defined reference", ("ohlcv", "distribution_features")),
    StrategySpec("breakout", "volatility", "Trade expansion from a defined consolidation or range", ("ohlcv", "range_features", "volatility")),
    StrategySpec("momentum", "momentum", "Rank and trade persistent price movement", ("ohlcv", "momentum_features")),
    StrategySpec("volatility", "volatility", "Model and trade changes in realized or implied volatility", ("ohlcv", "volatility_features")),
    StrategySpec("pairs", "relative_value", "Relative-value trading between linked instruments", ("synchronized_prices", "spread")),
    StrategySpec("stat_arb", "relative_value", "Statistical relationships across a portfolio of instruments", ("panel_prices", "cross_sectional_features")),
    StrategySpec("carry", "macro", "Return associated with holding assets with favorable carry", ("price", "carry_data")),
    StrategySpec("macro_regime", "macro", "Conditional strategies selected by macroeconomic regime", ("market_data", "macro_data", "regime_features")),
    StrategySpec("event_driven", "event", "Research price response around scheduled or unscheduled events", ("market_data", "event_timestamps")),
    StrategySpec("seasonality", "calendar", "Conditional behavior associated with calendar or session effects", ("timestamped_prices", "calendar_features")),
    StrategySpec("order_flow", "microstructure", "Use transaction or order-book imbalance where available", ("trades_or_book", "microstructure")),
)


def find_strategies(*, family: str | None = None, feature: str | None = None) -> tuple[StrategySpec, ...]:
    return tuple(
        strategy for strategy in STRATEGY_CATALOG
        if (family is None or strategy.family == family)
        and (feature is None or feature in strategy.required_features)
    )
