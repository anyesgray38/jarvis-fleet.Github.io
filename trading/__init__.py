"""Governed trading research and bot primitives for AEGIS."""

from .models import Candle, Direction, OrderIntent, Position, Signal
from .smc import SMCAnalyzer
from .risk import RiskPolicy, RiskDecision
from .bot import TradingBot, BotState
from .fleet import TradingBotFleet
from .backtest import BacktestReport, Backtester, TradeResult
from .paper import PaperBroker
from .universe import AssetClass, Instrument, MarketRegime, DEFAULT_UNIVERSE, find_instruments
from .strategies import StrategySpec, STRATEGY_CATALOG, find_strategies
from .research import ResearchTarget, TradingResearchPlanner

__all__ = [
    "AssetClass", "BacktestReport", "Backtester", "BotState", "Candle",
    "DEFAULT_UNIVERSE", "Direction", "Instrument", "MarketRegime",
    "OrderIntent", "PaperBroker", "Position", "ResearchTarget", "RiskDecision",
    "RiskPolicy", "SMCAnalyzer", "Signal", "StrategySpec", "STRATEGY_CATALOG",
    "TradeResult", "TradingBot", "TradingBotFleet", "TradingResearchPlanner",
    "find_instruments", "find_strategies",
]
