import aiohttp
import asyncio
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def fetch_naver(ticker):
    url_stock = f"https://m.stock.naver.com/api/stock/{ticker}/basic"
    url_etf = f"https://m.stock.naver.com/api/etf/{ticker}/basic"
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    
    async with aiohttp.ClientSession() as session:
        print(f"Fetching Stock Basic for {ticker}...")
        try:
            async with session.get(url_stock, headers=headers) as res:
                if res.status == 200:
                    data = await res.json()
                    print(f"Stock Basic Res: {data}")
                else:
                    print(f"Stock Basic Status: {res.status}")
        except Exception as e:
            print(f"Stock Basic Error: {e}")

        print(f"\nFetching ETF Basic for {ticker}...")
        try:
            async with session.get(url_etf, headers=headers) as res:
                if res.status == 200:
                    data = await res.json()
                    print(f"ETF Basic Res: {data}")
                else:
                    print(f"ETF Basic Status: {res.status}")
        except Exception as e:
            print(f"ETF Basic Error: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_naver("472150"))
