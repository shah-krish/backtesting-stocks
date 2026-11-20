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
    find_weekly_buying_zones,
)


FIRST_WEEK = datetime(2026, 1, 5, 9, 15, tzinfo=NSE_TIMEZONE)


def weekly(week, open, high, low, close):
    start = FIRST_WEEK + timedelta(weeks=week)
    return TimedCandle(Candle(open, high, low, close), start, start + timedelta(days=4, hours=6))


def hourly(week, low, *, day=0, hour=0):
    start = FIRST_WEEK + timedelta(weeks=week, days=day, hours=hour)
    return TimedCandle(Candle(low + 1, low + 2, low, low + 1), start, start + timedelta(hours=1))


def weekly_dbr(week, lower, upper, *, leg_out_low, leg_out_high, leg_in_low=None):
    if leg_in_low is None:
        leg_in_low = lower
    return (
        weekly(week, upper + 2, upper + 3, leg_in_low, leg_in_low),
        weekly(week + 1, upper, upper + 1, lower, upper),
        weekly(week + 2, leg_out_low, leg_out_high, leg_out_low, leg_out_high - 1),
    )


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

    def test_leg_out_must_close_strictly_above_highest_base_body_top(self):
        older_base = weekly(1, 105, 113, 97, 103)
        newer_base = weekly(2, 101, 115, 99, 103)
        observation = hourly(4, 107)
        leg_ins = {
            "RBR": weekly(0, 100, 116, 98, 114),
            "DBR": weekly(0, 114, 116, 98, 100),
        }

        for pattern, leg_in in leg_ins.items():
            for close, qualifies in [("104.99", False), ("105", False), ("105.01", True)]:
                with self.subTest(pattern=pattern, close=close):
                    leg_out = weekly(3, 96, 107, 96, close)
                    zone = find_weekly_buying_zone(
                        [leg_in, older_base, newer_base, leg_out],
                        [observation],
                        as_of=observation.ends_at,
                    )
                    if qualifies:
                        self.assertIsNotNone(zone)
                        self.assertEqual(zone.pattern, pattern)
                        self.assertEqual(zone.upper, Decimal(105))
                        self.assertEqual(zone.right_leg, leg_out)
                    else:
                        self.assertIsNone(zone)

    def test_rejected_pattern_restarts_from_its_full_pattern_low(self):
        valid_left = weekly(0, 80, 94, 79, 92)
        valid_base = weekly(1, 88, 94, 85, 90)
        valid_right = weekly(2, 89, 96, 88, 95)
        observation = hourly(6, 107)

        for low_source in ("leg-in", "base", "leg-out"):
            with self.subTest(low_source=low_source):
                left = weekly(3, 112, 114, 90 if low_source == "leg-in" else 98, 98)
                base = weekly(4, 105, 111, 90 if low_source == "base" else 98, 103)
                right_low = 90 if low_source == "leg-out" else 98
                right = weekly(5, right_low, 107, right_low, 105)
                zone = find_weekly_buying_zone(
                    [valid_left, valid_base, valid_right, left, base, right],
                    [observation],
                    as_of=observation.ends_at,
                )

                self.assertIsNotNone(zone)
                self.assertEqual(zone.anchor_low, Decimal(107))
                self.assertEqual(zone.right_leg, valid_right)

    def test_rejected_pattern_cannot_reuse_its_leg_in_as_an_older_leg_out(self):
        older_leg_in = weekly(0, 94, 109, 91, 107)
        older_base = weekly(1, 98, 104, 95, 99)
        shared_rally = weekly(2, 100, 113, 98, 111)
        newer_base = weekly(3, 104, 112, 98, 106)
        rejected_leg_out = weekly(4, 99, 108, 98, 106)
        observation = hourly(5, 108)
        older_history = [older_leg_in, older_base, shared_rally]

        older_zone = find_weekly_buying_zone(
            older_history, [observation], as_of=observation.ends_at
        )
        self.assertIsNotNone(older_zone)
        self.assertEqual(older_zone.right_leg, shared_rally)
        self.assertIsNone(
            find_weekly_buying_zone(
                [*older_history, newer_base, rejected_leg_out],
                [observation],
                as_of=observation.ends_at,
            )
        )

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
        self.assertEqual(
            find_weekly_buying_zones(history, observations, as_of=assessment), [zone]
        )
        self.assertEqual(
            find_weekly_buying_zones(history, observations, as_of=wednesday.ends_at), []
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

    def test_valid_zones_are_empty_without_an_observation_or_qualifying_pattern(self):
        history = weekly_dbr(0, 100, 106, leg_out_low=101, leg_out_high=112)
        observation = hourly(3, 20)

        self.assertEqual(find_weekly_buying_zones(history, [], as_of=observation.ends_at), [])
        self.assertEqual(
            find_weekly_buying_zones(history, [observation], as_of=observation.ends_at), []
        )

    def test_equal_marked_lows_keep_older_zone_and_append_disjoint_zone_once(self):
        oldest = weekly_dbr(0, 92, 97, leg_out_low=92, leg_out_high=99)
        middle = weekly_dbr(3, 100, 103, leg_in_low=94, leg_out_low=96, leg_out_high=106)
        newest = weekly_dbr(6, 100, 106, leg_out_low=101, leg_out_high=112)
        observation = hourly(9, 111)

        zones = find_weekly_buying_zones(
            [*oldest, *middle, *newest], [observation], as_of=observation.ends_at
        )

        self.assertEqual([(zone.lower, zone.upper) for zone in zones], [(100, 103), (92, 97)])
        self.assertEqual([zone.right_leg for zone in zones], [middle[-1], oldest[-1]])
        self.assertEqual([zone.anchor_low for zone in zones], [111, 111])

    def test_endpoint_overlap_keeps_lower_marked_zone_and_uses_its_line(self):
        oldest = weekly_dbr(0, 78, 79, leg_out_low=78, leg_out_high=83)
        middle = weekly_dbr(3, 100, 104, leg_in_low=75, leg_out_low=80, leg_out_high=108)
        newest = weekly_dbr(6, 95, 100, leg_in_low=80, leg_out_low=95, leg_out_high=110)
        observation = hourly(9, 109)

        zones = find_weekly_buying_zones(
            [*oldest, *middle, *newest], [observation], as_of=observation.ends_at
        )

        self.assertEqual([(zone.lower, zone.upper) for zone in zones], [(95, 100), (78, 79)])
        self.assertEqual([zone.right_leg for zone in zones], [newest[-1], oldest[-1]])
        self.assertEqual(zones[0].full_pattern_low, Decimal(80))

    def test_disjoint_older_zone_can_be_above_newer_zone(self):
        older = weekly_dbr(0, 108, 111, leg_out_low=96, leg_out_high=119)
        newer = weekly_dbr(3, 100, 106, leg_in_low=99, leg_out_low=100, leg_out_high=122)
        observation = hourly(6, 121)

        zones = find_weekly_buying_zones(
            [*older, *newer], [observation], as_of=observation.ends_at
        )

        self.assertEqual([(zone.lower, zone.upper) for zone in zones], [(100, 106), (108, 111)])

    def test_saved_zone_survives_overlap_with_a_later_addition(self):
        oldest = weekly_dbr(0, 88, 102, leg_out_low=87, leg_out_high=106)
        middle = weekly_dbr(3, 90, 95, leg_in_low=89, leg_out_low=90, leg_out_high=98)
        newest = weekly_dbr(6, 100, 106, leg_in_low=94, leg_out_low=100, leg_out_high=112)
        observation = hourly(9, 111)

        zones = find_weekly_buying_zones(
            [*oldest, *middle, *newest], [observation], as_of=observation.ends_at
        )

        self.assertEqual([(zone.lower, zone.upper) for zone in zones], [(100, 106), (88, 102)])
        self.assertEqual([zone.right_leg for zone in zones], [newest[-1], oldest[-1]])

    def test_older_rejected_pattern_preserves_active_candidate_and_restarts(self):
        oldest = weekly_dbr(0, 91, 95, leg_out_low=90, leg_out_high=97)
        rejected = (
            weekly(3, 109, 110, 91, 91),
            weekly(4, 103, 104, 97, 103),
            weekly(5, 98, 105, 98, 103),
        )
        newest = weekly_dbr(6, 100, 106, leg_in_low=99, leg_out_low=100, leg_out_high=112)
        observation = hourly(9, 111)

        zones = find_weekly_buying_zones(
            [*oldest, *rejected, *newest], [observation], as_of=observation.ends_at
        )

        self.assertEqual([zone.right_leg for zone in zones], [newest[-1], oldest[-1]])
        self.assertEqual(
            find_weekly_buying_zones(
                [*rejected, *newest], [observation], as_of=observation.ends_at
            ),
            [zones[0]],
        )

    def test_older_search_starts_strictly_before_the_accepted_leg_in(self):
        history = [
            weekly(0, 94, 109, 91, 107),
            weekly(1, 98, 104, 95, 99),
            weekly(2, 100, 113, 98, 111),
            weekly(3, 104, 112, 98, 106),
            weekly(4, 99, 115, 98, 113),
        ]
        observation = hourly(5, 114)

        zones = find_weekly_buying_zones(history, [observation], as_of=observation.ends_at)

        self.assertEqual([zone.right_leg for zone in zones], [history[-1]])
        self.assertEqual(zones[0].left_leg, history[2])
