# Weekly buying zone

The weekly buying zone provides context for the daily and hourly buying strategy. Entry confirmations, trade execution, exits, and the selling strategy are open for later specification.

## Candle classification

The body size is the absolute difference between the open and close. The full range is the high minus the low, including both wicks. A candle is decisive when its body is strictly more than half its full range.

- R (rally). A decisive candle that closes above its open.
- D (drop). A decisive candle that closes below its open.
- B (base). A candle whose body is half its full range or less, regardless of colour.

A body of exactly half the range, a doji, and a valid zero-range candle all count as B.

## Backward search

1. Set the line price to the current week's low observed through the assessment time. Start searching from the most recent earlier weekly candle.
2. Find the nearest candle to the left whose range contains the line price. The line can touch only a wick or sit exactly at the candle's high or low.
3. If the candle found is D or B, move the line to its low and continue strictly to its left. If it is R and the immediately preceding candle is decisive, move the line to that R's low and likewise continue strictly to its left.
4. If the candle found is R and the immediately preceding candle is B, collect the full consecutive run of B candles before that R. The candle immediately before the run must be decisive. The pattern, in chronological order, is R–B–R or D–B–R, where B represents one or more consecutive base candles.
5. The **leg-in** is the decisive candle immediately before the base run (D or R). The **leg-out** is the rally candle immediately after it (always R). For every DBR or RBR, require the leg-out close to be strictly above the highest body top across all base candles: `leg_out.close > max(max(b.open, b.close) for b in base)`. A close exactly at that level fails, even if the leg-out wick extends above it.
6. If the leg-out closes at or below the highest base body top, skip the entire pattern. Move the line to the lowest wick low across its leg-in, all bases, and leg-out. Resume strictly to the left of its leg-in. Apply this rule during both the initial search and every search for an older zone. Any active candidate carries forward to the next qualifying comparison.
7. Keep the first qualifying zone as the current candidate. If there is no observed low for the current week or no qualifying pattern in the available history, there is no zone for that assessment.

## Zone boundaries

- Lower edge. Take the lowest wick low across the consecutive base candles.
- Upper edge. Find each base candle's body top by taking the higher of its open and close. Take the highest of those body tops.

The two boundaries can come from different base candles. For example, if one B has the highest body top at ₹105 and another B has the lowest wick low at ₹98, the buying zone is ₹98–₹105.

## Refining the weekly zone

Collect the valid weekly buying zones for each assessment by working backward through the available history.

1. Whenever a pattern supplies the next horizontal line, use its **full-pattern low**. This is the minimum wick low across the leg-in, every base candle, and the leg-out. From the initial candidate, search strictly to the left of its leg-in for the next qualifying pattern.
2. If the two marked zones share any price, including a single endpoint, they overlap. Keep the zone with the lower **marked lower edge** (the lowest wick low among its base candles). If the marked lows are equal, keep the older zone. Draw the next line at the surviving pattern's full-pattern low and search strictly to the left of the older pattern just examined.
3. If the zones share no price, record the current zone in the valid-zone list. The older zone becomes the next candidate. Continue from its full-pattern low and compare it with the next qualifying zone farther left.
4. A saved zone is final for this assessment. Apply the overlap comparison only between the active candidate and the next qualifying older zone. If a later addition overlaps a saved zone, keep both list entries.
5. When the remaining history yields no qualifying earlier pattern, append the last surviving candidate once and finish. If the initial search found no candidate, the list is empty.

For example, suppose the search finds ₹100–₹106, then ₹100–₹103, then ₹92–₹97. The first two overlap and have equal lows, so keep the older ₹100–₹103. The third zone is disjoint, so add ₹100–₹103 to the list and continue from the full-pattern low of the ₹92–₹97 pattern. If there is no further pattern, the final list contains ₹100–₹103 and ₹92–₹97.

For a saved-zone overlap example, suppose ₹100–₹106 is already saved and ₹90–₹95 is active. An older ₹88–₹102 zone overlaps the active zone and wins on its lower marked low. If history ends there, record ₹88–₹102 alongside ₹100–₹106. Both are valid despite sharing ₹100–₹102.

## Historical evaluation

- Assessments use timezone-aware timestamps. The implementation groups trading dates into Monday-based weeks in Indian Standard Time and expects timestamps to reflect when each candle's prices were available.
- Reconstruct the current week's low from observed prices in that week through the assessment timestamp. For candle data, only use bars whose closing prices and ranges were already known. For an assessment inside a bar, use finer observations or a partial candle recorded through the assessment time to capture any newer low. A later low must never revise an earlier result.
- The search requires the prior weekly candles in chart order. Missing bars, incomplete opening history, different weekly boundaries, or inconsistent corporate-action adjustments between the input series can change the first intersection or the base boundaries. Validate data coverage and chart alignment before measuring performance.
- A wick crossing establishes a price intersection. A later backtest will need to define when it can evaluate the confirmation and how to simulate fills, gaps, costs, and ambiguous intrabar event order.
- Keep the agreed candle threshold and zone rules fixed for the initial evaluation. Compare added confirmations on chronological out-of-sample data before drawing performance conclusions.

## Backtester architecture

Start with this deterministic strategy module. As the remaining rules are agreed, a historical data adapter can supply and validate candles, including from FYERS. A replay engine will give the strategy only candles known at each decision time. Entry and exit rules will produce signals for a simulated execution and portfolio layer. Reporting will record the candles behind each decision, simulated fills, and performance. All execution belongs to the simulator.

## Python entry point

Create a `TimedCandle` with `Candle(open, high, low, close)` and its timezone-aware start and end timestamps. Pass weekly candles and finer observations to the strategy for one instrument at a time.

    from weekly_buying_zone import find_weekly_buying_zone

    zone = find_weekly_buying_zone(
        weekly_candles,
        lower_timeframe_candles,
        as_of=assessment_time,
    )

The current Python function returns the first structural DBR or RBR found by the backward search, including its two price boundaries, the current week's low used for the search, the pattern, and its candles. A search without a match returns `None`. The leg-out close filter, overlap refinement, and full zone list await implementation.
