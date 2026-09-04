"""Governed trading research and bot primitives for AEGIS."""

from .models import Candle, Direction, OrderIntent, Position, Signal
from .smc import SMCAnalyzer
from .risk import RiskPolicy, RiskDecision
from .bot import TradingBot, BotState
from .paper import PaperBroker

__all__ = [
    "BotState", "Candle", "Direction", "OrderIntent", "PaperBroker",
    "Position", "RiskDecision", "RiskPolicy", "SMCAnalyzer", "Signal",
    "TradingBot",
]
