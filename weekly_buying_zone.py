"""Find the confirmed weekly buying zone from historical OHLC candles."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
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


def classify_candle(candle: Candle) -> CandleType:
    body = abs(candle.close - candle.open)
    if 2 * body <= candle.high - candle.low:
        return CandleType.BASE
    return CandleType.RALLY if candle.close > candle.open else CandleType.DROP


def _week_start(exchange_time: datetime) -> datetime:
    midnight = exchange_time.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=midnight.weekday())


def find_weekly_buying_zone(
    weekly_candles: Iterable[TimedCandle],
    lower_timeframe_candles: Iterable[TimedCandle],
    *,
    as_of: datetime,
) -> BuyingZone | None:
    """Use prior weeks and the current week's observed low as of the given time.

    Supply one weekly candle per chart week. Lower-timeframe candles or snapshots
    must use the same instrument and price adjustment as the weekly candles.
    """
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

    line_price = anchor_low
    index = len(history) - 1
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
        return BuyingZone(
            lower=min(bar.candle.low for bar in base),
            upper=max(max(bar.candle.open, bar.candle.close) for bar in base),
            pattern=pattern,
            anchor_low=anchor_low,
            left_leg=left_leg,
            base=base,
            right_leg=right_leg,
        )

    return None
