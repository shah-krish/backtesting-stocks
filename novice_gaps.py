import pandas as pd
import yfinance as yf


def scan_novice_gaps(ticker_basket):
    """Scans a list of tickers for True Novice Gap Up and Gap Down formations."""

    # Dictionary to store our results
    results = {
        "Novice_Gap_Up": [],
        "Novice_Gap_Down": []
    }

    for ticker in ticker_basket:
        print(f"Scanning {ticker}...")

        # 15 days of data
        df = yf.download(tickers=ticker, period="15d", interval="1d", progress=False)

        if df.empty or len(df) < 2:
            continue

        # Flatten yfinance Multi-Index columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Grab the necessary data points (Current and Previous Day)
        prev_open = df["Open"].iloc[-4]
        prev_close = df["Close"].iloc[-4]
        prev_low = df["Low"].iloc[-4]
        prev_high = df["High"].iloc[-4]

        curr_open = df["Open"].iloc[-3]
        curr_close = df["Close"].iloc[-3]

        # Determine previous day's candle color
        prev_is_red = prev_open > prev_close
        prev_is_green = prev_close > prev_open

        # 1. TRUE Novice Gap Up Logic
        # Prev candle RED, today opens strictly below prev LOW, today closes above prev close
        if prev_is_red and (curr_open < prev_low) and (curr_close > prev_close):
            results["Novice_Gap_Up"].append(ticker)

        # 2. TRUE Novice Gap Down Logic
        # Prev candle GREEN, today opens strictly above prev HIGH, today closes below prev close
        elif prev_is_green and (curr_open > prev_high) and (curr_close < prev_close):
            results["Novice_Gap_Down"].append(ticker)

    return results


# ----------------------------------------------------
# RUNNING THE SCREENER
# ----------------------------------------------------

# Placeholder for your F&O list (Note the .NS suffix for NSE)
fno_tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "VEDL.NS"]

if __name__ == "__main__":
    scan_results = scan_novice_gaps(fno_tickers)

    print("\n" + "=" * 55)
    print(" TRUE NOVICE GAP SCREENER RESULTS")
    print("=" * 55)

    print("\n🟢 TRUE NOVICE GAP UP")
    print("   (Prev day RED -> Opened below prev LOW -> Closed above prev close):")
    if scan_results["Novice_Gap_Up"]:
        for stock in scan_results["Novice_Gap_Up"]:
            print(f"  - {stock}")
    else:
        print("  None found today.")

    print("\n🔴 TRUE NOVICE GAP DOWN")
    print("   (Prev day GREEN -> Opened above prev HIGH -> Closed below prev close):")
    if scan_results["Novice_Gap_Down"]:
        for stock in scan_results["Novice_Gap_Down"]:
            print(f"  - {stock}")
    else:
        print("  None found today.")
    print("\n" + "=" * 55)