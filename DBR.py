import numpy as np
import pandas as pd
import yfinance as yf

def fetch_and_prep_data(ticker, period="2y", interval="1h"):
    """Downloads historical data and computes basic candle metrics."""
    print(f"Fetching data for {ticker}...")
    df = yf.download(tickers=ticker, period=period, interval=interval)

    if df.empty:
        return None

    # Flatten multi-index columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df["Candle_Range"] = df["High"] - df["Low"]
    df["Body_Size"] = np.abs(df["Open"] - df["Close"])

    # Define structural movements mathematically
    df["Is_Drop"] = (df["Close"] < df["Open"]) & (
        df["Body_Size"] > (df["Candle_Range"] * 0.50)
    )
    df["Is_Rally"] = (df["Close"] > df["Open"]) & (
        df["Body_Size"] > (df["Candle_Range"] * 0.50)
    )
    df["Is_Base"] = df["Body_Size"] <= (df["Candle_Range"] * 0.50)

    return df.dropna()


def backtest_demand_zones(df):
    """Scans for DBR formations and tracks historical retests."""
    active_zones = []
    trade_logs = []

    # Iterate through data (starting from index 2 to allow for pattern matching)
    for i in range(2, len(df)):
        current_candle = df.iloc[i]
        current_low = current_candle["Low"]
        current_high = current_candle["High"]
        current_close = df.iloc[i]["Close"]
        current_time = df.index[i]

        # ----------------------------------------------------
        # 1. CHECK FOR RETESTS OF EXISTING ZONES FIRST
        # ----------------------------------------------------
        for zone in active_zones[:]:  # Iterate over a copy to safely remove items
            # If price dips into the demand zone (touches Proximal Line)
            if current_low <= zone["proximal_line"]:
                # Check if it hit the stop loss (closed below Distal Line)
                if current_close < zone["distal_line"]:
                    trade_logs.append(
                        {
                            "Type": "DBR_Demand",
                            "Base_Date": zone["formed_at"],
                            "Leg_Out_Date": zone["leg_out_date"],  # NEW
                            "Retested_At": current_time,
                            "Result": "Stop_Loss",
                        }
                    )
                    active_zones.remove(zone)
                # Check if it bounced successfully (moved up past entry)
                elif current_high > zone["proximal_line"] + (
                        zone["proximal_line"] - zone["distal_line"]
                ) * 2:
                    trade_logs.append(
                        {
                            "Type": "DBR_Demand",
                            "Base_Date": zone["formed_at"],
                            "Leg_Out_Date": zone["leg_out_date"],
                            "Retested_At": current_time,
                            "Result": "Take_Profit_2R",
                        }
                    )
                    active_zones.remove(zone)

            # Invalidate zone if price completely breaks below without executing cleanly
            elif current_low < zone["distal_line"]:
                active_zones.remove(zone)

        # ----------------------------------------------------
        # 2. IDENTIFY NEW DBR FORMATIONS (Drop -> Base -> Rally)
        # ----------------------------------------------------

        if(current_candle["Is_Rally"]):
            basing_candle_index = i-1
            pattern_low = current_low
            pattern_high = 0
            base_count = 0
            while(basing_candle_index>=0):
                basing_candle = df.iloc[basing_candle_index]
                if basing_candle["Is_Base"]:
                    pattern_high = max(pattern_high, basing_candle["Close"], basing_candle["Open"])
                    pattern_low = min(pattern_low, basing_candle["Low"])
                    base_count += 1
                    basing_candle_index -= 1
                else:
                    break
            if base_count > 0 and basing_candle_index >= 0:
                leg_in_candle = df.iloc[basing_candle_index]
                if(leg_in_candle["Is_Drop"]):
                    proximal = pattern_high
                    distal = pattern_low
                    active_zones.append(
                        {
                            "leg_out_date": df.index[i],
                            "leg_in_date": df.index[basing_candle_index],
                            "formed_at": df.index[basing_candle_index + 1],
                            "proximal_line": proximal,
                            "distal_line": distal,
                        }
                    )

        # candle_minus_2 = df.iloc[i - 2]
        # candle_minus_1 = df.iloc[i - 1]
        #
        # if (
        #     candle_minus_2["Is_Drop"]
        #     and candle_minus_1["Is_Base"]
        #     and current_candle["Is_Rally"]
        # ):
        #     # Define structural boundaries
        #     proximal = max(candle_minus_1["Open"], candle_minus_1["Close"])
        #     distal = candle_minus_1["Low"]
        #
        #     active_zones.append(
        #         {
        #             "leg_out_date": df.index[i],
        #             "formed_at": df.index[i - 1],
        #             "proximal_line": proximal,
        #             "distal_line": distal,
        #         }
        #     )
    return pd.DataFrame(trade_logs)


# ----------------------------------------------------
# RUNNING THE INITIAL SANDBOX
# ----------------------------------------------------
# Basket of liquid Indian equities (Note the .NS suffix for NSE)
ticker_basket = ["NUVAMA.NS"]
all_results = []

for ticker in ticker_basket:
    data = fetch_and_prep_data(ticker)
    if data is not None:
        results = backtest_demand_zones(data)
        if not results.empty:
            results["Ticker"] = ticker
            all_results.append(results)

# Combine and analyze metrics
if all_results:
    master_df = pd.concat(all_results, ignore_index=True)
    print("\n--- Phase 1 Backtest Summary ---")
    print(master_df["Result"].value_counts(normalize=True) * 100)
    print(f"\nTotal trades found across basket: {len(master_df)}")

    # NEW: Print the trade log table
    print("\n--- Detailed Trade Log ---")
    print(master_df.to_string())  # .to_string() forces Pandas to show all rows/columns
else:
    print("No valid structural trades found with current mathematical thresholds.")