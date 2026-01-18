import sys
import io
import os
# Set stdout to utf-8 to avoid encoding errors in non-console environments
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

import asyncio
import pandas as pd
from datetime import datetime
from kr_etf_investor import loader
import aiohttp

async def verify():
    ticker = "472150"
    print(f"Verifying price for {ticker}...")
    
    # Mock master_df with dummy data (price=0 to simulate failure/missing)
    master_data = {
        "종가": [0], 
        "종가_1m": [0], "종가_3m": [0], "종가_6m": [0], 
        "종가_1y": [0], "종가_3y": [0], "종가_5y": [0]
    }
    master_df = pd.DataFrame(master_data, index=[ticker])
    manual_data = {}
    
    conn = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=conn) as session:
        result = await loader.process_single_ticker(session, ticker, master_df, manual_data)
        
        if result:
            data = result["data"]
            price = data["price"]
            print(f"Result Price: {price}")
            print(f"Result Name: {data['name']}")
            print(f"Result Yield: {data['yield']}")
            
            if price > 14000:
                print("SUCCESS: Price is valid and sourced from Naver (fallback).")
            else:
                print("FAIL: Price is still invalid.")
        else:
            print("FAIL: No result returned.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify())
