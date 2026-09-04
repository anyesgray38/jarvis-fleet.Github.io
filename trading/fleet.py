"""Deterministic multi-bot coordinator for research and paper execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .bot import TradingBot
from .models import Candle, Signal


@dataclass(frozen=True)
class BotSpec:
    bot_id: str
    symbol: str
    timeframe: str


class TradingBotFleet:
    def __init__(self, bots: Sequence[tuple[str, TradingBot]] = ()):
        self.bots = dict(bots)

    def register(self, bot_id: str, bot: TradingBot) -> None:
        if not bot_id.strip():
            raise ValueError("bot_id is required")
        if bot_id in self.bots:
            raise ValueError("bot_id already registered")
        self.bots[bot_id] = bot

    def paper_scan(self, candles_by_bot: dict[str, Sequence[Candle]]) -> dict[str, Signal | None]:
        results: dict[str, Signal | None] = {}
        for bot_id in sorted(self.bots):
            bot = self.bots[bot_id]
            candles = candles_by_bot.get(bot_id, ())
            results[bot_id] = bot.paper_step(candles)
        return results

    def states(self) -> dict[str, str]:
        return {bot_id: bot.state.value for bot_id, bot in sorted(self.bots.items())}
