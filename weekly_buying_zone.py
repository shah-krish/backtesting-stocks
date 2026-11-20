"""Find confirmed weekly buying zones from historical OHLC candles."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from fractions import Fraction
from typing import Literal


NSE_TIMEZONE = timezone(timedelta(hours=5, minutes=30))
Price = Decimal | int | float | str


class CandleType(Enum):
    RALLY = "R"
    DROP = "D"
    BASE = "B"


@dataclass(frozen=True, slots=True, init=False)
class Candle:
    """OHLC prices stored as decimals to preserve the rule's exact boundary."""

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    def __init__(self, open: Price, high: Price, low: Price, close: Price):
        try:
            open_price, high_price, low_price, close_price = (
                Decimal(str(price)) for price in (open, high, low, close)
            )
        except InvalidOperation as error:
            raise ValueError("OHLC prices must be decimal numbers") from error

        prices = (open_price, high_price, low_price, close_price)
        if not all(price.is_finite() for price in prices):
            raise ValueError("OHLC prices must be finite")
        if low_price > min(open_price, close_price) or high_price < max(open_price, close_price):
            raise ValueError("The low and high must contain the open and close")

        object.__setattr__(self, "open", open_price)
        object.__setattr__(self, "high", high_price)
        object.__setattr__(self, "low", low_price)
        object.__setattr__(self, "close", close_price)


def _exchange_time(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("Candle and assessment timestamps must be timezone-aware")
    return value.astimezone(NSE_TIMEZONE)


@dataclass(frozen=True, slots=True)
class TimedCandle:
    """A candle and the interval it covers, known in full at ends_at."""

    candle: Candle
    starts_at: datetime
    ends_at: datetime

    def __post_init__(self):
        starts_at = _exchange_time(self.starts_at)
        ends_at = _exchange_time(self.ends_at)
        if starts_at >= ends_at:
            raise ValueError("A candle must end after it starts")
        object.__setattr__(self, "starts_at", starts_at)
        object.__setattr__(self, "ends_at", ends_at)


@dataclass(frozen=True, slots=True)
class BuyingZone:
    """Price bounds and the source candles in chronological order."""

    lower: Decimal
    upper: Decimal
    pattern: Literal["RBR", "DBR"]
    anchor_low: Decimal
    left_leg: TimedCandle
    base: tuple[TimedCandle, ...]
    right_leg: TimedCandle

    @property
    def full_pattern_low(self) -> Decimal:
        """Lowest wick across the leg-in, base run, and leg-out."""
        return min(self.left_leg.candle.low, self.lower, self.right_leg.candle.low)


def classify_candle(candle: Candle) -> CandleType:
    # Exact ratios keep the caller's Decimal precision out of the threshold check.
    body = abs(Fraction(candle.close) - Fraction(candle.open))
    full_range = Fraction(candle.high) - Fraction(candle.low)
    if 2 * body <= full_range:
        return CandleType.BASE
    return CandleType.RALLY if candle.close > candle.open else CandleType.DROP


def _week_start(exchange_time: datetime) -> datetime:
    midnight = exchange_time.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=midnight.weekday())


def _prepare_weekly_search(
    weekly_candles: Iterable[TimedCandle],
    lower_timeframe_candles: Iterable[TimedCandle],
    as_of: datetime,
) -> tuple[list[TimedCandle], Decimal] | None:
    as_of = _exchange_time(as_of)
    week_start = _week_start(as_of)
    anchor_low = min(
        (
            bar.candle.low
            for bar in lower_timeframe_candles
            if week_start <= bar.starts_at and bar.ends_at <= as_of
        ),
        default=None,
    )
    if anchor_low is None:
        return None

    history = sorted(
        (bar for bar in weekly_candles if bar.ends_at <= week_start),
        key=lambda bar: bar.starts_at,
    )
    if len({_week_start(bar.starts_at) for bar in history}) != len(history):
        raise ValueError("Supply at most one weekly candle per prior chart week")
    return history, anchor_low


def _find_next_zone(
    history: list[TimedCandle],
    index: int,
    *,
    line_price: Decimal,
    anchor_low: Decimal,
) -> tuple[BuyingZone, int] | None:
    """Return the next qualifying zone and the index before its leg-in."""
    while index >= 0:
        right_leg = history[index]
        index -= 1
        candle = right_leg.candle
        if not candle.low <= line_price <= candle.high:
            continue

        line_price = candle.low
        if classify_candle(candle) is not CandleType.RALLY:
            continue

        base_end = index
        while index >= 0 and classify_candle(history[index].candle) is CandleType.BASE:
            index -= 1
        if index < 0:
            return None
        if index == base_end:
            continue

        base = tuple(history[index + 1 : base_end + 1])
        left_leg = history[index]
        pattern = "RBR" if classify_candle(left_leg.candle) is CandleType.RALLY else "DBR"
        zone = BuyingZone(
            lower=min(bar.candle.low for bar in base),
            upper=max(max(bar.candle.open, bar.candle.close) for bar in base),
            pattern=pattern,
            anchor_low=anchor_low,
            left_leg=left_leg,
            base=base,
            right_leg=right_leg,
        )
        index -= 1  # Both accepted and rejected patterns resume before the leg-in.
        if candle.close > zone.upper:
            return zone, index
        line_price = zone.full_pattern_low

    return None


def find_weekly_buying_zone(
    weekly_candles: Iterable[TimedCandle],
    lower_timeframe_candles: Iterable[TimedCandle],
    *,
    as_of: datetime,
) -> BuyingZone | None:
    """Return the first qualifying zone before overlap refinement.

    Supply one weekly candle per chart week. Lower-timeframe candles or snapshots
    must use the same instrument and price adjustment as the weekly candles.
    """
    search = _prepare_weekly_search(weekly_candles, lower_timeframe_candles, as_of)
    if search is None:
        return None
    history, anchor_low = search
    match = _find_next_zone(history, len(history) - 1, line_price=anchor_low, anchor_low=anchor_low)
    return match[0] if match is not None else None


def find_weekly_buying_zones(
    weekly_candles: Iterable[TimedCandle],
    lower_timeframe_candles: Iterable[TimedCandle],
    *,
    as_of: datetime,
) -> list[BuyingZone]:
    """Return valid zones in search order after resolving candidate overlaps.

    Use the same as-of inputs as find_weekly_buying_zone. Each returned zone's
    anchor_low is the observed current-week low that started the initial search.
    """
    search = _prepare_weekly_search(weekly_candles, lower_timeframe_candles, as_of)
    if search is None:
        return []
    history, anchor_low = search
    match = _find_next_zone(history, len(history) - 1, line_price=anchor_low, anchor_low=anchor_low)
    if match is None:
        return []

    candidate, next_index = match
    valid_zones = []
    while match := _find_next_zone(
        history, next_index, line_price=candidate.full_pattern_low, anchor_low=anchor_low
    ):
        older, next_index = match
        if candidate.upper < older.lower or older.upper < candidate.lower:
            valid_zones.append(candidate)
            candidate = older
        elif older.lower <= candidate.lower:
            candidate = older

    valid_zones.append(candidate)
    return valid_zones
