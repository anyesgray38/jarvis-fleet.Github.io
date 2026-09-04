"""In-memory paper broker used for deterministic bot tests and dry runs."""
from __future__ import annotations

from dataclasses import dataclass

from .models import OrderIntent, Position


@dataclass(frozen=True)
class Fill:
    order_id: str
    symbol: str
    quantity: float
    price: float


class PaperBroker:
    live = False

    def __init__(self):
        self.positions: dict[str, Position] = {}
        self.fills: list[Fill] = []

    def submit(self, order: OrderIntent) -> Fill:
        if order.quantity <= 0:
            raise ValueError("quantity must be positive")
        if order.symbol in self.positions:
            raise ValueError("one position per symbol is supported in MVP")
        fill = Fill(order.client_order_id, order.symbol, order.quantity, order.entry)
        self.fills.append(fill)
        self.positions[order.symbol] = Position(
            order.symbol, order.direction, order.quantity,
            order.entry, order.stop, order.target,
        )
        return fill

    def mark(self, symbol: str, price: float) -> float:
        position = self.positions.get(symbol)
        if position is None:
            return 0.0
        return position.unrealized_pnl(price)

    def close(self, symbol: str, price: float) -> float:
        position = self.positions.pop(symbol, None)
        if position is None:
            return 0.0
        pnl = position.unrealized_pnl(price)
        position.realized_pnl = pnl
        return pnl
