import time
import pandas as pd
import yfinance as yf

# Throttle configuration
CALL_DELAY = 60  # seconds to wait between yfinance requests to avoid rate limits

if __name__ == "__main__":
    # List of US stock tickers for testing
    us_symbols = ["AAPL", "MSFT", "GOOG", "AMZN"]
    all_data = {}

    for sym in us_symbols:
        try:
            print(f"Fetching {sym} from Yahoo Finance...")
            ticker = yf.Ticker(sym)
            df = ticker.history(period="3mo", interval="1d")
            if df.empty:
                raise ValueError(f"No data returned for {sym}")

            # Retain only key OHLCV columns
            df = df.loc[:, ["Open", "High", "Low", "Close", "Volume"]]
            all_data[sym] = df
            print(f"Successfully loaded {sym}. Head of data:")
            print(df.head())
        except Exception as e:
            print(f"Failed to fetch {sym}: {e}")

        print(
            f"Waiting {CALL_DELAY}s before next request to avoid rate limits...")
        time.sleep(CALL_DELAY)

    # Optionally save to CSV files
    # for sym, df in all_data.items():
    #     df.to_csv(f"{sym}.csv")
