"""Governed trading bot state machine.

The bot defaults to paper execution. Live execution is deliberately not
implemented here; a future broker adapter must be admitted by AEGIS policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .models import Candle, OrderIntent, Signal
from .paper import PaperBroker
from .risk import RiskEngine, RiskPolicy
from .smc import SMCAnalyzer


class BotState(str, Enum):
    STOPPED = "stopped"
    SCANNING = "scanning"
    SIGNAL = "signal"
    RISK_REJECTED = "risk_rejected"
    PAPER_FILLED = "paper_filled"
    ERROR = "error"


@dataclass(frozen=True)
class BotEvent:
    state: BotState
    message: str
    signal_id: str | None = None


class TradingBot:
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        *,
        analyzer: SMCAnalyzer | None = None,
        risk_policy: RiskPolicy | None = None,
        broker: PaperBroker | None = None,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.analyzer = analyzer or SMCAnalyzer()
        self.risk = RiskEngine(risk_policy or RiskPolicy(account_equity=10_000.0))
        self.broker = broker or PaperBroker()
        self.state = BotState.STOPPED
        self.events: list[BotEvent] = []

    def _event(self, state: BotState, message: str, signal_id: str | None = None) -> None:
        self.state = state
        self.events.append(BotEvent(state, message, signal_id))

    def scan(self, candles: Sequence[Candle]) -> Signal | None:
        self._event(BotState.SCANNING, f"scanning {self.symbol} {self.timeframe}")
        signal = self.analyzer.analyze(self.symbol, self.timeframe, candles)
        if signal is None:
            self._event(BotState.STOPPED, "no admitted setup")
            return None
        self._event(BotState.SIGNAL, f"setup score={signal.score:.1f} rr={signal.rr:.2f}", signal.signal_id)
        return signal

    def paper_step(self, candles: Sequence[Candle]) -> Signal | None:
        signal = self.scan(candles)
        if signal is None:
            return None
        decision = self.risk.size(signal)
        if not decision.approved:
            self._event(BotState.RISK_REJECTED, decision.reason, signal.signal_id)
            return signal
        order = OrderIntent(
            client_order_id=f"paper-{signal.signal_id}",
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=decision.quantity,
            entry=signal.entry,
            stop=signal.stop,
            target=signal.target,
            signal_id=signal.signal_id,
        )
        self.broker.submit(order)
        self._event(BotState.PAPER_FILLED, f"paper fill qty={decision.quantity:.6f}", signal.signal_id)
        return signal
