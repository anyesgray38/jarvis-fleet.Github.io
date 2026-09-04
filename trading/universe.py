"""Broad, provider-neutral trading universe definitions."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AssetClass(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    FOREX = "forex"
    METAL = "metal"
    ENERGY = "energy"
    CRYPTO = "crypto"
    INDEX = "index"
    FUTURES = "futures"
    OPTION = "option"
    FIXED_INCOME = "fixed_income"
    RATE = "rate"
    VOLATILITY = "volatility"
    COMMODITY = "commodity"


class MarketRegime(str, Enum):
    TREND = "trend"
    RANGE = "range"
    BREAKOUT = "breakout"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRANSITION = "transition"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Instrument:
    symbol: str
    asset_class: AssetClass
    venue: str = "unknown"
    currency: str = "USD"
    quote_currency: str = "USD"
    tags: tuple[str, ...] = ()


DEFAULT_UNIVERSE: tuple[Instrument, ...] = (
    Instrument("XAUUSD", AssetClass.METAL, tags=("gold", "precious_metals")),
    Instrument("XAGUSD", AssetClass.METAL, tags=("silver", "precious_metals")),
    Instrument("EURUSD", AssetClass.FOREX, tags=("major", "fx")),
    Instrument("GBPUSD", AssetClass.FOREX, tags=("major", "fx")),
    Instrument("USDJPY", AssetClass.FOREX, tags=("major", "fx")),
    Instrument("AUDUSD", AssetClass.FOREX, tags=("major", "fx")),
    Instrument("USDCAD", AssetClass.FOREX, tags=("major", "fx")),
    Instrument("USDCHF", AssetClass.FOREX, tags=("major", "fx")),
    Instrument("NZDUSD", AssetClass.FOREX, tags=("major", "fx")),
    Instrument("EURGBP", AssetClass.FOREX, tags=("cross", "fx")),
    Instrument("EURCAD", AssetClass.FOREX, tags=("cross", "fx")),
    Instrument("BTCUSD", AssetClass.CRYPTO, tags=("bitcoin", "crypto")),
    Instrument("ETHUSD", AssetClass.CRYPTO, tags=("ethereum", "crypto")),
    Instrument("SOLUSD", AssetClass.CRYPTO, tags=("solana", "crypto")),
    Instrument("SPX500", AssetClass.INDEX, tags=("us_equity", "index")),
    Instrument("NAS100", AssetClass.INDEX, tags=("us_tech", "index")),
    Instrument("US30", AssetClass.INDEX, tags=("us_equity", "index")),
    Instrument("USOIL", AssetClass.ENERGY, tags=("crude", "energy")),
    Instrument("NATGAS", AssetClass.ENERGY, tags=("natural_gas", "energy")),
)


def find_instruments(*, asset_class: AssetClass | None = None, tag: str | None = None) -> tuple[Instrument, ...]:
    """Filter the default research universe without requiring a market-data provider."""
    return tuple(
        item for item in DEFAULT_UNIVERSE
        if (asset_class is None or item.asset_class is asset_class)
        and (tag is None or tag in item.tags)
    )
