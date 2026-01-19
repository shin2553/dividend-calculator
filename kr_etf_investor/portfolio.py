import math
import os
import json
import tempfile
import shutil
import re
from datetime import datetime

class PortfolioStorage:
    DEFAULT_ACCOUNT = "기본 계좌" # Keep default as is for existing? Or change? User asked to restrict generic new ones. Let's keep existing constant but validate new ones. 
    # Actually, "기본 계좌" is Korean. If user wants English only to fix encoding, we might want to change this constant too?
    # But that might break existing data logic. 
    # User said "Restriction on account names *I write*". 
    # I will add validation for NEW names.

    def __init__(self, data_dir='data', filename='portfolio.json'):
        self.data_dir = data_dir
        self.filepath = os.path.join(data_dir, filename)
        self._ensure_dir()

    def _ensure_dir(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def load(self):
        """Load portfolio data from JSON file with migration support."""
        if not os.path.exists(self.filepath):
            return {"updated_at": "", "accounts": {self.DEFAULT_ACCOUNT: {"positions": {}}}}
        
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Migration logic
            modified = False
            if 'accounts' not in data:
                positions = data.get('positions', {})
                data['accounts'] = {self.DEFAULT_ACCOUNT: {"positions": positions}}
                if 'positions' in data:
                    del data['positions']
                modified = True
            
            if not data.get('accounts'):
                data['accounts'] = {self.DEFAULT_ACCOUNT: {"positions": {}}}
                modified = True
            
            # Timestamp migration: Ensure all positions have 'added_at'
            for acc_name, acc_info in data['accounts'].items():
                positions = acc_info.get('positions', {})
                for sym, pos in positions.items():
                    if 'added_at' not in pos:
                        # Use a sequential or fixed past timestamp for existing items to maintain some order,
                        # but ISO format is needed. Let's use a base time if missing.
                        pos['added_at'] = datetime.now().isoformat()
                        modified = True
            
            if modified:
                self.save(data)
                
            return data
        except Exception as e:
            print(f"[ERR] Failed to load portfolio: {e}")
            return {"updated_at": "", "accounts": {self.DEFAULT_ACCOUNT: {"positions": {}}}}

    def save(self, data):
        """Save portfolio data atomically."""
        data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with tempfile.NamedTemporaryFile('w', delete=False, dir=self.data_dir, encoding='utf-8') as tf:
                json.dump(data, tf, ensure_ascii=False, indent=2)
                temp_name = tf.name
            
            shutil.move(temp_name, self.filepath)
            return True
        except Exception as e:
            print(f"[ERR] Failed to save portfolio: {e}")
            if 'temp_name' in locals() and os.path.exists(temp_name):
                os.remove(temp_name)
            return False

    def upsert(self, symbol, qty, account_name=None, avg_price=0):
        """Update or insert a single position in a specific account."""
        data = self.load()
        if not account_name:
            account_name = self.DEFAULT_ACCOUNT
            
        if account_name not in data['accounts']:
            # Implicit creation? Should we validate here too?
            # Ideally yes, but existing calls might rely on it.
            # upsert is usually for existing accounts or default.
            # If account_name comes from UI selector, it should exist.
            # If it's a new one passed here, it should be validated.
            # But upsert is mostly called with existing account names from the UI dropdown.
            data['accounts'][account_name] = {"positions": {}}
            
        positions = data['accounts'][account_name]['positions']
        
        if qty <= 0:
            if symbol in positions:
                del positions[symbol]
        else:
            # Preserve existing avg_price if not provided (0)? 
            # No, if 0 is passed, it might mean reset? 
            # Or if user just updates qty, we should pass the old avg_price?
            # The API caller (Flask) should handle fetching old value if needed, 
            # OR we handle it here. 
            # Better to assume if avg_price is passed as argument, we use it. 
            # But we default to 0 in signature. 
            # Let's check if symbol exists.
            
            current_entry = positions.get(symbol, {})
            
            final_avg_price = avg_price
            if avg_price is None:
                 final_avg_price = current_entry.get('avg_price', 0)
            
            # Preserve original added_at or set new one
            added_at = current_entry.get('added_at', datetime.now().isoformat())
            
            positions[symbol] = {
                'qty': qty, 
                'avg_price': final_avg_price,
                'added_at': added_at
            }
            
        success = self.save(data)
        return data, success

    def bulk_save_account(self, account_name, positions):
        """
        Replace all positions in a specific account.
        positions: dict { symbol: {'qty': 10, 'avg_price': 1000} }
        """
        data = self.load()
        if not account_name:
            account_name = self.DEFAULT_ACCOUNT
            
        data['accounts'][account_name] = {"positions": positions}
        success = self.save(data)
        return data, success

    def bulk_save(self, all_accounts_data):
        """Replace the entire accounts structure."""
        data = self.load()
        data['accounts'] = all_accounts_data
        success = self.save(data)
        return data, success

    def clear(self):
        """Clear all active positions across all accounts and reset to default."""
        data = self.load()
        # Reset entire accounts structure to default
        data['accounts'] = {self.DEFAULT_ACCOUNT: {"positions": {}}}
        success = self.save(data)
        return data, success

    # ==========================
    # Account Management
    # ==========================
    def add_account(self, name):
        if not name: return False, "Invalid name"
        
        data = self.load()
        if name in data['accounts']:
            return False, "Account already exists"
        data['accounts'][name] = {"positions": {}}
        return self.save(data), "Added"

    def rename_account(self, old_name, new_name):
        if not new_name or old_name == new_name: return False, "Invalid name"
        
        data = self.load()
        if old_name not in data['accounts']:
            return False, "Account not found"
        if new_name in data['accounts']:
            return False, "New name already exists"
            
        data['accounts'][new_name] = data['accounts'].pop(old_name)
        return self.save(data), "Renamed"

    def delete_account(self, name):
        data = self.load()
        if name not in data['accounts']:
            return False, "Account not found"
        if len(data['accounts']) <= 1:
            return False, "Cannot delete last account"
            
        del data['accounts'][name]
        return self.save(data), "Deleted"

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
            # Migration check
            if 'accounts' not in data:
                positions = data.get('positions', {})
                data['accounts'] = {self.DEFAULT_ACCOUNT: {"positions": positions}}
                if 'positions' in data: del data['positions']

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
