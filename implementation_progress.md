# Implementation progress

The weekly buying-zone detector returns the refined list of zones for one instrument at a given assessment time. Verification has used synthetic candles. The historical data adapter and backtester are still pending. [Strategy specification](strategy_spec.md)

## Implemented

- `Candle` validates OHLC prices and stores them as decimals. Classification compares twice the body with the full range using exact fractions. A body exactly half the range counts as a base at any caller precision.
- `TimedCandle` normalizes timezone-aware timestamps to Indian Standard Time. The detector uses Monday-based weeks and anchors the search at the current week's lowest observed price through the assessment time. An assessment inside a bar requires finer observations or a partial candle captured by that time.
- The backward search includes wick touches and exact high or low matches. The marked zone spans the lowest base wick low through the highest base body top. Each result records these boundaries, the initial search price, the pattern, and its source candles.
- For both DBR and RBR, the leg-out close must exceed the highest body top across the complete base run. A close at or below that price fails even when the leg-out wick extends above it.
- For a rejected pattern, the search uses the lowest wick low across the leg-in, base run, and leg-out as its next line. It resumes on the candle immediately before the rejected pattern's leg-in.
- `find_weekly_buying_zones` takes one instrument's weekly history, lower-timeframe observations, and assessment timestamp. It returns the valid `BuyingZone` entries in search order, or an empty list when there is no qualifying zone. `find_weekly_buying_zone` returns the first qualifying candidate before overlap refinement, or `None`. Both use the same assessment-time cutoff and qualifying search. [Weekly detector](weekly_buying_zone.py)
- Refinement compares the active candidate with the next qualifying older zone. A shared endpoint counts as overlap. The lower marked edge wins, and an equal marked edge favors the older zone. The search resumes at the survivor's full-pattern low, strictly before the older pattern just examined.
- A disjoint comparison saves the active zone and promotes the older zone. Saved zones stay in the list even if a later addition overlaps them. The final active zone is appended once when history runs out. [Weekly refinement rules](strategy_spec.md#refining-the-weekly-zone)

## Verification

The detector and tests use the Python standard library and caller-supplied candles. The 21 synthetic tests passed on Python 3.14.3. Run them from the project root with `python -B -m unittest discover -s tests -v`.

- The detector tests cover backward search, wick touches, multi-candle bases, rejected patterns, overlap decisions, insufficient history, and assessment-time cutoffs for both public functions. [Detector tests](tests/test_weekly_buying_zone.py)
- The audit tests cover classification around the 50% threshold, reduced decimal precision, rejected patterns inserted at different search positions, and partial-bar observations. [Audit tests](tests/test_weekly_zone_audit.py)

## Next tasks

1. Verify FYERS history coverage, missing bars, timestamp conventions, and consistent price adjustments across timeframes. Compare weekly candles and marked zones against TradingView for NSE stocks and indices, then build the historical data adapter.
2. Define how weekly zones filter daily and hourly setups. Agree on buy confirmations, entry timing, exits, position sizing, and the separate selling strategy.
3. Build replay so each decision sees only observations available at its timestamp. Define how the simulator handles gaps, costs, and intrabar event order, then track fills and positions in the portfolio.
4. Record the candles behind each decision, simulated fills, and performance. Evaluate the agreed rules on chronological out-of-sample data. [Backtester architecture](strategy_spec.md#backtester-architecture)
