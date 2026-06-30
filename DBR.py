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


def scan_for_dbr_zones(df):
    """Scans backwards from the most recent candle to find DBR formations."""
    found_zones = []

    # Iterate backwards from the newest candle down to index 2
    for i in range(len(df) - 1, 1, -1):
        current_candle = df.iloc[i]

        # Stop when we find a Rally candle
        if current_candle["Is_Rally"]:
            basing_candle_index = i - 1
            base_count = 0

            # Loop backward through any preceding Base candles
            while basing_candle_index >= 0:
                basing_candle = df.iloc[basing_candle_index]

                if basing_candle["Is_Base"]:
                    base_count += 1
                    basing_candle_index -= 1
                else:
                    break

            # Check if we found at least one base AND the candle right before them is a Drop
            if base_count > 0 and basing_candle_index >= 0:
                leg_in_candle = df.iloc[basing_candle_index]

                if leg_in_candle["Is_Drop"]:
                    found_zones.append(
                        {
                            "Leg_In_Date": df.index[basing_candle_index],
                            "Leg_Out_Date": df.index[i]
                        }
                    )

                    # NOTE: If you ONLY want the single most recent zone and want the
                    # script to completely stop searching after finding one,
                    # uncomment the 'break' statement below.
                    # break

    return pd.DataFrame(found_zones)


# ----------------------------------------------------
# RUNNING THE SCANNER
# ----------------------------------------------------
ticker_basket = ["NUVAMA.NS"]
all_zones = []

for ticker in ticker_basket:
    data = fetch_and_prep_data(ticker)
    if data is not None:
        zones_df = scan_for_dbr_zones(data)
        if not zones_df.empty:
            all_zones.append(zones_df)

# Print the clean output
if all_zones:
    master_df = pd.concat(all_zones, ignore_index=True)

    master_df = master_df.sort_values(by="Leg_Out_Date", ascending=True).reset_index(drop=True)

    # Strip the timezone information for a cleaner output
    master_df["Leg_In_Date"] = master_df["Leg_In_Date"].dt.tz_localize(None)
    master_df["Leg_Out_Date"] = master_df["Leg_Out_Date"].dt.tz_localize(None)

    print("\n--- DBR Zones Found (Newest to Oldest) ---")
    print(master_df.to_string(col_space=25, justify="left"))
else:
    print("No structural DBR zones found.")