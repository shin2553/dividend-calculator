import random

def optimize_portfolio(target_yield, capital=10000):
    """
    Suggests a portfolio based on target yield.
    target_yield: float (e.g. 5.5 for 5.5%)
    capital: Total amount to allocate (default 10000 USD for simulation)
    """
    
    # Universe of reliable dividend stocks
    universe = {
        'high_yield': [
            {'ticker': 'O', 'yield': 5.5, 'price': 52},
            {'ticker': 'JEPI', 'yield': 7.5, 'price': 55},
            {'ticker': 'MAIN', 'yield': 6.2, 'price': 42},
            {'ticker': 'MO', 'yield': 8.5, 'price': 41},
            {'ticker': 'VICI', 'yield': 5.8, 'price': 30}
        ],
        'growth': [
            {'ticker': 'AAPL', 'yield': 0.5, 'price': 180},
            {'ticker': 'MSFT', 'yield': 0.7, 'price': 370},
            {'ticker': 'V', 'yield': 0.8, 'price': 260},
            {'ticker': 'AVGO', 'yield': 1.9, 'price': 900},
            {'ticker': 'HD', 'yield': 2.8, 'price': 350}
        ],
        'balanced': [
            {'ticker': 'KO', 'yield': 3.1, 'price': 59},
            {'ticker': 'SCHD', 'yield': 3.5, 'price': 76},
            {'ticker': 'JNJ', 'yield': 3.0, 'price': 155},
            {'ticker': 'PG', 'yield': 2.4, 'price': 148},
            {'ticker': 'PEP', 'yield': 3.0, 'price': 168}
        ]
    }
    
    selected_stocks = []
    
    # Simple Strategy Selection based on Target Yield
    if target_yield >= 5.0:
        # Aggressive Yield: 70% High Yield, 30% Balanced
        pool = universe['high_yield'] * 2 + universe['balanced']
    elif target_yield <= 2.0:
        # Growth Focus: 70% Growth, 30% Balanced
        pool = universe['growth'] * 2 + universe['balanced']
    else:
        # Balanced: Mix of everything
        pool = universe['balanced'] * 2 + universe['high_yield'] + universe['growth']
        
    # Pick 5 random stocks from the weighted pool
    picks = random.sample(pool, 5)
    # Remove duplicates
    unique_picks = {p['ticker']: p for p in picks}.values()
    
    # Allocate capital evenly
    allocation_per_stock = capital / len(unique_picks)
    
    portfolio = []
    for stock in unique_picks:
        shares = int(allocation_per_stock / stock['price'])
        if shares < 1: shares = 1
        
        portfolio.append({
            'ticker': stock['ticker'],
            'shares': shares
        })
        
    return portfolio
