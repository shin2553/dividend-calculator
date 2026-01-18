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
    Advanced Dividend Reinvestment Simulator
    
    params: {
        'initial_principal': float,     # 초기 투자금
        'monthly_invest': float,        # 월 추가 투자금
        'annual_yield': float,          # 연 배당률 (decimal, e.g. 0.1 for 10%)
        'growth_rate': float,           # 연 주가상승률 (decimal)
        'annual_div_growth': float,     # 연 배당성장률 (decimal)
        'tax_rate': float,              # 세율 (decimal, e.g. 0.154 as default)
        'account_type': str,            # 'general', 'isa', 'pension'
        'reinvest_ratio': float,        # 재투자 비율 (decimal, 1.0 = 100%)
        'years': int,                   # 투자 기간 (년)
        'inflation_rate': float         # 물가상승률 (decimal)
    }
    """
    initial_principal = params.get('initial_principal', 0)
    monthly_invest = params.get('monthly_invest', 0)
    annual_yield = params.get('annual_yield', 0)
    growth_rate = params.get('growth_rate', 0)
    annual_div_growth = params.get('annual_div_growth', 0)
    
    # Custom Logic for Account Types
    account_type = params.get('account_type', 'general')
    base_tax_rate = 0.154
    
    # In simulation, ISA/Pension act as 0% tax for reinvestment (Tax deferral)
    current_tax_rate = params.get('tax_rate', base_tax_rate)
    if account_type in ['isa', 'pension']:
        current_tax_rate = 0.0
        
    reinvest_ratio = params.get('reinvest_ratio', 1.0)
    years = params.get('years', 10)
    inflation_rate = params.get('inflation_rate', 0.0)
    
    history = []
    
    # Asset Values
    V = initial_principal
    total_principal = initial_principal
    total_dividends = 0
    total_tax_saved = 0 # Cumulative tax savings compared to General 15.4%
    
    # Comparison: General Account (No Tax Benefit)
    V_gen = initial_principal
    
    monthly_growth_rate = (1 + growth_rate) ** (1/12) - 1
    monthly_inflation_rate = (1 + inflation_rate) ** (1/12) - 1
    current_deflator = 1.0
    current_annual_yield = annual_yield

    max_months = years * 12
    
    for m in range(1, max_months + 1):
        current_deflator /= (1 + monthly_inflation_rate)

        if m > 1 and (m - 1) % 12 == 0:
            current_annual_yield *= (1 + annual_div_growth)
            
        monthly_yield_rate = current_annual_yield / 12.0
        
        # 1. Price Appreciation
        V += V * monthly_growth_rate
        V_gen += V_gen * monthly_growth_rate # General comparison
        
        # 2. Dividends
        d_pre_tax = V * monthly_yield_rate
        d_actual = d_pre_tax * (1 - current_tax_rate)
        
        # Calculate Potential Tax in General mode
        d_gen_pre = V_gen * monthly_yield_rate
        d_gen_after = d_gen_pre * (1 - base_tax_rate)
        
        # Tax Saved this month
        tax_saved_this_month = d_pre_tax * (base_tax_rate - current_tax_rate)
        total_tax_saved += tax_saved_this_month
        
        reinvest_amt = d_actual * reinvest_ratio
        reinvest_gen = d_gen_after * reinvest_ratio
        
        # 3. Add Contribution + Reinvestment
        V += monthly_invest + reinvest_amt
        V_gen += monthly_invest + reinvest_gen
        
        # 4. Update Stats
        total_principal += monthly_invest
        total_dividends += reinvest_amt
        capital_profit = V - total_principal - total_dividends
        
        # 5. Record
        row = {
            "month": m,
            "period": f"{(m-1)//12}년 {(m-1)%12+1}개월",
            
            # Simulated Account
            "asset_post": round(V),
            "monthly_div_post": round(d_actual),
            "reinvest_post": round(reinvest_amt),
            "cash_div_post": round(d_actual - reinvest_amt),
            "principal_post": round(total_principal),
            "total_div_post": round(total_dividends),
            "capital_growth_post": round(capital_profit),
            
            # Tax Savings Info
            "tax_saved_total": round(total_tax_saved),
            
            # Real Value (Inflation Adjusted)
            "asset_post_real": round(V * current_deflator),
            "monthly_div_post_real": round(d_actual * current_deflator),
            
            # General Account (Comparison Base)
            "asset_gen": round(V_gen),
            "advantage": round(V - V_gen) # Wealth gap due to tax benefit
        }
        history.append(row)
        
    return history
