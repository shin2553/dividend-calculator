import sys
import io
# Set stdout to utf-8 to avoid encoding errors in non-console environments
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pykrx import stock
from datetime import datetime, timedelta
import pandas as pd

tickers = ["069500", "472150"] # KODEX 200, ACE ...
now = datetime.now()
print(f"Current time: {now}")

for ticker in tickers:
    print(f"\nChecking price for ticker: {ticker}")
    for i in range(5):
        d = now - timedelta(days=i)
        d_str = d.strftime("%Y%m%d")
        print(f"  Fetching for {d_str}...")
        try:
            df = stock.get_etf_ohlcv_by_ticker(d_str)
            if df is not None and not df.empty:
                if ticker in df.index:
                    row = df.loc[ticker]
                    print(f"    SUCCESS: Date: {d_str}, Close: {row['종가']}")
                    break # Found distinct price
                else:
                     print(f"    Empty/Missing: Ticker {ticker} not in returned DF. DF size: {len(df)}")
            else:
                 print(f"    Empty: Returned DF is empty or None")
        except Exception as e:
            print(f"    Error: {d_str}, {e}")
