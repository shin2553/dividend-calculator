import json
import os

DATA_FILE = 'portfolio.json'

def save_portfolio(portfolio_data):
    """
    Saves portfolio list to JSON file.
    """
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(portfolio_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving portfolio: {e}")
        return False

def load_portfolio():
    """
    Loads portfolio list from JSON file.
    """
    if not os.path.exists(DATA_FILE):
        return []
        
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading portfolio: {e}")
        return []
