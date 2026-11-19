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
5. Return the first qualifying zone. If there is no observed low for the current week, the search runs out of history, or a base run reaches the start of the history without a preceding decisive candle, there is no zone for that assessment.

## Zone boundaries

- Lower edge. Take the lowest wick low across the consecutive base candles.
- Upper edge. Find each base candle's body top by taking the higher of its open and close. Take the highest of those body tops.

The two boundaries can come from different base candles. For example, if one B has the highest body top at ₹105 and another B has the lowest wick low at ₹98, the buying zone is ₹98–₹105.

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

The result contains the two price boundaries, the current week's low used for the search, the pattern, and the candles that formed it. A search without a qualifying zone returns `None`.
