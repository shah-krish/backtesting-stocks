"""Synthetic checks against the weekly strategy's published rules."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from unittest import TestCase

from weekly_buying_zone import (
    Candle, CandleType, NSE_TIMEZONE, TimedCandle, classify_candle,
    find_weekly_buying_zone, find_weekly_buying_zones,
)


FIRST_OPEN = datetime(2026, 1, 5, 9, 15, tzinfo=NSE_TIMEZONE)


def weekly_history(prices):
    bars = []
    for week, ohlc in enumerate(prices):
        start = FIRST_OPEN + timedelta(weeks=week)
        bars.append(TimedCandle(Candle(*ohlc), start, start + timedelta(days=4, hours=6)))
    return bars


def observation(start, minutes, low):
    return TimedCandle(Candle(low, low + 1, low, low), start, start + timedelta(minutes=minutes))


class WeeklyZoneAuditTests(TestCase):
    def test_small_tick_ranges_against_integer_classification(self):
        tick = Decimal("0.05")
        with localcontext(prec=28):
            for width in range(13):
                for opening in range(width + 1):
                    for closing in range(width + 1):
                        # Compute the expected label in whole ticks before
                        # converting the OHLC prices to decimal currency.
                        expected = CandleType.BASE
                        if 2 * abs(closing - opening) > width:
                            expected = CandleType.RALLY if closing > opening else CandleType.DROP
                        candle = Candle(100 + opening * tick, 100 + width * tick, 100, 100 + closing * tick)
                        with self.subTest(width=width, opening=opening, closing=closing):
                            self.assertEqual(classify_candle(candle), expected)

    def test_refinement_with_rejections_inserted_at_each_search_position(self):
        # Prices are in search order. Expected indices identify individual
        # patterns even when two zones have identical boundaries.
        bounds = {"A": (100, 106), "B": (90, 95), "C": (88, 102),
                  "D": (100, 103), "E": (106, 109), "X": (92, 99)}
        cases = [
            ("ABC", [0, 2]),  # Final C overlaps saved A as well as active B.
            ("AD", [1]),      # Equal marked lows.
            ("AA", [1]),      # Identical boundaries, different source candles.
            ("AE", [0]),      # Endpoint touch, newer zone wins.
            ("EA", [1]),      # Endpoint touch, older zone wins.
            ("ABA", [0, 1, 2]),  # All three saved, including both occurrences of A.
        ]
        for labels, winners in cases:
            for insertion in [None, *range(len(labels) + 1)]:
                with self.subTest(labels=labels, rejected_at=insertion):
                    order = list(enumerate(labels))
                    if insertion is not None:
                        order.insert(insertion, (None, "X"))
                    prices = []
                    right_week = {}
                    for source, label in reversed(order):
                        low, top = bounds[label]
                        # Mix DBR and RBR. Every leg-out intersects both
                        # the initial line (110) and every restart line (70).
                        leg_in = (110, 110, 80, 80) if source == 0 else (80, 110, 80, 110)
                        close = top if label == "X" else top + 1
                        prices.extend([leg_in, (top, top + 1, low, top), (70, 110, 70, close)])
                        right_week[source] = len(prices) - 1
                    history = weekly_history(prices)
                    bar = observation(FIRST_OPEN + timedelta(weeks=len(history)), 60, 110)
                    first = find_weekly_buying_zone(reversed(history), [bar], as_of=bar.ends_at)
                    self.assertIsNotNone(first)
                    self.assertEqual(first.right_leg, history[right_week[0]])
                    zones = find_weekly_buying_zones(reversed(history), [bar], as_of=bar.ends_at)
                    self.assertEqual([z.right_leg for z in zones], [history[right_week[i]] for i in winners])
                    self.assertEqual([(z.lower, z.upper) for z in zones], [bounds[labels[i]] for i in winners])

    def test_partial_bar_reveals_new_low_only_at_its_own_timestamp(self):
        history = weekly_history([(110, 111, 98, 100), (102, 108, 99, 104), (105, 116, 103, 115)])
        start = FIRST_OPEN + timedelta(weeks=3)
        prior = observation(start, 60, 112)
        snapshot = observation(prior.ends_at, 15, 107)
        completed = observation(prior.ends_at, 60, 90)
        # Supply all observations at every assessment, including the completed
        # bar whose lower low must only become visible at its own close.
        observations = [completed, prior, snapshot]
        for as_of, expected_anchor in [
            (snapshot.ends_at - timedelta(microseconds=1), 112),
            (snapshot.ends_at, 107),
            (completed.ends_at, None),
        ]:
            with self.subTest(as_of=as_of):
                cutoff = as_of.astimezone(timezone.utc)
                first = find_weekly_buying_zone(history, observations, as_of=cutoff)
                zones = find_weekly_buying_zones(history, observations, as_of=cutoff)
                if expected_anchor is None:
                    self.assertIsNone(first)
                    self.assertEqual(zones, [])
                else:
                    self.assertIsNotNone(first)
                    self.assertEqual((first.anchor_low, first.right_leg), (expected_anchor, history[-1]))
                    self.assertEqual(zones, [first])

    def test_rally_just_above_half_range_at_default_decimal_precision(self):
        # Exact finite decimal just above 105. The body exceeds half the
        # range and the close clears the base body top of 104.
        close = "105.0000000000000000000000000001"
        history = weekly_history([(110, 110, 98, 98), (104, 106, 101, 104), (100, 110, 100, close)])
        bar = observation(FIRST_OPEN + timedelta(weeks=3), 60, 106)
        with localcontext(prec=28):
            with self.subTest(check="classification"):
                self.assertEqual(classify_candle(history[-1].candle), CandleType.RALLY)
            with self.subTest(check="initial candidate"):
                self.assertIsNotNone(find_weekly_buying_zone(history, [bar], as_of=bar.ends_at))
            with self.subTest(check="final list"):
                zones = find_weekly_buying_zones(history, [bar], as_of=bar.ends_at)
                self.assertEqual([z.right_leg for z in zones], [history[-1]])

    def test_ordinary_prices_with_reduced_decimal_precision(self):
        cases = (
            ("100.00", "124.95", CandleType.BASE),
            ("100.00", "125.00", CandleType.BASE),
            ("100.00", "125.05", CandleType.RALLY),
            ("125.00", "100.00", CandleType.BASE),
            ("125.05", "100.00", CandleType.DROP),
        )
        with localcontext(prec=3):
            for opening, closing, expected in cases:
                with self.subTest(opening=opening, closing=closing):
                    candle = Candle(opening, "150.00", "100.00", closing)
                    self.assertEqual(classify_candle(candle), expected)
