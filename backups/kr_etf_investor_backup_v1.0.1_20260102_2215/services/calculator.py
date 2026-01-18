def calculate_projection(holdings, years=10, monthly_contribution=0, dividend_growth_rate=0.0):
    """
    (Legacy) Calculates simple portfolio value projection.
    """
    # 1. Calculate initial portfolio stats
    total_value = 0
    annual_dividend = 0
    weighted_yield = 0
    
    for asset in holdings:
        asset_value = asset['price'] * asset['shares']
        total_value += asset_value
        div_amt = asset_value * (asset['yield'] / 100.0)
        annual_dividend += div_amt
        
    if total_value > 0:
        weighted_yield = (annual_dividend / total_value)
    
    # 2. Year-by-year projection
    history = []
    
    current_value = total_value
    current_yield = weighted_yield
    current_annual_dividend = annual_dividend
    
    invested_capital = total_value
    
    for year in range(1, years + 1):
        year_start_value = current_value
        dividends_accumulated = 0
        
        # Monthly loop
        for month in range(12):
            # Add contribution
            current_value += monthly_contribution
            invested_capital += monthly_contribution
            
            # Reinvest dividends
            monthly_div = (current_value * current_yield) / 12
            dividends_accumulated += monthly_div
            current_value += monthly_div # DRIP
            
        current_annual_dividend = current_value * current_yield 
        
        history.append({
            'year': year,
            'invested_capital': invested_capital,
            'total_value': current_value,
            'annual_dividend': current_annual_dividend
        })
        
    return {
        'initial_stats': {
            'value': total_value,
            'dividend': annual_dividend,
            'yield': weighted_yield * 100
        },
        'projection': history
    }

def calculate_div_simulation(params):
    """
    Advanced Dividend Reinvestment Simulator (Mirrors Tkinter Logic)
    
    params: {
        'initial_principal': float,     # 초기 투자금
        'monthly_invest': float,        # 월 추가 투자금
        'annual_yield': float,          # 연 배당률 (decimal, e.g. 0.1 for 10%)
        'growth_rate': float,           # 연 주가상승률 (decimal)
        'annual_div_growth': float,     # 연 배당성장률 (decimal)
        'tax_rate': float,              # 세율 (decimal, e.g. 0.154)
        'reinvest_ratio': float,        # 재투자 비율 (decimal, 1.0 = 100%)
        'years': int,                   # 투자 기간 (년)
        'target_div': float             # (Optional) Break check handled in frontend primarily, but calculated here
    }
    """
    initial_principal = params.get('initial_principal', 0)
    monthly_invest = params.get('monthly_invest', 0)
    annual_yield = params.get('annual_yield', 0)
    growth_rate = params.get('growth_rate', 0)
    annual_div_growth = params.get('annual_div_growth', 0)
    tax_rate = params.get('tax_rate', 0.154)
    reinvest_ratio = params.get('reinvest_ratio', 1.0)
    years = params.get('years', 10)
    inflation_rate = params.get('inflation_rate', 0.0) # New Parameter
    
    history = []
    
    # Init variables
    # Post-tax (Real)
    V_post = initial_principal
    total_principal_post = initial_principal
    total_dividends_post = 0
    
    # Pre-tax (Comparison)
    V_pre = initial_principal
    total_principal_pre = initial_principal
    total_dividends_pre = 0
    
    current_annual_yield = annual_yield
    monthly_growth_rate = (1 + growth_rate) ** (1/12) - 1
    
    # Inflation deflator initialization
    # We want to show Real Value (Present Value). 
    # PV = FV / (1 + inflation_rate)^years
    monthly_inflation_rate = (1 + inflation_rate) ** (1/12) - 1
    current_deflator = 1.0

    max_months = years * 12
    
    for m in range(1, max_months + 1):
        # Update deflator
        current_deflator /= (1 + monthly_inflation_rate)

        # Annual Dividend Growth Update
        if m > 1 and (m - 1) % 12 == 0:
            current_annual_yield *= (1 + annual_div_growth)
            
        monthly_yield_rate = current_annual_yield / 12.0
        
        # 1. Capital Growth (Price Appreciation)
        V_post += V_post * monthly_growth_rate
        V_pre += V_pre * monthly_growth_rate
        
        # 2. Dividends
        d_post_calc = V_post * monthly_yield_rate
        d_post = d_post_calc * (1 - tax_rate)
        
        d_pre_calc = V_pre * monthly_yield_rate # Independent calculation
        d_pre = d_pre_calc # Alias for downstream usage
        
        reinvest_post = d_post * reinvest_ratio
        reinvest_pre = d_pre * reinvest_ratio 
        
        # 3. Add Contribution + Reinvestment
        V_post += monthly_invest + reinvest_post
        V_pre += monthly_invest + reinvest_pre
        
        # 4. Update Cumulative Stats
        total_principal_post += monthly_invest
        total_dividends_post += reinvest_post
        capital_profit_post = V_post - total_principal_post - total_dividends_post
        
        total_principal_pre += monthly_invest
        total_dividends_pre += reinvest_pre
        capital_profit_pre = V_pre - total_principal_pre - total_dividends_pre
        
        # 5. Record
        row = {
            "month": m,
            "period": f"{(m-1)//12}년 {(m-1)%12+1}개월",
            
            # Post-Tax (Real)
            "asset_post": round(V_post),
            "monthly_div_post": round(d_post),
            "reinvest_post": round(reinvest_post),
            "cash_div_post": round(d_post - reinvest_post),
            "principal_post": round(total_principal_post),
            "total_div_post": round(total_dividends_post),
            "capital_growth_post": round(capital_profit_post),
            
            # Real Value (Inflation Adjusted)
            "asset_post_real": round(V_post * current_deflator),
            "monthly_div_post_real": round(d_post * current_deflator),
            
            # Pre-Tax (Comparison)
            "asset_pre": round(V_pre),
            "monthly_div_pre": round(d_pre),
            "reinvest_pre": round(reinvest_pre),
            "cash_div_pre": round(d_pre - reinvest_pre),
            "principal_pre": round(total_principal_pre),
            "total_div_pre": round(total_dividends_pre),
            "capital_growth_pre": round(capital_profit_pre)
        }
        history.append(row)
        
    return history

