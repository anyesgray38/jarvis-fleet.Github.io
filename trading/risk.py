"""Deterministic risk admission. No broker/network access."""
from __future__ import annotations

from dataclasses import dataclass

from .models import Signal


@dataclass(frozen=True)
class RiskPolicy:
    account_equity: float
    risk_fraction: float = 0.005
    max_position_fraction: float = 0.20
    min_rr: float = 2.0
    max_daily_loss_fraction: float = 0.02
    daily_realized_loss: float = 0.0

    def __post_init__(self) -> None:
        if self.account_equity <= 0:
            raise ValueError("account_equity must be positive")
        if not 0 < self.risk_fraction <= 0.05:
            raise ValueError("risk_fraction must be in (0, 0.05]")
        if not 0 < self.max_position_fraction <= 1:
            raise ValueError("max_position_fraction must be in (0, 1]")


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    quantity: float = 0.0
    risk_amount: float = 0.0
    reason: str = ""


class RiskEngine:
    def __init__(self, policy: RiskPolicy):
        self.policy = policy

    def size(self, signal: Signal) -> RiskDecision:
        if signal.risk_per_unit <= 0:
            return RiskDecision(False, reason="invalid stop distance")
        if signal.rr < self.policy.min_rr:
            return RiskDecision(False, reason="reward-to-risk below policy minimum")
        if self.policy.daily_realized_loss >= self.policy.account_equity * self.policy.max_daily_loss_fraction:
            return RiskDecision(False, reason="daily loss limit reached")

        risk_budget = self.policy.account_equity * self.policy.risk_fraction
        quantity = risk_budget / signal.risk_per_unit
        notional_cap = self.policy.account_equity * self.policy.max_position_fraction
        quantity = min(quantity, notional_cap / signal.entry)
        if quantity <= 0:
            return RiskDecision(False, reason="position size is zero")
        return RiskDecision(True, quantity=quantity, risk_amount=quantity * signal.risk_per_unit, reason="risk admitted")
