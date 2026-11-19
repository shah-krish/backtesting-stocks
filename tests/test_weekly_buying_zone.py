from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest import TestCase

from weekly_buying_zone import (
    NSE_TIMEZONE,
    Candle,
    CandleType,
    TimedCandle,
    classify_candle,
    find_weekly_buying_zone,
)


FIRST_WEEK = datetime(2026, 1, 5, 9, 15, tzinfo=NSE_TIMEZONE)


def weekly(week, open, high, low, close):
    start = FIRST_WEEK + timedelta(weeks=week)
    return TimedCandle(Candle(open, high, low, close), start, start + timedelta(days=4, hours=6))


def hourly(week, low, *, day=0, hour=0):
    start = FIRST_WEEK + timedelta(weeks=week, days=day, hours=hour)
    return TimedCandle(Candle(low + 1, low + 2, low, low + 1), start, start + timedelta(hours=1))


class WeeklyBuyingZoneTests(TestCase):
    def test_candle_classification(self):
        cases = (
            (Candle(100, 110, 100, 106), CandleType.RALLY),
            (Candle(106, 110, 100, 100), CandleType.DROP),
            (Candle("100.05", "100.15", "100.05", "100.10"), CandleType.BASE),
            (Candle(105, 110, 100, 100), CandleType.BASE),
            (Candle(105, 110, 100, 105), CandleType.BASE),
            (Candle(100, 100, 100, 100), CandleType.BASE),
        )
        for candle, expected in cases:
            with self.subTest(candle=candle):
                self.assertIs(classify_candle(candle), expected)

    def test_inclusive_wick_intersection_and_multiple_base_candles(self):
        left = weekly(0, 100, 116, 98, 114)
        older_base = weekly(1, 104, 112, 98, 102)
        newer_base = weekly(2, 103, 108, 100, 105)
        right = weekly(3, 106, 122, 103, 118)

        for low in (103, 121, 122):
            with self.subTest(low=low):
                observation = hourly(4, low)
                zone = find_weekly_buying_zone(
                    [right, newer_base, left, older_base],
                    [observation],
                    as_of=observation.ends_at,
                )
                self.assertIsNotNone(zone)
                self.assertEqual(zone.pattern, "RBR")
                self.assertEqual((zone.lower, zone.upper), (Decimal(98), Decimal(105)))
                self.assertEqual(zone.anchor_low, Decimal(low))
                self.assertEqual(zone.left_leg, left)
                self.assertEqual(zone.base, (older_base, newer_base))
                self.assertEqual(zone.right_leg, right)

    def test_restarts_at_low_after_drop_base_and_rally_without_base(self):
        left = weekly(0, 105, 106, 98, 99)
        base = weekly(1, 102, 108, 100, 104)
        right = weekly(2, 106, 111, 105, 110)
        intervening = [
            weekly(3, 115, 115, 112, 112),
            weekly(4, 110, 115, 109, 114),
            weekly(5, 116, 120, 114, 117),
            weekly(6, 125, 126, 118, 119),
            weekly(7, 126, 130, 122, 127),
        ]
        observation = hourly(8, 121)
        zone = find_weekly_buying_zone(
            [left, base, right, *intervening], [observation], as_of=observation.ends_at
        )

        self.assertIsNotNone(zone)
        self.assertEqual(zone.pattern, "DBR")
        self.assertEqual((zone.lower, zone.upper), (Decimal(100), Decimal(104)))
        self.assertEqual(zone.left_leg, left)
        self.assertEqual(zone.base, (base,))
        self.assertEqual(zone.right_leg, right)

    def test_returns_the_first_qualifying_zone(self):
        older_rally = weekly(0, 100, 116, 98, 114)
        older_base = weekly(1, 104, 112, 98, 102)
        middle_rally = weekly(2, 106, 122, 103, 118)
        newer_base = weekly(3, 103, 108, 100, 105)
        newer_rally = weekly(4, 106, 122, 103, 118)
        observation = hourly(5, 121)
        zone = find_weekly_buying_zone(
            [older_rally, older_base, middle_rally, newer_base, newer_rally],
            [observation],
            as_of=observation.ends_at,
        )

        self.assertIsNotNone(zone)
        self.assertEqual(zone.right_leg, newer_rally)
        self.assertEqual(zone.base, (newer_base,))

    def test_week_to_date_low_ignores_prior_week_and_future_prices(self):
        prior_weeks = [
            weekly(0, 100, 116, 98, 114),
            weekly(1, 104, 112, 98, 102),
            weekly(2, 106, 122, 103, 118),
        ]
        current_week = weekly(3, 115, 125, 90, 123)
        old_hour = hourly(2, 90)
        monday = hourly(3, 103)
        wednesday = hourly(3, 90, day=2)
        history = [*prior_weeks, current_week]
        observations = [wednesday, monday, old_hour]

        assessment = wednesday.ends_at - timedelta(minutes=1)
        zone = find_weekly_buying_zone(
            history, observations, as_of=assessment.astimezone(timezone.utc)
        )
        self.assertIsNotNone(zone)
        self.assertEqual(zone.anchor_low, Decimal(103))
        self.assertEqual(zone.right_leg, prior_weeks[-1])
        self.assertEqual(
            zone, find_weekly_buying_zone(prior_weeks, [monday], as_of=assessment)
        )
        self.assertIsNone(
            find_weekly_buying_zone(history, observations, as_of=wednesday.ends_at)
        )

    def test_returns_no_zone_without_current_week_observation_or_full_pattern(self):
        unfinished_history = [weekly(1, 104, 112, 98, 102), weekly(2, 106, 122, 103, 118)]
        observation = hourly(3, 103)
        self.assertIsNone(
            find_weekly_buying_zone(unfinished_history, [], as_of=observation.ends_at)
        )
        self.assertIsNone(
            find_weekly_buying_zone(unfinished_history, [observation], as_of=observation.ends_at)
        )
