"""Small, serializable trading domain contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"

    @property
    def sign(self) -> int:
        return 1 if self is Direction.LONG else -1


@dataclass(frozen=True)
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def __post_init__(self) -> None:
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC values must be positive")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("invalid candle range")


@dataclass(frozen=True)
class Signal:
    signal_id: str
    symbol: str
    timeframe: str
    direction: Direction
    entry: float
    stop: float
    target: float
    score: float
    reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry - self.stop)

    @property
    def reward_per_unit(self) -> float:
        return abs(self.target - self.entry)

    @property
    def rr(self) -> float:
        risk = self.risk_per_unit
        return self.reward_per_unit / risk if risk else 0.0


@dataclass(frozen=True)
class OrderIntent:
    client_order_id: str
    symbol: str
    direction: Direction
    quantity: float
    entry: float
    stop: float
    target: float
    signal_id: str


@dataclass
class Position:
    symbol: str
    direction: Direction
    quantity: float
    entry: float
    stop: float
    target: float
    realized_pnl: float = 0.0

    def unrealized_pnl(self, mark: float) -> float:
        return (mark - self.entry) * self.quantity * self.direction.sign
