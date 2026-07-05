import pandas as pd
import yfinance as yf


def get_tickers_from_csv(filepath="fo_mktlots.csv"):
    """Dynamically reads the NSE F&O CSV and formats tickers for yfinance."""
    try:
        # header=None ensures we safely grab all rows regardless of NSE's formatting
        df = pd.read_csv(filepath, header=None, on_bad_lines='skip')

        # Column B (Index 1) holds the symbols. We extract and strip away extra spaces.
        raw_symbols = df.iloc[:, 1].astype(str).str.strip().tolist()

        clean_tickers = []

        # Dictionary to translate NSE Index symbols into Yahoo Finance tickers
        index_map = {
            "NIFTY": "^NSEI",
            "BANKNIFTY": "^NSEBANK",
            "NIFTYNXT50": "^NSMIDCP",  # Temporarily mapping to Nifty 50 if ^NN50 fails
            "MIDCPNIFTY": "^NSEMDCP50",  # Temporarily mapping to Nifty 50 if MIDCP fails
            "FINNIFTY": "NIFTY_FIN_SERVICE.NS"
        }

        for sym in raw_symbols:
            # Ignore header rows, empty strings, and pandas 'nan' values
            if sym in ["SYMBOL", "Symbol", "nan", "", "None"]:
                continue

            # If it's an index, use the Yahoo translation. Otherwise, append .NS
            if sym in index_map:
                clean_tickers.append(index_map[sym])
            else:
                clean_tickers.append(f"{sym}.NS")

        # Return the list with any accidental duplicates removed
        return list(dict.fromkeys(clean_tickers))

    except Exception as e:
        print(f"🔴 Error reading CSV: {e}")
        return []


def scan_novice_gaps(ticker_basket):
    """Scans a list of tickers for True Novice Gap Up and Gap Down formations."""

    results = {"Novice_Gap_Up": [], "Novice_Gap_Down": []}

    for ticker in ticker_basket:
        print(f"Scanning {ticker}...")

        df = yf.download(tickers=ticker, period="10d", interval="1d", progress=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # ---------------------------------------------------------------------
        # Filter out any candles with zero or missing volume (Holiday/Halt fix)
        # ---------------------------------------------------------------------
        if "Volume" in df.columns:
            df = df[(df["Volume"].notna()) & (df["Volume"] > 0)]

        if df.empty or len(df) < 2:
            continue

        prev_open = df["Open"].iloc[-2]
        prev_close = df["Close"].iloc[-2]
        prev_low = df["Low"].iloc[-2]
        prev_high = df["High"].iloc[-2]

        curr_open = df["Open"].iloc[-1]
        curr_close = df["Close"].iloc[-1]

        prev_is_red = prev_open >= prev_close
        prev_is_green = prev_close >= prev_open

        # 1. TRUE NOVICE GAP UP LOGIC
        if prev_is_red and (curr_open < prev_low) and (curr_close > prev_close):
            results["Novice_Gap_Up"].append(ticker)

        # 2. TRUE NOVICE GAP DOWN LOGIC
        elif prev_is_green and (curr_open > prev_high) and (curr_close < prev_close):
            results["Novice_Gap_Down"].append(ticker)

    return results


# ----------------------------------------------------
# RUNNING THE SCREENER
# ----------------------------------------------------

if __name__ == "__main__":
    # 1. Dynamically load the tickers directly from your CSV!
    fno_tickers = get_tickers_from_csv("fo_mktlots.csv")

    if not fno_tickers:
        print("Scan aborted: Could not load tickers from CSV.")
        exit()

    print(f"\n✅ Successfully loaded {len(fno_tickers)} tickers from CSV.")
    print("Starting daily scan...\n")

    # 2. Run the scanner
    scan_results = scan_novice_gaps(fno_tickers)

    # 3. Print the results
    print("\n" + "=" * 55)
    print(" TRUE NOVICE GAP SCREENER RESULTS (YFINANCE)")
    print("=" * 55)

    print("\n🟢 TRUE NOVICE GAP UP")
    if scan_results["Novice_Gap_Up"]:
        for stock in scan_results["Novice_Gap_Up"]:
            print(f"  - {stock}")
    else:
        print("  None found.")

    print("\n🔴 TRUE NOVICE GAP DOWN")
    if scan_results["Novice_Gap_Down"]:
        for stock in scan_results["Novice_Gap_Down"]:
            print(f"  - {stock}")
    else:
        print("  None found.")
    print("\n" + "=" * 55)