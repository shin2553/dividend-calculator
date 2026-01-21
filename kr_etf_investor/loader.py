"""
ETF Universe Loader (Async Optimized)
✅ KRX: 가격/수익률(1y/3y/5y) + 가격 CAGR(1y/3y/5y)
✅ FnGuide/Naver: 배당수익률(최근 1회), 최근 분배금/기준일/연 분배횟수 (Async)
✅ 분배/배당:
   - (가능하면) 분배금 히스토리 표로 TTM(최근 12개월) 분배금/분배수익률 계산
   - 히스토리 없으면: 최근 분배금 × 연 분배횟수로 연 분배금/연 분배율(추정) 계산
✅ 총수익(가격+분배) (1y/3y/5y) + 총수익 CAGR(1y/3y/5y)
✅ 월 현금흐름(추정/TTM 기반): monthly_income_est

출력 파일:
  ./data/dividend_universe.json

설치:
  pip install pykrx pandas requests beautifulsoup4 lxml tqdm aiohttp
"""

from pykrx import stock
import pandas as pd
import json
import os
import requests
from requests.adapters import HTTPAdapter
from io import StringIO
import re
from datetime import datetime, timedelta, date
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import asyncio
import aiohttp
import sys

# =========================
# 콘솔 인코딩(윈도우)
# =========================
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# =========================
# 설정
# =========================
def get_data_dir():
    """ Get path to persistent data, next to .exe if frozen """
    if getattr(sys, 'frozen', False):
        # When frozen, data should be in a 'data' folder next to the executable
        return os.path.join(os.path.dirname(sys.executable), 'data')
    # When not frozen, data is in the 'data' subfolder of the package
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

DATA_DIR = get_data_dir()
OUTPUT_PATH = os.path.join(DATA_DIR, "dividend_universe.json")

MAX_Async_CONCURRENCY = 10 # Lowering further to avoid rate limits during heavy price history fetches
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
}

# (선택) 디버그
DEBUG = False
DEBUG_TICKERS = set()

# =========================
# 유틸
# =========================
def _clean_num(x):
    if x is None:
        return ""
    return re.sub(r"[^\d\.\-]", "", str(x))

def _parse_date_any(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None

def _find_text_by_label(labels, html):
    """
    FnGuide 페이지 구조가 dt/dd가 아니어도 잡히도록,
    라벨 뒤의 '가장 가까운 숫자/날짜'를 정규식으로 탐색
    """
    h = html.replace("\n", " ").replace("\t", " ")
    for lab in labels:
        m = re.search(
            rf"{re.escape(lab)}.*?(\d{{4}}[\/\.\-]\d{{2}}[\/\.\-]\d{{2}}|[0-9]+(?:\.[0-9]+)?)",
            h
        )
        if m:
            return m.group(1)
    return ""

def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def _safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

def _round2(x):
    try:
        return round(float(x), 2)
    except Exception:
        return 0.0

def _calc_cagr(now_price, past_price, years):
    try:
        if past_price <= 0 or now_price <= 0 or years <= 0:
            return 0.0
        return ( (now_price / past_price) ** (1.0/years) - 1.0 ) * 100.0
    except Exception:
        return 0.0

def _total_cagr(price_cagr_pct, income_yield_annual_pct):
    try:
        pc = float(price_cagr_pct) / 100.0
        iy = float(income_yield_annual_pct) / 100.0
        return ((1 + pc) * (1 + iy) - 1) * 100.0
    except Exception:
        return 0.0

def _total_return_from_cagr(total_cagr_pct, years):
    try:
        tc = float(total_cagr_pct) / 100.0
        return ((1 + tc) ** years - 1) * 100.0
    except Exception:
        return 0.0

# =========================
# 분배금 히스토리 추출 (read_html)
# =========================
def _extract_history_from_html_tables(html):
    rows = []
    try:
        # pandas read_html is blocking/sync, but fast enough for memory string
        tables = pd.read_html(StringIO(html))
    except Exception:
        return rows

    date_keys = ["지급기준일", "분배기준일", "기준일", "지급일", "일자", "날짜"]
    amt_keys = ["분배금", "현금분배", "현금 분배", "분배금(원)", "현금분배(원)", "금액"]

    def find_col(cols, keys):
        for c in cols:
            cs = str(c).replace(" ", "")
            if any(k.replace(" ", "") in cs for k in keys):
                return c
        return None

    for t in tables:
        try:
            cols = list(t.columns)
            date_col = find_col(cols, date_keys)
            amt_col = find_col(cols, amt_keys)
            if date_col is None or amt_col is None:
                continue

            sub = t[[date_col, amt_col]].dropna()
            for _, rr in sub.iterrows():
                d = _parse_date_any(rr[date_col])
                v = _clean_num(rr[amt_col])
                if d and v.isdigit():
                    rows.append((d, int(v)))
        except Exception:
            continue

    rows = list(set(rows))
    rows.sort(key=lambda x: x[0], reverse=True)
    return rows

# =========================
# Discovery: Naver ETF List API
# =========================
async def fetch_naver_etf_list(session):
    """
    Get full list of ETFs from Naver Finance API.
    Returns: { ticker: name, ... }
    """
    url = "https://finance.naver.com/api/sise/etfItemList.nhn"
    try:
        async with session.get(url, timeout=10) as r:
            if r.status == 200:
                # Naver API might return application/x-javascript or text/plain with euc-kr
                # We use r.text() to get the raw content and then parse it manually or let json.loads handle it
                text = await r.text()
                data = json.loads(text)
                items = data.get('result', {}).get('etfItemList', [])
                return {item['itemcode']: item['itemname'] for item in items if item.get('itemcode')}
    except Exception as e:
        print(f"[Discovery] Failed to fetch Naver ETF list: {e}")
    return {}

# =========================
# Async Fetchers
# =========================
async def fetch_naver_etf_dividend_history_async(session, ticker):
    for attempt in range(3):
        try:
            url = f"https://m.stock.naver.com/api/etf/{ticker}/dividend/history?page=1&pageSize=24&firstPageSize=24"
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
                "Referer": f"https://m.stock.naver.com/domestic/stock/{ticker}/total",
                "Origin": "https://m.stock.naver.com",
                "Accept": "application/json, text/plain, */*"
            }
            async with session.get(url, headers=headers, timeout=10) as res:
                if res.status == 200:
                    data = await res.json()
                    results = []
                    if isinstance(data, dict) and 'result' in data:
                        items = data['result']
                        if items:
                            for item in items:
                                date_str = str(item.get('exDividendAt', '')).replace('.', '-')
                                amount = str(item.get('dividendAmount', '0'))
                                if date_str and amount and amount != '0':
                                    results.append((date_str, amount))
                    return results
                elif res.status in [403, 429]:
                    await asyncio.sleep(1)
                else: break
        except Exception:
            await asyncio.sleep(1)
    return []

async def fetch_naver_price_history_async(session, ticker, pages=15, page_size=20):
    # Fetch enough history for 1Y calc (approx 250 trading days) -> 13 pages min
    full_hist = []
    
    # Simple Retry Logic (3 attempts)
    for attempt in range(3):
        try:
            temp_hist = []
            success = True
            for p_idx in range(1, pages + 1):
                 url = f"https://m.stock.naver.com/api/stock/{ticker}/price?pageSize={page_size}&page={p_idx}"
                 headers = HEADERS.copy()
                 headers["Referer"] = f"https://m.stock.naver.com/domestic/stock/{ticker}/total"
                 async with session.get(url, headers=headers, timeout=10) as res:
                     if res.status == 200:
                         data = await res.json()
                         if isinstance(data, list):
                             if not data: break # End of data
                             for item in data:
                                 d_str = item.get('localTradedAt', '')
                                 p_str = item.get('closePrice', '0')
                                 d = _parse_date_any(d_str)
                                 p = _safe_int(_clean_num(p_str))
                                 if d and p > 0:
                                     temp_hist.append({'date': d, 'price': p})
                         else:
                             break
                     elif res.status == 403 or res.status == 429:
                         success = False # Probably blocked
                         break
                     else:
                         break
            
            if success and temp_hist:
                return temp_hist
            
            # If failed or empty, wait and retry
            await asyncio.sleep(1)
        except Exception:
            await asyncio.sleep(1)
            
    return []

async def fetch_naver_intraday_async(session, ticker):
    for attempt in range(3):
        try:
            # Correct API for intra-day (1-minute) price points
            url = f"https://api.stock.naver.com/chart/domestic/item/{ticker}?periodType=day"
            headers = HEADERS.copy()
            headers["Referer"] = f"https://m.stock.naver.com/domestic/stock/{ticker}/total"
            async with session.get(url, headers=headers, timeout=10) as res:
                if res.status == 200:
                    data = await res.json()
                    if isinstance(data, dict):
                        price_infos = data.get('priceInfos', [])
                        if price_infos:
                            return [float(p.get('currentPrice') or p.get('closePrice') or 0) for p in price_infos if p.get('currentPrice') or p.get('closePrice')]
                    return []
                elif res.status in [403, 429]:
                    await asyncio.sleep(1)
                else: break
        except Exception:
            await asyncio.sleep(1)
    return []

async def fetch_naver_stock_basic_async(session, ticker):
    for attempt in range(3):
        try:
            url = f"https://m.stock.naver.com/api/stock/{ticker}/basic"
            headers = HEADERS.copy()
            headers["Referer"] = f"https://m.stock.naver.com/domestic/stock/{ticker}/total"
            async with session.get(url, headers=headers, timeout=10) as res:
                if res.status == 200:
                    data = await res.json()
                    # Check for "result" key (sometimes nested, sometimes flat)
                    if isinstance(data, dict):
                        if 'result' in data:
                            return data['result']
                        return data
                elif res.status in [403, 429]:
                    await asyncio.sleep(1)
                else: break
        except Exception:
            await asyncio.sleep(1)
    return {}

async def fetch_naver_etf_basic_async(session, ticker):
    for attempt in range(3):
        try:
            headers = HEADERS.copy()
            headers["Referer"] = f"https://m.stock.naver.com/domestic/stock/{ticker}/total"
            url_etf = f"https://m.stock.naver.com/api/etf/{ticker}/basic"
            
            async with session.get(url_etf, headers=headers, timeout=10) as res:
                if res.status == 200:
                    d = await res.json()
                    res_data = d
                    if isinstance(d, dict) and 'result' in d:
                        res_data = d['result']
                    
                    if not res_data or not isinstance(res_data, dict):
                         continue

                    # Stock Name
                    name = res_data.get('stockName', '')
                    
                    # Return Rates
                    return_rates = {}
                    return_rates['1m'] = float(res_data.get('returnRate1m', 0) or 0)
                    return_rates['3m'] = float(res_data.get('returnRate3m', 0) or 0)
                    return_rates['6m'] = float(res_data.get('returnRate6m', 0) or 0)
                    return_rates['1y'] = float(res_data.get('returnRate1y', 0) or 0)
                    
                    # Sector (etfType or baseIndexName or etfBaseIndex)
                    sector = res_data.get('etfType', 'Etc')
                    if sector == 'Etc' and res_data.get('baseIndexName'):
                        sector = res_data['baseIndexName']
                    
                    return {
                        'name': name,
                        'returns': return_rates,
                        'sector': sector,
                        'closePrice': _safe_int(_clean_num(res_data.get('closePrice', '0'))),
                        'change_rate': float(res_data.get('fluctuationsRatio', 0) or res_data.get('fluctuationRate', 0) or 0),
                        'change_val': _safe_int(_clean_num(res_data.get('compareToPreviousClosePrice', '0'))),
                        'fluctuationRate': float(res_data.get('fluctuationsRatio', 0) or res_data.get('fluctuationRate', 0) or 0),
                        'deviationRate': float(res_data.get('deviationRate', 0) or 0),
                        'compareToPreviousClosePrice': _safe_int(_clean_num(res_data.get('compareToPreviousClosePrice', '0')))
                    }
                elif res.status in [403, 429]:
                    await asyncio.sleep(1)
                else: break
        except Exception:
            await asyncio.sleep(1)
            
    return {'name': '', 'returns': {}, 'sector': 'Etc'}

def classify_sector(ticker_name, index_name):
    """
    Professional Hierarchical Sector Classification
    Priority: [자산] Asset Class > [전략] Strategy > [산업] Industry > [테마] Thematic > [지수] Broad Market
    """
    text = (ticker_name + " " + index_name).upper()
    
    # --- 1. [자산] Asset Class (Non-Equity or Specific Asset types) ---
    # Fixed Income / Cash
    if any(k in text for k in ["채권", "국채", "통안", "회사채", "금리", "CD", "KOFR", "파킹", "머니마켓", "단기자금", "CASH", "BOND", "통화", "달러", "USD"]):
        return "[자산] 채권/현금"
    
    # Real Estate / Infrastructure
    if any(k in text for k in ["리츠", "REITS", "부동산", "인프라"]):
        return "[자산] 리츠/인프라"

    # Commodities
    if any(k in text for k in ["금 ", "은 ", "구리", "원자재", "COMMODITY", "금현물", "은현물"]):
        return "[자산] 원자재"

    # --- 2. [전략] Specialized Strategy ---
    # Covered Call / Income Focus
    if any(k in text for k in ["커버드콜", "프리미엄", "데일리고정", "COVERED CALL", "PREMIUM", "BUFFALO", "타겟리턴", "플러스"]):
        return "[전략] 인컴/커버드콜"

    # Factor / Strategy (Dividend, Value, ESG)
    if any(k in text for k in ["배당", "고배당", "배당성장", "배당주", "DIVIDEND", "DURABILITY", "가치", "VALUE", "저PBR", "퀄리티", "QUALITY", "ESG", "사회책임", "모멘텀", "MOMENTUM"]):
        return "[전략] 배당/가치/성장"

    # --- 3. [산업] Industry Sectors (Standard GICS-style) ---
    # Tech / AI
    if any(k in text for k in ["반도체", "AI", "테크", "소부장", "IT", "TECH", "DIGITAL", "소프트웨어", "HBM"]):
        return "[산업] IT/반도체/AI"
        
    # Finance
    if any(k in text for k in ["금융", "은행", "보험", "증권", "지주", "FINANCE", "K-금융"]):
        return "[산업] 금융/은행/보험"
        
    # Traditional Industries (Energy, Chem, Metal, Ship)
    if any(k in text for k in ["에너지", "화학", "철강", "정유", "원유", "조선", "원자력", "신재생", "친환경", "소비재", "화장품", "건설"]):
        return "[산업] 에너지/소재/산업재"

    # --- 4. [테마] Thematic Focus ---
    # Battery / EV
    if any(k in text for k in ["2차전지", "배터리", "BATTERY", "리튬", "전기차", "EV", "에너지솔루션"]):
        return "[테마] 2차전지/전기차"
        
    # Bio / Healthcare
    if any(k in text for k in ["바이오", "헬스케어", "BIO", "HEALTHCARE", "의료", "제약"]):
        return "[테마] 바이오/헬스케어"
    
    # Mid-Small Caps
    if any(k in text for k in ["중소형", "SMALL CAP", "미드캡"]):
        return "[테마] 중소형주"

    # --- 5. [지수] Broad Market Indices (Fallback) ---
    # Global/Overseas
    if any(k in text for k in ["S&P", "NASDAQ", "나스닥", "다우", "미국", "글로벌", "GLOBAL", "MSCI", "유로", "베트남", "인도", "JAPAN", "일본", "차이나", "중국", "액티브"]):
        return "[지수] 해외/글로벌"
        
    # Domestic (Korea)
    if any(k in text for k in ["200", "KOSPI", "코스피", "KOSDAQ", "코스닥", "150", "KRX300", "삼성그룹", "현대차그룹"]):
        return "[지수] 국내 시장"
        
    return "[기타] 분류미상"

async def get_dividend_info_async(session, ticker, current_price, manual_data):
    """
    Consolidated Async Fetcher
    """
    # 1. Fetch FnGuide HTML + Naver Basic + Naver History concurrently
    url_fn = f"https://comp.fnguide.com/svo2/asp/etf_snapshot.asp?pGB=1&gicode=A{ticker}&cID=&MenuYn=Y&ReportGB=&NewMenuID=106&stkGb=770"
    
    async def fetch_text(url):
        try:
             async with session.get(url, timeout=10) as r:
                 if r.status == 200:
                     # encoding might be euc-kr or utf-8? FnGuide usually euc-kr or cp949 but aiohttp auto-detects often
                     # Let's force read content and decode safely
                     content = await r.read()
                     try:
                         return content.decode('utf-8')
                     except:
                         return content.decode('euc-kr', errors='replace')
        except:
            return ""
        return ""

    # Launch initial tasks
    task_fn = fetch_text(url_fn)
    task_naver_basic = fetch_naver_etf_basic_async(session, ticker)
    task_naver_hist = fetch_naver_etf_dividend_history_async(session, ticker)
    task_naver_intraday = fetch_naver_intraday_async(session, ticker)
    
    # Gather basics
    results = await asyncio.gather(task_fn, task_naver_basic, task_naver_hist, task_naver_intraday)
    
    html_fn = results[0]
    naver_info = results[1] 
    naver_hist_raw = results[2]
    intraday_data = results[3]

    # If naver_info (from ETF API) is empty or missing name/price, it might be a regular stock or new listing
    # Fetch stock basic as fallback for price/name
    if not naver_info.get('closePrice') or not naver_info.get('name'):
        stock_basic = await fetch_naver_stock_basic_async(session, ticker)
        if stock_basic:
            # Normalize stock_basic fields to match naver_info structure
            if not naver_info: naver_info = {}
            if not naver_info.get('name'): naver_info['name'] = stock_basic.get('stockName', '')
            if not naver_info.get('closePrice'): 
                naver_info['closePrice'] = _safe_int(_clean_num(stock_basic.get('closePrice', '0')))
            
            # Normalize change info
            if 'fluctuationRate' not in naver_info:
                naver_info['fluctuationRate'] = float(stock_basic.get('fluctuationsRatio', 0) or 0)
            if 'compareToPreviousClosePrice' not in naver_info:
                val = _safe_int(_clean_num(stock_basic.get('compareToPreviousClosePrice', '0') or '0'))
                # Handle sign from compareToPreviousPrice.name
                status_name = stock_basic.get('compareToPreviousPrice', {}).get('name', '')
                if status_name in ['FALLING', 'SHOCK', 'LOWER_LIMIT']: val = -abs(val)
                elif status_name in ['RISING', 'UPPER_LIMIT']: val = abs(val)
                naver_info['compareToPreviousClosePrice'] = val

            if 'sector' not in naver_info or naver_info['sector'] == 'Etc':
                naver_info['sector'] = stock_basic.get('industryCodeName', 'Etc')

    # Extract Daily Change info
    # Priority: fluctuationRate (%), compareToPreviousClosePrice (Value)
    daily_change_rate = naver_info.get('fluctuationRate', 0.0)
    if daily_change_rate == 0: daily_change_rate = naver_info.get('change_rate', 0.0) # Price change rate fallback
    
    daily_change_value = naver_info.get('compareToPreviousClosePrice', 0)
    # Naver Basic often gives positive value for drop, need check sign? 
    # Actually 'fluctuationRate' usually has sign. 'compareToPreviousClosePrice' might be absolute.
    # If rate < 0 and value > 0, flip value.
    if daily_change_rate < 0 and daily_change_value > 0:
        daily_change_value = -daily_change_value
    
    # Check if we need history fallback for returns
    # We call price history if returns are largely missing or all zero
    rets = naver_info.get("returns", {})
    needs_hist = (not rets or all(v == 0 for v in rets.values()) or rets.get("6m", 0) == 0)
    
    # Check for Naver Price Fallback
    # If we have a valid price from Naver and it might be more recent than KRX (or KRX failed)
    # We trust Naver price for today if available.
    updated_price = current_price
    naver_price = naver_info.get('closePrice', 0)
    if naver_price > 0:
        # If KRX failed (current_price=0) or we just prefer Naver:
        # Use Naver price directly.
        updated_price = naver_price

    price_hist = []
    # Always fetch at least 1 page for sparkline (trend_7d)
    hist_pages = 15 if needs_hist else 1
    price_hist = await fetch_naver_price_history_async(session, ticker, pages=hist_pages)

    # Calc Returns from History if missing (Fallback for 1M, 3M, 6M, 1Y)
    def calc_hist_return(days_ago):
        if not price_hist: return 0.0
        cutoff = date.today() - timedelta(days=days_ago)
        p_now_h = price_hist[0]['price']
        for r in price_hist:
            if r['date'] <= cutoff:
                if r['price'] > 0:
                     return (p_now_h - r['price']) / r['price'] * 100.0
                return 0.0
        return 0.0

    if "returns" not in naver_info: naver_info["returns"] = {}
    
    # Fill gaps
    for k, d in [("1m", 30), ("3m", 90), ("6m", 180), ("1y", 365)]:
        if naver_info["returns"].get(k, 0) == 0:
            val = calc_hist_return(d)
            if val != 0: naver_info["returns"][k] = round(val, 2)
    
    # Parse FnGuide
    div_yield = _safe_float(_clean_num(_find_text_by_label(["배당수익률", "배당수익률(%)"], html_fn)) or 0.0)
    dist_recent = _safe_int(_clean_num(_find_text_by_label(["최근 분배금", "최근 분배금(원)"], html_fn)) or 0)
    dist_base_date = _find_text_by_label(["최근 분배금 지급기준일"], html_fn) or ""
    dist_freq_1y = _safe_int(_clean_num(_find_text_by_label(["연 분배횟수", "연 분배횟수(회)"], html_fn)) or 0)

    # Resolve Name
    etf_name = naver_info['name']
    if not etf_name:
        # Fallback parsing from info... assume stock.get_etf_ticker_name is slow/sync, skip for now or use cached
        if html_fn:
            try:
                # Simple regex for name in title?
                m = re.search(r"<h1[^>]*id=\"giName\"[^>]*>(.*?)</h1>", html_fn)
                if m: etf_name = m.group(1).strip()
            except: pass
            
    # Final Fallback: Stock Basic API (Reliable for Name)
    if not etf_name or etf_name == str(ticker):
        try:
             stock_basic = await fetch_naver_stock_basic_async(session, ticker)
             if stock_basic.get('stockName'):
                 etf_name = stock_basic['stockName']
        except:
             pass
             
    if not etf_name:
        etf_name = str(ticker)

    sector = classify_sector(etf_name, naver_info['sector'])

    # Build History
    manual_rows = []
    if ticker in manual_data:
        for item in manual_data[ticker]:
            d = _parse_date_any(item["date"])
            v = item["amount"]
            if d:
                manual_rows.append((d, int(v)))
    
    hist = []
    for d_str, amt_str in naver_hist_raw:
        d = _parse_date_any(d_str)
        v = _safe_int(amt_str)
        if d and v > 0:
            hist.append((d, v))
            
    if not hist and manual_rows:
        hist = manual_rows
        
    if not hist and html_fn:
        # Parsing table from HTML is sync, but CPU bound.
        # Offloading to thread to prevent blocking event loop during large batch updates.
        hist = await asyncio.to_thread(_extract_history_from_html_tables, html_fn)

    hist = list(set(hist))
    hist.sort(key=lambda x: x[0], reverse=True)

    # TTM Calc
    cutoff = date.today() - timedelta(days=365)
    dist_ttm_amount = 0
    dist_ttm_count = 0
    dist_ttm_last_date = ""

    for d, amt in hist:
        if d >= cutoff:
            dist_ttm_amount += int(amt)
            dist_ttm_count += 1
            if not dist_ttm_last_date:
                dist_ttm_last_date = d.strftime("%Y-%m-%d")

    # Inference for dist_freq_1y if missing from FnGuide
    if dist_freq_1y == 0 and len(hist) >= 2:
        d_top1 = hist[0][0]
        d_top2 = hist[1][0]
        gap = abs((d_top1 - d_top2).days)
        if 20 <= gap <= 40: dist_freq_1y = 12
        elif 80 <= gap <= 110: dist_freq_1y = 4
        elif 170 <= gap <= 200: dist_freq_1y = 2
        elif 340 <= gap <= 380: dist_freq_1y = 1

    dist_ttm_yield = 0.0
    calc_base_amount = 0
    if dist_ttm_count > 0:
        # Disable auto-annualization for new ETFs (<1Y history) to avoid exaggerated yields
        # if dist_freq_1y > 0 and dist_ttm_count < dist_freq_1y: ...
        calc_base_amount = dist_ttm_amount

        if updated_price > 0:
            dist_ttm_yield = round(calc_base_amount / updated_price * 100.0, 4)

    # Est Calc
    est_annual_amount = 0
    est_annual_yield = 0.0
    est_method = ""

    if dist_ttm_count == 0 and dist_recent > 0 and dist_freq_1y > 0 and updated_price > 0:
        est_annual_amount = dist_recent * dist_freq_1y
        est_annual_yield = round(est_annual_amount / updated_price * 100.0, 4)
        est_method = "recent_x_freq"

    return {
        "yield": float(div_yield),
        "dist_amount_recent": int(dist_recent),
        "dist_base_date": str(dist_base_date),
        "dist_freq_1y": int(dist_freq_1y),

        "dist_ttm_amount": int(dist_ttm_amount),
        "dist_ttm_count": int(dist_ttm_count),
        "dist_ttm_last_date": str(dist_ttm_last_date),
        "dist_ttm_yield": float(dist_ttm_yield),

        "est_annual_amount": int(est_annual_amount),
        "est_annual_yield": float(est_annual_yield),
        "est_method": str(est_method),

        "sector": sector,
        "_name_fetched": etf_name,
        "naver_returns": naver_info.get("returns", {}),
        "dist_history": [{"date": d.strftime("%Y-%m-%d"), "amount": amt} for d, amt in hist],
        "updated_price": updated_price,
        "daily_change_rate": round(float(daily_change_rate), 2),
        "daily_change_value": int(daily_change_value),
        "price_hist": price_hist,
        "intraday_data": intraday_data # 1-day trend
    }

def get_income_yield_annual(div_info: dict) -> float:
    if div_info.get("dist_ttm_yield", 0) > 0:
        return float(div_info["dist_ttm_yield"])
    if div_info.get("est_annual_yield", 0) > 0:
        return float(div_info["est_annual_yield"])
    return 0.0

def get_income_amount_annual(div_info: dict) -> int:
    if div_info.get("dist_ttm_amount", 0) > 0:
        return int(div_info["dist_ttm_amount"])
    if div_info.get("est_annual_amount", 0) > 0:
        return int(div_info["est_annual_amount"])
    return 0

# =========================
# KRX (Sync) - Kept as is
# =========================
def get_price_df(date_obj):
    for i in range(7):
        d = (date_obj - timedelta(days=i)).strftime("%Y%m%d")
        try:
            # print(f"[DEBUG] Fetching KRX etf ohlcv for {d}...")
            df = stock.get_etf_ohlcv_by_ticker(d)
            if not df.empty:
                # print(f"[DEBUG] Success {d} (rows={len(df)})")
                return df[["종가"]]
        except Exception as e:
            # print(f"[DEBUG] Fail {d}: {e}")
            continue
    return pd.DataFrame()

def calc_return_pct(now_price, past_price):
    try:
        if past_price <= 0:
            return 0.0
        return (now_price - past_price) / past_price * 100.0
    except Exception:
        return 0.0

# =========================
# Main Logic
# =========================
async def process_tickers_async(tickers, master_df, manual_data, progress_callback, stop_event):
    results = {}
    conn = aiohttp.TCPConnector(limit=MAX_Async_CONCURRENCY)
    timeout = aiohttp.ClientTimeout(total=60) # Increased timeout for full discovery
    
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        # 1. Fetch Definitive ETF List from Naver (Direct Discovery)
        if progress_callback:
            progress_callback("Discovering All Listed ETFs (Naver API)...", 5)
        naver_etf_map = await fetch_naver_etf_list(session)
        
        # 2. Automated Discovery & Filtering
        # Discovery triggers if:
        # a) It's a full update (many/no tickers)
        # b) Any input ticker is NOT found in the current master_df (meaning it might be a new listing)
        input_set = set(tickers)
        known_set = set(master_df.index) if not master_df.empty else set()
        missing_from_master = input_set - known_set
        
        is_full_update = (len(tickers) > 50 or not tickers or missing_from_master)
        
        if is_full_update and naver_etf_map:
            # Discovery: Add any tickers from Naver that weren't in the input list
            discovery_set = set(naver_etf_map.keys())
            new_discoveries = discovery_set - input_set
            
            if new_discoveries:
                print(f"[Discovery] Found {len(new_discoveries)} new ETFs from Naver list.")
                tickers = list(input_set | discovery_set) # Merge
        
        valid_tickers = []
        for t in tickers:
            if t in naver_etf_map:
                valid_tickers.append(t)
            else:
                # Log or handle strictly: only process IF it's in the Naver ETF list
                # This removes things like "005930" (Samsung) which is a stock.
                print(f"[Filter] Skipping non-ETF ticker: {t}")
        
        if not valid_tickers:
            print("[loader] No valid ETFs to process.")
            return {}

        total = len(valid_tickers)
        tasks = []
        for ticker in valid_tickers:
            tasks.append(process_single_ticker(session, ticker, master_df, manual_data))
            
        # Run
        done_count = 0
        for f in asyncio.as_completed(tasks):
             if stop_event and stop_event.is_set():
                 break
                 
             res = await f
             done_count += 1
             
             if res:
                 results[res["symbol"]] = res["data"]
                 
             if progress_callback:
                 pct = int((done_count / total) * 100)
                 progress_callback(f"Collecting Dividends ({done_count}/{total})", pct)
                 
    return results

async def process_single_ticker(session, ticker, master_df, manual_data):
    try:
        # Default prices to 0 if ticker not found in master_df (e.g. new listing or regular stock)
        if ticker in master_df.index:
            row = master_df.loc[ticker]
            price_now = int(row["종가"])
            price_1m = int(row["종가_1m"]) if pd.notna(row.get("종가_1m")) else 0
            price_3m = int(row["종가_3m"]) if pd.notna(row.get("종가_3m")) else 0
            price_6m = int(row["종가_6m"]) if pd.notna(row.get("종가_6m")) else 0
            price_1y = int(row["종가_1y"]) if pd.notna(row.get("종가_1y")) else 0
            price_3y = int(row["종가_3y"]) if pd.notna(row.get("종가_3y")) else 0
            price_5y = int(row["종가_5y"]) if pd.notna(row.get("종가_5y")) else 0
        else:
            # Not in KRX ETF list, use defaults and rely on Naver fallback
            price_now = 0
            price_1m = price_3m = price_6m = price_1y = price_3y = price_5y = 0

        # Async Data Fetch
        div = await get_dividend_info_async(session, ticker, price_now, manual_data)
        
        # Update Price if Naver has better data
        if div.get("updated_price", 0) > 0:
             price_now = div["updated_price"]

        name = div.get('_name_fetched', str(ticker))

        # Re-calc Returns (Sync CPU bound)
        ret_1m = calc_return_pct(price_now, price_1m) if price_1m > 0 else 0.0
        ret_3m = calc_return_pct(price_now, price_3m) if price_3m > 0 else 0.0
        ret_6m = calc_return_pct(price_now, price_6m) if price_6m > 0 else 0.0
        ret_1y = calc_return_pct(price_now, price_1y) if price_1y > 0 else 0.0
        ret_3y = calc_return_pct(price_now, price_3y) if price_3y > 0 else 0.0
        ret_5y = calc_return_pct(price_now, price_5y) if price_5y > 0 else 0.0

        # Naver Fallback
        n_rets = div.get("naver_returns", {})

        if ret_1m == 0 and n_rets.get("1m"): ret_1m = n_rets["1m"]
        if ret_3m == 0 and n_rets.get("3m"): ret_3m = n_rets["3m"]
        if ret_6m == 0 and n_rets.get("6m"): ret_6m = n_rets["6m"]
        if ret_1y == 0 and n_rets.get("1y"): ret_1y = n_rets["1y"]

        price_cagr_1y = _calc_cagr(price_now, price_1y, 1) if price_1y > 0 else 0.0
        price_cagr_3y = _calc_cagr(price_now, price_3y, 3) if price_3y > 0 else 0.0
        price_cagr_5y = _calc_cagr(price_now, price_5y, 5) if price_5y > 0 else 0.0

        income_yield_annual = get_income_yield_annual(div)

        total_cagr_1y = _total_cagr(price_cagr_1y, income_yield_annual) if price_1y > 0 else 0.0
        total_cagr_3y = _total_cagr(price_cagr_3y, income_yield_annual) if price_3y > 0 else 0.0
        total_cagr_5y = _total_cagr(price_cagr_5y, income_yield_annual) if price_5y > 0 else 0.0

        total_return_1y = _total_return_from_cagr(total_cagr_1y, 1) if price_1y > 0 else 0.0
        total_return_3y = _total_return_from_cagr(total_cagr_3y, 3) if price_3y > 0 else 0.0
        total_return_5y = _total_return_from_cagr(total_cagr_5y, 5) if price_5y > 0 else 0.0

        annual_income_amt = get_income_amount_annual(div)
        monthly_income_est = round(annual_income_amt / 12.0, 2) if annual_income_amt > 0 else 0.0

        return {
            "symbol": ticker,
            "data": {
                "name": name,
                "price": price_now,
                "daily_change_rate": div.get("daily_change_rate", 0.0),
                "daily_change_value": div.get("daily_change_value", 0),

                "yield": float(div.get("yield", 0.0)),
                "dist_amount_recent": int(div.get("dist_amount_recent", 0)),
                "dist_base_date": div.get("dist_base_date", ""),
                "dist_freq_1y": int(div.get("dist_freq_1y", 0)),

                "dist_ttm_amount": int(div.get("dist_ttm_amount", 0)),
                "dist_ttm_count": int(div.get("dist_ttm_count", 0)),
                "dist_ttm_last_date": div.get("dist_ttm_last_date", ""),
                "dist_ttm_yield": float(div.get("dist_ttm_yield", 0.0)),

                "est_annual_amount": int(div.get("est_annual_amount", 0)),
                "est_annual_yield": float(div.get("est_annual_yield", 0.0)),
                "est_method": div.get("est_method", ""),
                
                "sector": div.get("sector", ""),
                "dist_history": div.get("dist_history", []),

                "income_yield_annual_used": float(income_yield_annual),
                "income_amount_annual_used": int(annual_income_amt),
                "monthly_income_est": float(monthly_income_est),

                "dist_warning": bool(income_yield_annual == 0),
                "annual_yield_label": "TTM" if div.get("dist_ttm_yield", 0) > 0 else ("EST" if div.get("est_annual_yield", 0) > 0 else "NONE"),

                "price_1m": price_1m,
                "price_3m": price_3m,
                "price_6m": price_6m,
                "price_1y": price_1y,
                "price_3y": price_3y,
                "price_5y": price_5y,

                "return_1m": _round2(ret_1m),
                "return_3m": _round2(ret_3m),
                "return_6m": _round2(ret_6m),
                "return_1y": _round2(ret_1y),
                "return_3y": _round2(ret_3y),
                "return_5y": _round2(ret_5y),

                "price_cagr_1y": _round2(price_cagr_1y),
                "price_cagr_3y": _round2(price_cagr_3y),
                "price_cagr_5y": _round2(price_cagr_5y),

                "total_return_1y": _round2(total_return_1y),
                "total_return_3y": _round2(total_return_3y),
                "total_return_5y": _round2(total_return_5y),

                "total_cagr_1y": _round2(total_cagr_1y),
                "total_cagr_3y": _round2(total_cagr_3y),
                "total_cagr_5y": _round2(total_cagr_5y),

                "trend_1d": div.get("intraday_data", []),

                "last_updated": datetime.now().strftime("%Y-%m-%d"),
            }
        }
    except Exception as e:
        # print(f"Error {ticker}: {e}")
        return None

def load_data(progress_callback=None, target_tickers=None, stop_event=None):
    print("[START] loader (Async)")

    # 1. KRX Prices (Sync, Threaded)
    now_dt = datetime.now()
    dates = {
        "now": now_dt,
        "1m": now_dt - timedelta(days=30),
        "3m": now_dt - timedelta(days=90),
        "6m": now_dt - timedelta(days=180),
        "1y": now_dt - timedelta(days=365),
        "3y": now_dt - timedelta(days=365*3),
        "5y": now_dt - timedelta(days=365*5),
    }
    
    if progress_callback:
        progress_callback("Fetching KRX prices...", 0)

    dfs = {}
    # Use standard threadpool for KRX
    with ThreadPoolExecutor(max_workers=7) as executor:
        future_map = {executor.submit(get_price_df, d): k for k, d in dates.items()}
        for future in as_completed(future_map):
            if stop_event and stop_event.is_set():
                print("[loader] STOPPING (during KRX fetch)")
                return
            tag = future_map[future]
            try:
                dfs[tag] = future.result()
            except:
                dfs[tag] = pd.DataFrame()

    if dfs["now"].empty:
        print("[FAIL] KRX now price empty. Checking for cached data...")
        if os.path.exists(OUTPUT_PATH):
             print(f"[WARN] Loading from {OUTPUT_PATH} (Fallback)")
             try:
                 with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
                     cached_data = json.load(f)
                 
                 # Construct valid master df from cache
                 cached_tickers = list(cached_data.keys())
                 if cached_tickers:
                     # Create a DataFrame with necessary columns
                     # We need '종가', '종가_1m' etc. OR just handle gracefully.
                     # For now, let's just ensure '종가' (price) is there.
                     
                     data_for_df = []
                     for t in cached_tickers:
                         item = cached_data[t]
                         p = item.get("price", 0)
                         data_for_df.append({"ticker": t, "종가": p})
                     
                     fallback_df = pd.DataFrame(data_for_df).set_index("ticker")
                     
                     # Fill other columns with 0 or NaN
                     # Fill other columns
                     for col_period in ["1m", "3m", "6m", "1y", "3y", "5y"]:
                          col_nam = f"종가_{col_period}"
                          ret_key = f"return_{col_period}"
                        
                          vals = []
                          for t in cached_tickers:
                              item = cached_data[t]
                              p = float(item.get("price", 0))
                              r = float(item.get(ret_key, 0))
                            
                              # Reverse calc: price_past = price_now / (1 + r/100)
                              if p > 0 and r != 0:
                                  past = p / (1 + r/100.0)
                                  vals.append(int(past))
                              else:
                                  # If return is 0 or price is 0, we treat history as missing
                                  # This prevents "hallucinated" 0% price change for new ETFs
                                  vals.append(0)
                        
                          fallback_df[col_nam] = vals

                     master = fallback_df
                     print(f"[INFO] Loaded {len(master)} tickers from cache (with reconstructed history).")
                 else:
                     print("[FAIL] Cache empty")
                     if progress_callback: progress_callback("Failed: KRX empty & Cache empty", 0)
                     return
             except Exception as e:
                 print(f"[FAIL] Cache load error: {e}")
                 if progress_callback: progress_callback("Failed: KRX empty & Cache error", 0)
                 return
        else:
             print("[FAIL] No cache found")
             if progress_callback: progress_callback("Failed: KRX empty & No cache", 0)
             return
    else:
        master = dfs["now"].copy()
        master = master.join(dfs["1m"], rsuffix="_1m")
        master = master.join(dfs["3m"], rsuffix="_3m")
        master = master.join(dfs["6m"], rsuffix="_6m")
        master = master.join(dfs["1y"], rsuffix="_1y")
        master = master.join(dfs["3y"], rsuffix="_3y")
        master = master.join(dfs["5y"], rsuffix="_5y")

    tickers = master.index.tolist()

    if target_tickers:
        # For targeted updates, we combine KRX list + target_tickers
        # process_tickers_async will then verify/expand as needed.
        tickers_set = set(tickers)
        for t in target_tickers:
            if t not in tickers_set:
                tickers.append(t)
        
        # Filter to only the targets for this specific run
        tickers = [t for t in target_tickers if t] 
        print(f"[INFO] Targeted Refresh: {len(tickers)} tickers")

    total = len(tickers)
    
    # 2. Async Process
    manual_hist_path = os.path.join(DATA_DIR, "manual_dividend_history.json")
    manual_data = {}
    if os.path.exists(manual_hist_path):
        try:
            with open(manual_hist_path, "r", encoding="utf-8") as f:
                manual_data = json.load(f)
        except: pass

    # Windows Asyncio Policy fix for some environments
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Run Async Loop
    results = asyncio.run(process_tickers_async(tickers, master, manual_data, progress_callback, stop_event))
    
    if stop_event and stop_event.is_set():
        print("[loader] STOPPED.")
        return

    # Load existing data if exists to merge (for partial updates)
    existing_data = {}
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except:
            pass
            
    # Merge: update existing with new results
    existing_data.update(results)
    
    # Save
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fp:
        json.dump(existing_data, fp, ensure_ascii=False, indent=4)

    print(f"[DONE] saved -> {OUTPUT_PATH} (updated={len(results)}, total={len(existing_data)})")

# =========================
# Fast Refresh Logic
# =========================
async def fetch_basic_info_only(session, ticker):
    """
    Fetch only price and change data.
    """
    try:
        # Launch intraday fetch early
        intraday_task = asyncio.create_task(fetch_naver_intraday_async(session, ticker))

        # Try ETF Basic first
        etf_data = await fetch_naver_etf_basic_async(session, ticker)
        if etf_data.get('closePrice') and etf_data['closePrice'] > 0:
            trend_data = await intraday_task
            etf_data['trend_1d'] = trend_data
            return ticker, etf_data

        # Fallback to Stock Basic
        stock_data = await fetch_naver_stock_basic_async(session, ticker)
        if stock_data:
             p = _safe_int(_clean_num(stock_data.get('closePrice', '0')))
             rate = float(stock_data.get('fluctuationsRatio', 0) or 0)
             val = _safe_int(_clean_num(stock_data.get('compareToPreviousClosePrice', '0') or '0'))
             
             status_name = stock_data.get('compareToPreviousPrice', {}).get('name', '')
             if status_name in ['FALLING', 'SHOCK', 'LOWER_LIMIT']:
                 val = -abs(val)
                 rate = -abs(rate)
             elif status_name in ['RISING', 'UPPER_LIMIT']:
                 val = abs(val)
                 rate = abs(rate)
             
             trend_data = await intraday_task
             return ticker, {
                 'closePrice': p,
                 'change_rate': rate,
                 'change_val': val,
                 'name': stock_data.get('stockName', ticker),
                 'trend_1d': trend_data
             }
        
        # Ensure intraday task is completed even if basics fail
        await intraday_task
    except:
        pass
    return ticker, None

async def refresh_prices_async(tickers):
    results = {}
    conn = aiohttp.TCPConnector(limit=20) # Higher limit for fast refresh
    async with aiohttp.ClientSession(connector=conn) as session:
        tasks = [fetch_basic_info_only(session, t) for t in tickers]
        for f in asyncio.as_completed(tasks):
            t, data = await f
            if data:
                results[t] = data
    return results

def refresh_prices(tickers):
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(refresh_prices_async(tickers))

if __name__ == "__main__":
    load_data()
