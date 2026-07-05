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

        # 10 days of data guarantees we have enough historical rows
        df = yf.download(tickers=ticker, period="10d", interval="1d", progress=False)

        # Flatten yfinance Multi-Index columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # ---------------------------------------------------------------------
        # THE FIX: Filter out any candles with zero or missing volume
        # ---------------------------------------------------------------------
        if "Volume" in df.columns:
            df = df[(df["Volume"].notna()) & (df["Volume"] > 0)]

        # Check if we still have at least 2 valid trading days after filtering
        if df.empty or len(df) < 2:
            continue

        # ---------------------------------------------------------------------
        # Grab the necessary data points
        # ---------------------------------------------------------------------
        prev_open = df["Open"].iloc[-2]
        prev_close = df["Close"].iloc[-2]
        prev_low = df["Low"].iloc[-2]
        prev_high = df["High"].iloc[-2]

        curr_open = df["Open"].iloc[-1]
        curr_close = df["Close"].iloc[-1]

        # Determine previous day's candle color (Using >= to gracefully handle Dojis)
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

fno_tickers = [
    "RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "BHARTIARTL.NS", "ICICIBANK.NS", "SBIN.NS", "HINDUNILVR.NS",
    "INFY.NS", "BAJFINANCE.NS", "LICI.NS", "ITC.NS", "LT.NS", "MARUTI.NS", "M&M.NS", "KOTAKBANK.NS", "HCLTECH.NS",
    "SUNPHARMA.NS", "ULTRACEMCO.NS", "AXISBANK.NS", "TITAN.NS", "BAJAJFINSV.NS", "NTPC.NS", "ETERNAL.NS",
    "DMART.NS", "HAL.NS", "ONGC.NS", "ADANIPORTS.NS", "BEL.NS", "POWERGRID.NS", "ADANIENT.NS", "JSWSTEEL.NS",
    "WIPRO.NS", "TMPV.NS", "BAJAJ-AUTO.NS", "ASIANPAINT.NS", "COALINDIA.NS", "NESTLEIND.NS", "INDIGO.NS",
    "TATASTEEL.NS", "IOC.NS", "JIOFIN.NS", "TRENT.NS", "GRASIM.NS", "DLF.NS", "HINDZINC.NS", "SBILIFE.NS",
    "EICHERMOT.NS", "VEDL.NS", "HINDALCO.NS", "TVSMOTOR.NS", "MARICO.NS", "BSE.NS", "ICICIGI.NS", "ADANIENSOL.NS",
    "GMRAIRPORT.NS", "INDIANB.NS", "INDUSTOWER.NS", "LUPIN.NS", "JSWENERGY.NS", "NAUKRI.NS", "ICICIPRULI.NS",
    "SRF.NS", "POLICYBZR.NS", "HINDPETRO.NS", "PERSISTENT.NS", "PAYTM.NS", "SUZLON.NS", "IDEA.NS", "NHPC.NS",
    "ASHOKLEY.NS", "SBICARD.NS", "UNOMINDA.NS", "BHEL.NS", "ABCAPITAL.NS", "OFSS.NS", "FORTIS.NS", "RVNL.NS",
    "NYKAA.NS", "COLPAL.NS", "PRESTIGE.NS", "NMDC.NS", "PATANJALI.NS", "OIL.NS", "YESBANK.NS", "ALKEM.NS",
    "TORNTPOWER.NS", "AUROPHARMA.NS", "OBEROIRLTY.NS", "GODREJPROP.NS", "INDUSINDBK.NS", "SUPREMEIND.NS",
    "GLENMARK.NS", "TIINDIA.NS", "LTF.NS", "IRCTC.NS", "COFORGE.NS", "PIIND.NS", "MFSL.NS", "BHARATFORG.NS",
    "PHOENIXLTD.NS", "SAIL.NS", "IDFCFIRSTB.NS", "MPHASIS.NS", "BDL.NS", "KALYANKJIL.NS", "AUBANK.NS", "UPL.NS",
    "BANKINDIA.NS", "PAGEIND.NS", "BIOCON.NS", "LAURUSLABS.NS", "VOLTAS.NS", "FEDERALBNK.NS", "APLAPOLLO.NS",
    "DALBHARAT.NS", "KAYNES.NS", "JUBLFOOD.NS", "CONCOR.NS", "HUDCO.NS", "PETRONET.NS", "IREDA.NS", "BLUESTARCO.NS",
    "NATIONALUM.NS", "ASTRAL.NS", "MCX.NS", "KEI.NS", "EXIDEIND.NS", "DELHIVERY.NS", "TATAELXSI.NS", "KPITTECH.NS",
    "CDSL.NS", "LICHSGFIN.NS", "IGL.NS", "NBCC.NS", "SONACOMS.NS", "TATATECH.NS", "PPLPHARMA.NS", "AMBER.NS",
    "BANDHANBNK.NS", "SYNGENE.NS", "INOXWIND.NS", "TATACHEM.NS", "MANAPPURAM.NS", "NUVAMA.NS", "CROMPTON.NS",
    "ANGELONE.NS", "PNBHOUSING.NS", "CAMS.NS", "KFINTECH.NS", "IIFL.NS", "RBLBANK.NS", "PGEL.NS", "NCC.NS",
    "CYIENT.NS", "IEX.NS", "SAMMAANCAP.NS", "TITAGARH.NS"
]

if __name__ == "__main__":
    scan_results = scan_novice_gaps(fno_tickers)

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