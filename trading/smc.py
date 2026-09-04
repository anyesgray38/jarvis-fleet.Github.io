"""Conservative Smart Money Concepts feature extraction and signal scoring.

This module is intentionally deterministic. It turns candles into observable
features; it does not claim that an SMC pattern is predictive without testing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .models import Candle, Direction, Signal


@dataclass(frozen=True)
class FVG:
    direction: Direction
    low: float
    high: float
    index: int


@dataclass(frozen=True)
class Sweep:
    direction: Direction
    level: float
    index: int


class SMCAnalyzer:
    def __init__(self, pivot_window: int = 2, min_score: float = 70.0):
        if pivot_window < 1:
            raise ValueError("pivot_window must be positive")
        self.pivot_window = pivot_window
        self.min_score = min_score

    def swings(self, candles: Sequence[Candle]) -> tuple[tuple[str, int, float], ...]:
        w = self.pivot_window
        out: list[tuple[str, int, float]] = []
        for i in range(w, len(candles) - w):
            c = candles[i]
            left = candles[i - w:i]
            right = candles[i + 1:i + w + 1]
            if c.high > max(x.high for x in left + right):
                out.append(("high", i, c.high))
            if c.low < min(x.low for x in left + right):
                out.append(("low", i, c.low))
        return tuple(out)

    def fair_value_gaps(self, candles: Sequence[Candle]) -> tuple[FVG, ...]:
        out: list[FVG] = []
        for i in range(2, len(candles)):
            a, c = candles[i - 2], candles[i]
            if c.low > a.high:
                out.append(FVG(Direction.LONG, a.high, c.low, i))
            elif c.high < a.low:
                out.append(FVG(Direction.SHORT, c.high, a.low, i))
        return tuple(out)

    def liquidity_sweeps(self, candles: Sequence[Candle]) -> tuple[Sweep, ...]:
        swings = self.swings(candles)
        out: list[Sweep] = []
        for kind, idx, level in swings:
            for j in range(idx + 1, min(idx + 4, len(candles))):
                c = candles[j]
                if kind == "high" and c.high > level and c.close < level:
                    out.append(Sweep(Direction.SHORT, level, j))
                    break
                if kind == "low" and c.low < level and c.close > level:
                    out.append(Sweep(Direction.LONG, level, j))
                    break
        return tuple(out)

    def displacement(self, candles: Sequence[Candle], lookback: int = 5) -> float:
        if len(candles) < lookback + 1:
            return 0.0
        current = abs(candles[-1].close - candles[-1].open)
        prior = [abs(c.close - c.open) for c in candles[-lookback-1:-1]]
        avg = sum(prior) / len(prior) if prior else 0.0
        return current / avg if avg else 0.0

    def analyze(self, symbol: str, timeframe: str, candles: Sequence[Candle]) -> Signal | None:
        if len(candles) < max(8, self.pivot_window * 2 + 3):
            return None
        sweeps = self.liquidity_sweeps(candles)
        gaps = self.fair_value_gaps(candles)
        if not sweeps:
            return None
        sweep = sweeps[-1]
        latest = candles[-1]
        direction = sweep.direction
        reasons = ["liquidity_sweep"]
        score = 45.0

        recent_gap = next((g for g in reversed(gaps) if g.direction is direction and g.index >= sweep.index), None)
        if recent_gap:
            score += 20.0
            reasons.append("directional_fvg")

        disp = self.displacement(candles)
        if disp >= 1.5:
            score += 20.0
            reasons.append("displacement")
        elif disp >= 1.2:
            score += 10.0
            reasons.append("moderate_displacement")

        # A close beyond the swept level is treated as confirmation of a
        # structure shift candidate, not proof of BOS/ChoCh by itself.
        if (direction is Direction.LONG and latest.close > sweep.level) or (
            direction is Direction.SHORT and latest.close < sweep.level
        ):
            score += 15.0
            reasons.append("structure_shift_confirmation")

        if score < self.min_score:
            return None

        risk_buffer = max((latest.high - latest.low) * 0.25, latest.close * 0.0005)
        if direction is Direction.LONG:
            stop = min(sweep.level, latest.low) - risk_buffer
            entry = latest.close
            target = entry + 3.0 * (entry - stop)
        else:
            stop = max(sweep.level, latest.high) + risk_buffer
            entry = latest.close
            target = entry - 3.0 * (stop - entry)

        return Signal(
            signal_id=f"smc-{symbol}-{latest.timestamp}",
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            entry=entry,
            stop=stop,
            target=target,
            score=min(score, 100.0),
            reasons=tuple(reasons),
            metadata={"displacement_ratio": disp, "sweep_level": sweep.level},
        )
