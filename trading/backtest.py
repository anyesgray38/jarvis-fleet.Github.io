"""Minimal event-driven backtest harness for signal research."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .models import Candle, Direction
from .smc import SMCAnalyzer


@dataclass(frozen=True)
class TradeResult:
    signal_id: str
    direction: Direction
    entry: float
    exit: float
    pnl_per_unit: float
    outcome: str


@dataclass(frozen=True)
class BacktestReport:
    trades: tuple[TradeResult, ...]
    total_pnl_per_unit: float
    win_rate: float
    max_drawdown_per_unit: float


class Backtester:
    def __init__(self, analyzer: SMCAnalyzer | None = None):
        self.analyzer = analyzer or SMCAnalyzer()

    def run(self, symbol: str, timeframe: str, candles: Sequence[Candle]) -> BacktestReport:
        trades: list[TradeResult] = []
        i = 0
        while i < len(candles):
            signal = self.analyzer.analyze(symbol, timeframe, candles[: i + 1])
            if signal is None:
                i += 1
                continue
            exit_price = None
            outcome = "unresolved"
            for j in range(i + 1, len(candles)):
                c = candles[j]
                if signal.direction is Direction.LONG:
                    if c.low <= signal.stop:
                        exit_price, outcome = signal.stop, "stop"
                        break
                    if c.high >= signal.target:
                        exit_price, outcome = signal.target, "target"
                        break
                else:
                    if c.high >= signal.stop:
                        exit_price, outcome = signal.stop, "stop"
                        break
                    if c.low <= signal.target:
                        exit_price, outcome = signal.target, "target"
                        break
            if exit_price is None:
                i += 1
                continue
            pnl = (exit_price - signal.entry) * signal.direction.sign
            trades.append(TradeResult(signal.signal_id, signal.direction, signal.entry, exit_price, pnl, outcome))
            i = j + 1

        equity = peak = drawdown = 0.0
        for trade in trades:
            equity += trade.pnl_per_unit
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        wins = sum(1 for t in trades if t.pnl_per_unit > 0)
        return BacktestReport(tuple(trades), equity, wins / len(trades) if trades else 0.0, drawdown)
