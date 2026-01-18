import asyncio
import aiohttp
import sys

# Windows console encoding fix
try:
    sys.stdout.reconfigure(encoding="utf-8")
except:
    pass

async def test_naver_api(ticker):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://m.stock.naver.com/domestic/stock/{ticker}/total"
    }
    url_etf = f"https://m.stock.naver.com/api/etf/{ticker}/basic"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url_etf, headers=headers) as res:
            if res.status == 200:
                data = await res.json()
                print("KEYS:", data.get('result', {}).keys())
                print("Specific Keys:")
                result = data.get('result', {})
                print(f"closePrice: {result.get('closePrice')}")
                print(f"compareToPreviousClosePrice: {result.get('compareToPreviousClosePrice')}")
                print(f"fluctuationRate: {result.get('fluctuationRate')}")
            else:
                print(f"Error: {res.status}")

if __name__ == "__main__":
    asyncio.run(test_naver_api("069500")) # KODEX 200
