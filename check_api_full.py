import asyncio
import aiohttp
import sys
import json

# Windows console encoding fix
try:
    sys.stdout.reconfigure(encoding="utf-8")
except:
    pass

async def test_naver_api(ticker, type='etf'):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://m.stock.naver.com/domestic/stock/{ticker}/total"
    }
    url = f"https://m.stock.naver.com/api/{type}/{ticker}/basic"
    print(f"Fetching {url}...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as res:
            if res.status == 200:
                data = await res.json()
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print(f"Error: {res.status}")

if __name__ == "__main__":
    print("Testing ETF (KODEX 200)...")
    asyncio.run(test_naver_api("069500", "etf"))
    print("\nTesting Stock (Samsung)...")
    asyncio.run(test_naver_api("005930", "stock"))
