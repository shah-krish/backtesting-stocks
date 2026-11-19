# Implementation status

The initial weekly buying-zone search is implemented and tested with synthetic candles. The Python detector returns the first structural DBR or RBR. The leg-out close filter, full-pattern search lines, overlap resolution, and collection of all valid zones are documented and await implementation. [Strategy specification](strategy_spec.md#refining-the-weekly-zone)

## Implemented

- `Candle` validates open, high, low, and close prices and stores them as decimals. `classify_candle` labels each candle R, D, or B. A body of exactly 50% of the full range counts as B.
- `TimedCandle` requires timezone-aware timestamps and converts them to Indian Standard Time. The detector uses Monday-based weeks and calculates the current week's low from observations available by the assessment time.
- `find_weekly_buying_zone` searches prior weekly candles for the first qualifying RBR or DBR pattern. Wick touches and exact price matches at the high or low count. The zone spans the lowest wick low and the highest body top across the consecutive base candles.
- The function returns both zone edges, the starting low, the pattern, and the weekly candles that formed it. It returns `None` when the available observations and history yield no qualifying zone. [Python implementation](weekly_buying_zone.py)

## Architecture

The current entry point is a standalone function that accepts weekly history, lower-timeframe observations, and an assessment timestamp for one instrument. The proposed backtester adds these components around it.

1. **Historical data adapter.** Load and validate NSE stock and index candles and normalize their timestamps and price adjustments.
2. **Replay engine.** Advance through assessment times and provide the observations available at each point.
3. **Strategy rules.** Use the weekly zone as context for daily or hourly confirmations and trade signals.
4. **Simulator and portfolio.** Model fills, costs, and position state entirely within the backtest.
5. **Reporting.** Record the candles behind decisions, simulated fills, and performance. [Architecture proposal](strategy_spec.md#backtester-architecture)

## Dependencies and verification

- The detector and tests use the Python standard library. The implementation reads candles supplied by the caller and requires no third-party packages, credentials, or network access.
- All six tests passed on Python 3.14.3. They cover candle classification, exact wick touches, search restarts, multiple base candles, first-match selection, insufficient history, and the exclusion of future prices. [Test suite](tests/test_weekly_buying_zone.py)
- Run the tests from the project root with `python -B -m unittest discover -s tests -v`.

## Unfinished tasks

- **Historical data and chart validation.** Verify FYERS history availability and timestamp conventions, then build the adapter. Compare the detector's weekly candles and zones against TradingView on NSE stocks and indices. Check missing bars and price adjustments across timeframes. An assessment inside a bar needs finer observations or a partial candle captured at that time.
- **Remaining trading rules.** Define how the weekly zone filters daily or hourly setups, what confirms a buy, and when an entry can occur. Define exits, position sizing, and the separate selling strategy when those rules are agreed.
- **Backtest and research.** Build the replay, simulator, portfolio, and reporting layers. Specify how simulated fills handle gaps, costs, and ambiguous intrabar event order. Evaluate the agreed rules on chronological out-of-sample data before drawing performance conclusions.
