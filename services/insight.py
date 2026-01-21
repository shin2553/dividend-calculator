import pandas as pd
from pykrx import stock
import requests
from datetime import datetime, timedelta
import re

# ================================
# 1. Sector Rotation Logic
# ================================
def get_sector_rotation(universe_data):
    """
    Groups ETFs by their 'sector' field and calculates average returns.
    Returns sorted lists for 1M and 3M performance.
    """
    if not universe_data:
        return {}

    sector_stats = {}

    for ticker, data in universe_data.items():
        sector = data.get('sector', '기타')
        # Skip classification errors or uncategorized if desired, but '기타' is fine to show too.
        if sector == '[기타] 분류미상' or not sector:
            sector = "기타_미분류"

        if sector not in sector_stats:
            sector_stats[sector] = {
                'count': 0,
                'sum_1m': 0.0,
                'sum_3m': 0.0,
                'sum_year': 0.0 # Yield
            }
        
        # FIX: Returns are top-level keys, not in 'returns' dict
        # parse values like 19.16 (float)
        r1m = data.get('return_1m', 0.0) or 0.0
        r3m = data.get('return_3m', 0.0) or 0.0
        
        sector_stats[sector]['count'] += 1
        sector_stats[sector]['sum_1m'] += float(r1m)
        sector_stats[sector]['sum_3m'] += float(r3m)
        
        # Add yield to see which sector is "high yield"
        # Use TTM yield preferably, else Est
        y = data.get('dist_ttm_yield', 0.0)
        yield_val = float(y) if y > 0 else float(data.get('est_annual_yield', 0.0))
        sector_stats[sector]['sum_year'] += yield_val

    # Average out
    results = []
    for sec, stat in sector_stats.items():
        if stat['count'] > 0:
            results.append({
                'sector': sec,
                'count': stat['count'],
                'avg_return_1m': round(stat['sum_1m'] / stat['count'], 2),
                'avg_return_3m': round(stat['sum_3m'] / stat['count'], 2),
                'avg_yield': round(stat['sum_year'] / stat['count'], 2)
            })
    
    # Sort by 3M return descending
    results.sort(key=lambda x: x['avg_return_3m'], reverse=True)
    
    return results

# ================================
# 2. Supply & Demand (Investor Trends)
# ================================
def get_supply_demand_ranking(universe_tickers=None):
    """
    Fetches Net Purchases for Institution & Foreigner for the last 5 trading days.
    Filters to return only ETFs in our universe.
    """
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d") # Approx 5 trading days
        
        # PyKRX: stock.get_market_net_purchases_of_equities_by_ticker(start, end, "KOSPI", investor="기관합계")
        # Retry with KOSPI first, as most ETFs are there.
        
        # 1. Institution
        try:
            df_inst = stock.get_market_net_purchases_of_equities_by_ticker(start_date, end_date, "KOSPI", investor="기관합계")
        except:
            df_inst = pd.DataFrame()
        
        # 2. Foreigner
        try:
            df_for = stock.get_market_net_purchases_of_equities_by_ticker(start_date, end_date, "KOSPI", investor="외국인")
        except:
            df_for = pd.DataFrame()
        
        # Process results
        def process_df(df, type_label):
            top_list = []
            if df is None or df.empty: return []
            
            # Check if columns exist (sometimes pykrx returns different format on error)
            if '순매수거래대금' not in df.columns: return []

            df_sorted = df.sort_values(by='순매수거래대금', ascending=False)
            
            for ticker, row in df_sorted.iterrows():
                net_buy = row['순매수거래대금']
                if net_buy <= 0: break 
                
                # Check Universe
                if universe_tickers and ticker not in universe_tickers:
                    continue
                    
                top_list.append({
                    'ticker': ticker,
                    'name': row['종목명'],
                    'net_buy': int(net_buy),
                    'type': type_label
                })
                if len(top_list) >= 10: break
            return top_list

        inst_top = process_df(df_inst, "Institution")
        for_top = process_df(df_for, "Foreigner")
        
        return {
            'institution': inst_top,
            'foreigner': for_top
        }

    except Exception as e:
        print(f"[Insight] Supply/Demand Error: {e}")
        return {'institution': [], 'foreigner': []}

# ================================
# 3. Macro Indicators (Yield Gap)
# ================================
def get_market_indicators():
    """
    Scrapes Treasury Bond 3Y Yield and USD/KRW.
    Returns dict.
    """
    indicators = {
        'bond_3y': 0.0,
        'usd_krw': 0.0,
        'usd_trend': 'flat',
        'bond_trend': 'flat'
    }
    
    try:
        url = "https://finance.naver.com/marketindex/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'euc-kr' 
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 1. Bond Yield (Government Bond 3Y)
        # ID: #marketindex_cd_IRR_GOVT03Y (often reliable)
        bond_val = 0.0
        bond_item = soup.select_one("#marketindex_cd_IRR_GOVT03Y .value")
        
        if bond_item:
             try: bond_val = float(bond_item.text.replace(',', ''))
             except: pass
        else:
            # Fallback: Search in list
            items = soup.select("ul.data_lst li")
            for item in items:
                name = item.select_one(".blind")
                if name and "국고채 3년" in name.text:
                    val = item.select_one(".value")
                    if val:
                        try: bond_val = float(val.text.replace(',', ''))
                        except: pass
                        break
        
        indicators['bond_3y'] = bond_val
            
        # 2. Exchange Rate (USD)
        usd_val = 0.0
        # ID: #exchangeList .on > .head_info > .value (First item usually USD)
        usd_item = soup.select_one("#exchangeList .on .head_info .value")
        if usd_item:
            try: usd_val = float(usd_item.text.replace(',', ''))
            except: pass
        
        indicators['usd_krw'] = usd_val
            
    except Exception as e:
        print(f"[Insight] Macro Scraping Error: {e}")

    return indicators
