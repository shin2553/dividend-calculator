import math
import os
import json
import tempfile
import shutil
from datetime import datetime

class PortfolioStorage:
    def __init__(self, data_dir='data', filename='portfolio.json'):
        self.data_dir = data_dir
        self.filepath = os.path.join(data_dir, filename)
        self._ensure_dir()

    def _ensure_dir(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def load(self):
        """Load portfolio data from JSON file."""
        if not os.path.exists(self.filepath):
            return {"updated_at": "", "positions": {}}
        
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERR] Failed to load portfolio: {e}")
            return {"updated_at": "", "positions": {}}

    def save(self, data):
        """Save portfolio data atomically."""
        data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Write to temp file first
        try:
            with tempfile.NamedTemporaryFile('w', delete=False, dir=self.data_dir, encoding='utf-8') as tf:
                json.dump(data, tf, ensure_ascii=False, indent=2)
                temp_name = tf.name
            
            # Atomic move
            shutil.move(temp_name, self.filepath)
            return True
        except Exception as e:
            print(f"[ERR] Failed to save portfolio: {e}")
            if 'temp_name' in locals() and os.path.exists(temp_name):
                os.remove(temp_name)
            return False

    def upsert(self, symbol, qty):
        """Update or insert a single position. If qty <= 0, remove it."""
        data = self.load()
        positions = data.get('positions', {})
        
        if qty <= 0:
            if symbol in positions:
                del positions[symbol]
        else:
            positions[symbol] = {'qty': qty}
            
        data['positions'] = positions
        success = self.save(data)
        return data, success

    def bulk_save(self, positions):
        """Replace all positions."""
        data = {
            'positions': positions
        }
        success = self.save(data)
        return data, success

    def clear(self):
        """Clear all active positions."""
        return self.bulk_save({})

    # ==========================
    # Named Portfolios
    # ==========================
    def get_portfolios_dir(self):
        d = os.path.join(self.data_dir, 'portfolios')
        if not os.path.exists(d):
            os.makedirs(d)
        return d

    def list_portfolios(self):
        """List all saved portfolio names."""
        d = self.get_portfolios_dir()
        files = [f for f in os.listdir(d) if f.endswith('.json')]
        # Return names without extension
        return sorted([os.path.splitext(f)[0] for f in files])

    def save_as(self, name):
        """Save current active portfolio as a named file."""
        if not name or "/" in name or "\\" in name:
            return False, "Invalid name"
        
        current_data = self.load()
        path = os.path.join(self.get_portfolios_dir(), f"{name}.json")
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(current_data, f, ensure_ascii=False, indent=2)
            return True, "Saved"
        except Exception as e:
            return False, str(e)

    def load_named(self, name):
        """Load a named portfolio into the active slot."""
        path = os.path.join(self.get_portfolios_dir(), f"{name}.json")
        if not os.path.exists(path):
            return False, "Not found"
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Save to active slot
            return self.save(data), "Loaded"
        except Exception as e:
            return False, str(e)

    def delete_portfolio(self, name):
        path = os.path.join(self.get_portfolios_dir(), f"{name}.json")
        if os.path.exists(path):
            try:
                os.remove(path)
                return True, "Deleted"
            except Exception as e:
                return False, str(e)
        return False, "Not found"

class PortfolioEngine:
    def __init__(self):
        pass

    def calculate(self, holdings, universe_data):
        """
        Calculates portfolio statistics.
        
        Args:
            holdings (list): List of dicts [{'ticker': '005930', 'amount': 1000000}, ...]
            universe_data (dict): The full data dictionary from loader.py
            
        Returns:
            dict: {
                'total_investment': float,
                'weighted_yield': float,
                'annual_income': float,
                'monthly_income': float,
                'weighted_return_1y': float,
                'monthly_simulation': list [12]
            }
        """
        total_investment = 0
        total_weighted_yield = 0
        total_weighted_return_1y = 0
        
        valid_holdings = []
        
        # 1. Validation and Totals
        for item in holdings:
            ticker = item.get('ticker')
            amount = float(item.get('amount', 0))
            
            if not ticker or amount <= 0:
                continue
                
            data = universe_data.get(ticker)
            if not data:
                continue
                
            valid_holdings.append({
                'ticker': ticker,
                'amount': amount,
                'data': data
            })
            total_investment += amount
            
        if total_investment == 0:
            return {
                'total_investment': 0,
                'weighted_yield': 0.0,
                'annual_income': 0,
                'monthly_income': 0,
                'weighted_return_1y': 0.0,
                'monthly_simulation': [0]*12
            }
            
        # 2. Weighted Calculations
        for item in valid_holdings:
            amount = item['amount']
            data = item['data']
            weight = amount / total_investment
            
            # Yield
            y = data.get('yield', 0.0)
            total_weighted_yield += y * weight
            
            # Return
            r = data.get('total_return_1y', 0.0) # Corrected to use total_return_1y if available
            if not r:
                 r = data.get('return_1y', 0.0)
                 
            total_weighted_return_1y += r * weight
            
        annual_income = total_investment * (total_weighted_yield / 100.0)
        monthly_income = annual_income / 12.0
        
        # 3. Monthly Simulation (Simple flat distribution for now)
        # In reality, ETFs pay quarterly or monthly. Without distribution schedule data,
        # we assume uniform distribution for the simulation visualization.
        monthly_simulation = [int(monthly_income)] * 12
        
        return {
            'total_investment': int(total_investment),
            'weighted_yield': round(total_weighted_yield, 2),
            'annual_income': int(annual_income),
            'monthly_income': int(monthly_income),
            'weighted_return_1y': round(total_weighted_return_1y, 2),
            'monthly_simulation': monthly_simulation
        }
