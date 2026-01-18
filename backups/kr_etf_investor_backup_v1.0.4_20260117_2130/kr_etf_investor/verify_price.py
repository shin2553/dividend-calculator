import sys
import io
# Set stdout to utf-8 to avoid encoding errors in non-console environments
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pykrx import stock
from datetime import datetime, timedelta
import pandas as pd

tickers = ["069500", "472150"] # KODEX 200 (standard), Target (problematic)
now = datetime.now()
print(f"Current time: {now}")

for ticker in tickers:
    print(f"\nChecking price for ticker: {ticker}")
    for i in range(5):
        d = now - timedelta(days=i)
        d_str = d.strftime("%Y%m%d")
        try:
            df = stock.get_etf_ohlcv_by_ticker(d_str)
            if df is not None and not df.empty:
                if ticker in df.index:
                    row = df.loc[ticker]
                    print(f"  Date: {d_str}, Close: {row['종가']}")
                else:
                     # print(f"  Date: {d_str}, Ticker {ticker} not found in ETF list.")
                     pass
            else:
                 pass
        except Exception as e:
            print(f"  Date: {d_str}, Error: {e}")
