"""Deterministic ICT framework features for research and paper testing.

The implementation turns the structured ICT knowledge packet into observable
features.  It does not claim that an ICT pattern predicts price, and it never
places live orders.  A setup must pass the complete
``bias -> location -> draw -> level -> time -> trigger`` sequence before a
signal is emitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

from .ict_knowledge import load_ict_knowledge
from .models import Candle, Direction, Signal


@dataclass(frozen=True)
class DealingRange:
    low: float
    high: float

    @property
    def equilibrium(self) -> float:
        return (self.low + self.high) / 2

    def zone(self, price: float) -> str:
        if price < self.equilibrium:
            return "discount"
        if price > self.equilibrium:
            return "premium"
        return "equilibrium"

    def retracement(self, price: float, direction: Direction) -> float:
        span = self.high - self.low
        if span <= 0:
            return 0.0
        return ((self.high - price) / span) if direction is Direction.LONG else ((price - self.low) / span)


@dataclass(frozen=True)
class SwingPoint:
    kind: str
    index: int
    price: float
    label: str


@dataclass(frozen=True)
class LiquidityPool:
    kind: str
    level: float
    index: int
    source: str
    range_role: str


@dataclass(frozen=True)
class LiquidityEvent:
    event: str
    response: Direction
    pool: LiquidityPool
    index: int
    close: float


@dataclass(frozen=True)
class Imbalance:
    kind: str
    direction: Direction
    low: float
    high: float
    index: int
    qualified: bool = True

    @property
    def consequent_encroachment(self) -> float:
        return (self.low + self.high) / 2


@dataclass(frozen=True)
class PriceZone:
    kind: str
    direction: Direction
    low: float
    high: float
    index: int


@dataclass(frozen=True)
class ICTStep:
    name: str
    passed: bool
    detail: str


@dataclass
class ICTFeatures:
    dealing_range: DealingRange | None
    swings: tuple[SwingPoint, ...]
    liquidity_pools: tuple[LiquidityPool, ...]
    liquidity_events: tuple[LiquidityEvent, ...]
    imbalances: tuple[Imbalance, ...]
    volume_imbalances: tuple[Imbalance, ...]
    suspension_blocks: tuple[PriceZone, ...]
    vacuum_blocks: tuple[Imbalance, ...]
    inverted_imbalances: tuple[Imbalance, ...]
    balanced_price_ranges: tuple[Imbalance, ...]
    order_blocks: tuple[PriceZone, ...]
    breaker_blocks: tuple[PriceZone, ...]
    mitigation_blocks: tuple[PriceZone, ...]
    rejection_blocks: tuple[PriceZone, ...]
    propulsion_blocks: tuple[PriceZone, ...]
    hidden_blocks: tuple[PriceZone, ...]
    market_structure_shift: Direction | None
    cisd: Direction | None
    session: str | None
    asian_range: DealingRange | None
    cbdr_range: DealingRange | None
    opening_gaps: tuple[Imbalance, ...]


@dataclass(frozen=True)
class ICTReport:
    strategy_id: str
    valid: bool
    bias: Direction | None
    steps: tuple[ICTStep, ...]
    features: ICTFeatures
    signal: Signal | None
    reason: str


_SESSION_WINDOWS = {
    "asian": (0, 5),
    "london": (7, 10),
    "new_york": (12, 15),
    "london_close": (15, 17),
}
_KILLZONES = {"london", "new_york", "london_close"}
_DETAILED_STRATEGIES = {"ote", "order_block", "turtle_soup", "silver_bullet", "power_of_3", "unicorn_smt", "smc"}


def _body_direction(candle: Candle) -> Direction:
    return Direction.LONG if candle.close >= candle.open else Direction.SHORT


def _body_size(candle: Candle) -> float:
    return abs(candle.close - candle.open)


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _in_window(hour: int, start: int, end: int) -> bool:
    return start <= hour < end


class ICTAnalyzer:
    """Extract ICT features and gate paper-only setup research."""

    def __init__(self, pivot_window: int = 2, min_displacement: float = 1.5):
        if pivot_window < 1:
            raise ValueError("pivot_window must be positive")
        if min_displacement <= 0:
            raise ValueError("min_displacement must be positive")
        self.pivot_window = pivot_window
        self.min_displacement = min_displacement

    @staticmethod
    def supported_strategy_ids() -> tuple[str, ...]:
        return tuple(load_ict_knowledge()["strategies"])

    @staticmethod
    def framework_coverage() -> dict[str, tuple[str, ...]]:
        return {
            "foundation_gate": ("bias", "location", "draw", "level", "time", "trigger"),
            "structure": ("STH", "ITH", "LTH", "STL", "ITL", "LTL", "MSS", "CISD"),
            "liquidity": ("BSL", "SSL", "ERL", "IRL", "sweep", "run", "equal_highs", "equal_lows"),
            "imbalances": ("FVG", "BISI", "SIBI", "IFVG", "BPR", "volume_imbalance", "suspension_block", "vacuum_block"),
            "price_delivery": ("OB", "breaker", "mitigation", "rejection", "propulsion", "hidden_ob", "premium_discount", "OTE", "CE"),
            "time": ("asian", "london", "new_york", "london_close", "killzone", "CBDR", "macro", "NWOG", "NDOG"),
            "strategies": tuple(load_ict_knowledge()["strategies"]),
        }

    def swings(self, candles: Sequence[Candle]) -> tuple[SwingPoint, ...]:
        """Return nested short-, intermediate-, and long-term pivots."""
        found: dict[tuple[str, int], SwingPoint] = {}
        for window, high_label, low_label in ((1, "STH", "STL"), (2, "ITH", "ITL"), (4, "LTH", "LTL")):
            for i in range(window, len(candles) - window):
                left = candles[i - window:i]
                right = candles[i + 1:i + window + 1]
                if candles[i].high > max(c.high for c in left + right):
                    found[("high", i)] = SwingPoint("high", i, candles[i].high, high_label)
                if candles[i].low < min(c.low for c in left + right):
                    found[("low", i)] = SwingPoint("low", i, candles[i].low, low_label)
        return tuple(sorted(found.values(), key=lambda point: (point.index, point.kind)))

    def dealing_range(self, candles: Sequence[Candle]) -> DealingRange | None:
        if not candles:
            return None
        return DealingRange(min(c.low for c in candles), max(c.high for c in candles))

    def displacement_ratio(self, candles: Sequence[Candle], index: int | None = None, lookback: int = 5) -> float:
        end = len(candles) - 1 if index is None else index
        if end < 1 or end >= len(candles):
            return 0.0
        prior = [_body_size(c) for c in candles[max(0, end - lookback):end]]
        average = sum(prior) / len(prior) if prior else 0.0
        return _body_size(candles[end]) / average if average else 0.0

    def imbalances(self, candles: Sequence[Candle]) -> tuple[Imbalance, ...]:
        result: list[Imbalance] = []
        for i in range(2, len(candles)):
            first, middle, third = candles[i - 2], candles[i - 1], candles[i]
            qualified = self.displacement_ratio(candles, i - 1) >= self.min_displacement
            if third.low > first.high:
                result.append(Imbalance("BISI", Direction.LONG, first.high, third.low, i, qualified))
            elif third.high < first.low:
                result.append(Imbalance("SIBI", Direction.SHORT, third.high, first.low, i, qualified))
        return tuple(result)

    def volume_imbalances(self, candles: Sequence[Candle]) -> tuple[Imbalance, ...]:
        """Detect body-to-body gaps where wick overlap is allowed."""
        result: list[Imbalance] = []
        for index in range(1, len(candles)):
            previous, current = candles[index - 1], candles[index]
            previous_low, previous_high = min(previous.open, previous.close), max(previous.open, previous.close)
            current_low, current_high = min(current.open, current.close), max(current.open, current.close)
            if current_low > previous_high:
                result.append(Imbalance("volume_imbalance", Direction.LONG, previous_high, current_low, index))
            elif current_high < previous_low:
                result.append(Imbalance("volume_imbalance", Direction.SHORT, current_high, previous_low, index))
        return tuple(result)

    def suspension_blocks(self, candles: Sequence[Candle], volume_imbalances: Iterable[Imbalance] | None = None) -> tuple[PriceZone, ...]:
        gaps = tuple(volume_imbalances) if volume_imbalances is not None else self.volume_imbalances(candles)
        result: list[PriceZone] = []
        for left in gaps:
            for right in gaps:
                if right.index != left.index + 2 or right.direction is not left.direction:
                    continue
                middle = candles[left.index + 1]
                low, high = min(middle.open, middle.close), max(middle.open, middle.close)
                result.append(PriceZone("suspension_block", left.direction, low, high, left.index + 1))
        return tuple(result)

    def vacuum_blocks(self, candles: Sequence[Candle]) -> tuple[Imbalance, ...]:
        """Detect opening gaps beyond the prior candle's full range."""
        result: list[Imbalance] = []
        for index in range(1, len(candles)):
            previous, current = candles[index - 1], candles[index]
            if current.open > previous.high:
                result.append(Imbalance("vacuum_block", Direction.LONG, previous.high, current.open, index))
            elif current.open < previous.low:
                result.append(Imbalance("vacuum_block", Direction.SHORT, current.open, previous.low, index))
        return tuple(result)

    def liquidity_pools(self, candles: Sequence[Candle], *, tolerance: float | None = None) -> tuple[LiquidityPool, ...]:
        points = self.swings(candles)
        if not points:
            return ()
        span = max(c.high for c in candles) - min(c.low for c in candles)
        tol = tolerance if tolerance is not None else max(span * 0.002, candles[-1].close * 0.0005)
        highs = [point for point in points if point.kind == "high"]
        lows = [point for point in points if point.kind == "low"]
        high_values = [point.price for point in highs]
        low_values = [point.price for point in lows]
        result: list[LiquidityPool] = []
        high_edge = max(c.high for c in candles)
        low_edge = min(c.low for c in candles)
        for point in highs:
            source = "equal_highs" if sum(abs(point.price - value) <= tol for value in high_values) > 1 else "swing_high"
            role = "ERL" if abs(point.price - high_edge) <= tol else "IRL"
            result.append(LiquidityPool("BSL", point.price, point.index, source, role))
        for point in lows:
            source = "equal_lows" if sum(abs(point.price - value) <= tol for value in low_values) > 1 else "swing_low"
            role = "ERL" if abs(point.price - low_edge) <= tol else "IRL"
            result.append(LiquidityPool("SSL", point.price, point.index, source, role))
        return tuple(sorted(result, key=lambda pool: (pool.index, pool.kind)))

    def liquidity_events(self, candles: Sequence[Candle], pools: Iterable[LiquidityPool] | None = None) -> tuple[LiquidityEvent, ...]:
        pools = tuple(pools) if pools is not None else self.liquidity_pools(candles)
        result: list[LiquidityEvent] = []
        for pool in pools:
            for index in range(pool.index + 1, min(len(candles), pool.index + 5)):
                candle = candles[index]
                if pool.kind == "BSL" and candle.high > pool.level:
                    event = "sweep" if candle.close < pool.level else "run"
                    response = Direction.SHORT if event == "sweep" else Direction.LONG
                    result.append(LiquidityEvent(event, response, pool, index, candle.close))
                    break
                if pool.kind == "SSL" and candle.low < pool.level:
                    event = "sweep" if candle.close > pool.level else "run"
                    response = Direction.LONG if event == "sweep" else Direction.SHORT
                    result.append(LiquidityEvent(event, response, pool, index, candle.close))
                    break
        return tuple(sorted(result, key=lambda event: event.index))

    def inverted_imbalances(self, candles: Sequence[Candle], imbalances: Iterable[Imbalance] | None = None) -> tuple[Imbalance, ...]:
        gaps = tuple(imbalances) if imbalances is not None else self.imbalances(candles)
        result: list[Imbalance] = []
        for gap in gaps:
            for index in range(gap.index, len(candles)):
                close = candles[index].close
                if gap.direction is Direction.LONG and close < gap.low:
                    result.append(Imbalance("IFVG", Direction.SHORT, gap.low, gap.high, index, gap.qualified))
                    break
                if gap.direction is Direction.SHORT and close > gap.high:
                    result.append(Imbalance("IFVG", Direction.LONG, gap.low, gap.high, index, gap.qualified))
                    break
        return tuple(result)

    def balanced_price_ranges(self, imbalances: Iterable[Imbalance]) -> tuple[Imbalance, ...]:
        gaps = tuple(imbalances)
        result: list[Imbalance] = []
        for left_index, left in enumerate(gaps):
            for right in gaps[left_index + 1:]:
                if left.direction is right.direction:
                    continue
                low = max(left.low, right.low)
                high = min(left.high, right.high)
                if low < high:
                    result.append(Imbalance("BPR", left.direction, low, high, max(left.index, right.index), left.qualified and right.qualified))
        return tuple(result)

    def order_blocks(self, candles: Sequence[Candle]) -> tuple[PriceZone, ...]:
        result: list[PriceZone] = []
        for i in range(1, len(candles)):
            direction = _body_direction(candles[i])
            if self.displacement_ratio(candles, i) < self.min_displacement:
                continue
            opposing = candles[i - 1]
            if _body_direction(opposing) is direction:
                continue
            result.append(PriceZone("OB", direction, opposing.low, opposing.high, i - 1))
        return tuple(result)

    def rejection_blocks(self, candles: Sequence[Candle], events: Iterable[LiquidityEvent] | None = None) -> tuple[PriceZone, ...]:
        result: list[PriceZone] = []
        for event in events if events is not None else self.liquidity_events(candles):
            candle = candles[event.index]
            body_low, body_high = min(candle.open, candle.close), max(candle.open, candle.close)
            if event.response is Direction.LONG:
                result.append(PriceZone("rejection", Direction.LONG, candle.low, body_low, event.index))
            else:
                result.append(PriceZone("rejection", Direction.SHORT, body_high, candle.high, event.index))
        return tuple(result)

    def _derived_blocks(self, candles: Sequence[Candle], order_blocks: tuple[PriceZone, ...], events: tuple[LiquidityEvent, ...]) -> tuple[tuple[PriceZone, ...], ...]:
        breakers: list[PriceZone] = []
        mitigations: list[PriceZone] = []
        propulsion: list[PriceZone] = []
        for block in order_blocks:
            invalidated = [i for i in range(block.index + 1, len(candles)) if (candles[i].close < block.low if block.direction is Direction.LONG else candles[i].close > block.high)]
            if not invalidated:
                continue
            event_indices = {event.index for event in events}
            target = PriceZone("breaker", Direction.SHORT if block.direction is Direction.LONG else Direction.LONG, block.low, block.high, invalidated[0])
            (breakers if any(i in event_indices for i in invalidated) else mitigations).append(target if any(i in event_indices for i in invalidated) else PriceZone("mitigation", target.direction, target.low, target.high, target.index))
        for block in order_blocks:
            for i in range(block.index + 1, len(candles) - 1):
                if candles[i].low <= block.high and candles[i].high >= block.low:
                    next_candle = candles[i + 1]
                    if (block.direction is Direction.LONG and next_candle.close > candles[i].high) or (block.direction is Direction.SHORT and next_candle.close < candles[i].low):
                        propulsion.append(PriceZone("propulsion", block.direction, block.low, block.high, i))
                        break
        return tuple(breakers), tuple(mitigations), tuple(propulsion)

    def hidden_blocks(self, candles: Sequence[Candle]) -> tuple[PriceZone, ...]:
        result: list[PriceZone] = []
        for i in range(1, len(candles)):
            if _body_direction(candles[i]) is not _body_direction(candles[i - 1]):
                continue
            low = max(candles[i].low, candles[i - 1].low)
            high = min(candles[i].high, candles[i - 1].high)
            if low < high:
                result.append(PriceZone("hidden_ob", _body_direction(candles[i]), low, high, i))
        return tuple(result)

    def market_structure_shift(self, candles: Sequence[Candle], swings: Iterable[SwingPoint] | None = None) -> Direction | None:
        points = tuple(swings) if swings is not None else self.swings(candles)
        if not candles or not points:
            return None
        latest = candles[-1]
        highs = [point for point in points if point.kind == "high" and point.index < len(candles) - 1]
        lows = [point for point in points if point.kind == "low" and point.index < len(candles) - 1]
        if highs and latest.close > highs[-1].price and self.displacement_ratio(candles) >= 1.0:
            return Direction.LONG
        if lows and latest.close < lows[-1].price and self.displacement_ratio(candles) >= 1.0:
            return Direction.SHORT
        return None

    def cisd(self, candles: Sequence[Candle]) -> Direction | None:
        if len(candles) < 2:
            return None
        previous, current = candles[-2], candles[-1]
        if _body_direction(previous) is Direction.SHORT and current.close > previous.open:
            return Direction.LONG
        if _body_direction(previous) is Direction.LONG and current.close < previous.open:
            return Direction.SHORT
        return None

    def session(self, timestamp: str) -> str | None:
        parsed = _parse_timestamp(timestamp)
        if parsed is None:
            return None
        hour = parsed.astimezone(timezone.utc).hour
        for name, (start, end) in _SESSION_WINDOWS.items():
            if _in_window(hour, start, end):
                return name
        return None

    def is_killzone(self, timestamp: str) -> bool:
        return self.session(timestamp) in _KILLZONES

    def is_macro(self, timestamp: str) -> bool:
        parsed = _parse_timestamp(timestamp)
        if parsed is None:
            return False
        return parsed.astimezone(timezone.utc).minute in {0, 1, 2, 3, 4, 5, 30, 31, 32, 33, 34, 35}

    def asian_range(self, candles: Sequence[Candle]) -> DealingRange | None:
        asian = [candle for candle in candles if self.session(candle.timestamp) == "asian"]
        return DealingRange(min(c.low for c in asian), max(c.high for c in asian)) if asian else None

    def cbdr_range(self, candles: Sequence[Candle], start_hour: int = 0, end_hour: int = 5) -> DealingRange | None:
        """Return a configurable UTC CBDR range; callers can supply market-local hours."""
        selected = []
        for candle in candles:
            parsed = _parse_timestamp(candle.timestamp)
            if parsed is not None and _in_window(parsed.astimezone(timezone.utc).hour, start_hour, end_hour):
                selected.append(candle)
        return DealingRange(min(c.low for c in selected), max(c.high for c in selected)) if selected else None

    def opening_gaps(self, candles: Sequence[Candle]) -> tuple[Imbalance, ...]:
        result: list[Imbalance] = []
        previous_time: datetime | None = None
        for index, candle in enumerate(candles):
            current_time = _parse_timestamp(candle.timestamp)
            if index and current_time and previous_time and current_time.date() != previous_time.date():
                previous = candles[index - 1]
                gap: Imbalance | None = None
                if candle.open > previous.close:
                    gap = Imbalance("NDOG", Direction.LONG, previous.close, candle.open, index)
                elif candle.open < previous.close:
                    gap = Imbalance("NDOG", Direction.SHORT, candle.open, previous.close, index)
                if gap is not None:
                    if current_time.weekday() == 0:
                        gap = Imbalance("NWOG", gap.direction, gap.low, gap.high, index)
                    result.append(gap)
            previous_time = current_time
        return tuple(result)

    def smt_divergence(self, candles: Sequence[Candle], correlated: Sequence[Candle]) -> Direction | None:
        if len(candles) < 2 or len(correlated) < 2:
            return None
        left, right = candles[-2:], correlated[-2:]
        if left[-1].low < left[0].low and right[-1].low >= right[0].low:
            return Direction.LONG
        if left[-1].high > left[0].high and right[-1].high <= right[0].high:
            return Direction.SHORT
        return None

    def extract(self, candles: Sequence[Candle]) -> ICTFeatures:
        swings = self.swings(candles)
        pools = self.liquidity_pools(candles)
        events = self.liquidity_events(candles, pools)
        imbalances = self.imbalances(candles)
        volume_imbalances = self.volume_imbalances(candles)
        blocks = self.order_blocks(candles)
        breakers, mitigations, propulsion = self._derived_blocks(candles, blocks, events)
        return ICTFeatures(
            dealing_range=self.dealing_range(candles),
            swings=swings,
            liquidity_pools=pools,
            liquidity_events=events,
            imbalances=imbalances,
            volume_imbalances=volume_imbalances,
            suspension_blocks=self.suspension_blocks(candles, volume_imbalances),
            vacuum_blocks=self.vacuum_blocks(candles),
            inverted_imbalances=self.inverted_imbalances(candles, imbalances),
            balanced_price_ranges=self.balanced_price_ranges(imbalances),
            order_blocks=blocks,
            breaker_blocks=breakers,
            mitigation_blocks=mitigations,
            rejection_blocks=self.rejection_blocks(candles, events),
            propulsion_blocks=propulsion,
            hidden_blocks=self.hidden_blocks(candles),
            market_structure_shift=self.market_structure_shift(candles, swings),
            cisd=self.cisd(candles),
            session=self.session(candles[-1].timestamp) if candles else None,
            asian_range=self.asian_range(candles),
            cbdr_range=self.cbdr_range(candles),
            opening_gaps=self.opening_gaps(candles),
        )

    def analyze(self, symbol: str, timeframe: str, candles: Sequence[Candle], strategy_id: str = "smc") -> ICTReport:
        if strategy_id not in self.supported_strategy_ids():
            raise KeyError(f"unknown ICT strategy: {strategy_id}")
        features = self.extract(candles)
        latest = candles[-1] if candles else None
        bias = features.market_structure_shift or features.cisd
        if bias is None and len(features.swings) >= 4:
            highs = [point.price for point in features.swings if point.kind == "high"]
            lows = [point.price for point in features.swings if point.kind == "low"]
            if len(highs) >= 2 and len(lows) >= 2:
                if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
                    bias = Direction.LONG
                elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
                    bias = Direction.SHORT

        steps: list[ICTStep] = []
        steps.append(ICTStep("bias", bias is not None, f"{bias.value if bias else 'no directional structure'}"))
        location = features.dealing_range.zone(latest.close) if latest and features.dealing_range else None
        location_ok = bool(bias and location == ("discount" if bias is Direction.LONG else "premium"))
        steps.append(ICTStep("location", location_ok, location or "no dealing range"))
        draw_kind = "BSL" if bias is Direction.LONG else "SSL" if bias is Direction.SHORT else ""
        draw_candidates = [pool for pool in features.liquidity_pools if pool.kind == draw_kind and latest and ((bias is Direction.LONG and pool.level > latest.close) or (bias is Direction.SHORT and pool.level < latest.close))]
        draw = min(draw_candidates, key=lambda pool: abs(pool.level - latest.close)) if draw_candidates else None
        steps.append(ICTStep("draw", draw is not None, f"{draw.source if draw else 'no aligned liquidity pool'}"))

        level_candidates = [gap for gap in features.imbalances if gap.qualified and bias and gap.direction is bias]
        level = level_candidates[-1] if level_candidates else None
        if level is None and bias:
            candidates = [block for block in features.order_blocks if block.direction is bias]
            level = candidates[-1] if candidates else None
        steps.append(ICTStep("level", level is not None, level.kind if level else "no qualified PDA/FVG"))

        session_ok = features.session in _SESSION_WINDOWS
        steps.append(ICTStep("time", session_ok, features.session or "timestamp/session unavailable"))

        sweep_ok = any(event.event == "sweep" and bias and event.response is bias for event in features.liquidity_events)
        mss_ok = bool(bias and features.market_structure_shift is bias)
        cisd_ok = bool(bias and features.cisd is bias)
        fvg_ok = bool(level and isinstance(level, Imbalance))
        if strategy_id == "turtle_soup":
            trigger_ok = sweep_ok and (mss_ok or cisd_ok)
        elif strategy_id == "silver_bullet":
            trigger_ok = fvg_ok and features.session in _KILLZONES
        elif strategy_id == "power_of_3":
            trigger_ok = features.session in _KILLZONES and bool(features.asian_range) and (sweep_ok or mss_ok)
        elif strategy_id == "unicorn_smt":
            trigger_ok = bool(features.breaker_blocks and features.imbalances)
        elif strategy_id in {"ote", "order_block"}:
            retracement = features.dealing_range.retracement(latest.close, bias) if latest and features.dealing_range and bias else 0.0
            trigger_ok = (0.62 <= retracement <= 0.79 if strategy_id == "ote" else bool(level)) and (mss_ok or cisd_ok)
        else:
            trigger_ok = sweep_ok and fvg_ok and (mss_ok or cisd_ok)
        steps.append(ICTStep("trigger", trigger_ok, f"sweep={sweep_ok} mss={mss_ok} cisd={cisd_ok} fvg={fvg_ok}"))

        valid = bool(latest and bias and all(step.passed for step in steps))
        signal = None
        if valid and draw and level:
            entry = level.consequent_encroachment if isinstance(level, Imbalance) else (level.low + level.high) / 2
            buffer = max((latest.high - latest.low) * 0.25, latest.close * 0.0005)
            stop = (min(level.low if isinstance(level, Imbalance) else level.low, latest.low) - buffer) if bias is Direction.LONG else (max(level.high if isinstance(level, Imbalance) else level.high, latest.high) + buffer)
            target = draw.level
            if (bias is Direction.LONG and not (stop < entry < target)) or (bias is Direction.SHORT and not (target < entry < stop)):
                valid = False
            else:
                signal = Signal(
                    signal_id=f"ict-{strategy_id}-{symbol}-{latest.timestamp}", symbol=symbol, timeframe=timeframe,
                    direction=bias, entry=entry, stop=stop, target=target, score=round(100 * sum(step.passed for step in steps) / len(steps), 2),
                    reasons=tuple(f"{step.name}:{step.detail}" for step in steps),
                    metadata={"ict_strategy": strategy_id, "framework_sequence": [step.name for step in steps], "research_only": True, "draw": draw.source},
                )
        reason = "all ICT framework gates passed" if valid else next((f"{step.name}: {step.detail}" for step in steps if not step.passed), "insufficient candles")
        return ICTReport(strategy_id, valid, bias, tuple(steps), features, signal, reason)
