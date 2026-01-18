from flask import Flask, render_template, jsonify, request
import flask
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta

APP_NAME = "KR ETF Dividend Insight"
VERSION = "1.0.1"
AUTHOR = "SHIN YONG HUI"

# Ensure root directory is in sys.path to find 'services'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from pykrx import stock
from .portfolio import PortfolioStorage
import threading
from . import loader
from services.calculator import calculate_div_simulation

def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if getattr(sys, 'frozen', False):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def get_data_path():
    """ Get path to persistent data, next to .exe if frozen """
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'data')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

# Initialize directories
base_path = get_base_path()
data_path = get_data_path()
if not os.path.exists(data_path):
    os.makedirs(data_path, exist_ok=True)

# Sync bundled data to external data folder on first run if missing
if getattr(sys, 'frozen', False):
    import shutil
    for filename in ['dividend_universe.json', 'manual_dividend_history.json']:
        bundled_file = os.path.join(base_path, 'data', filename)
        external_file = os.path.join(data_path, filename)
        if os.path.exists(bundled_file) and not os.path.exists(external_file):
            try:
                shutil.copy2(bundled_file, external_file)
                print(f"[pkg] Synced {filename} to external data folder")
            except Exception as e:
                print(f"[pkg] Failed to sync {filename}: {e}")

app = Flask(__name__, 
            template_folder=os.path.join(base_path, 'templates'))

portfolio_storage = PortfolioStorage(data_dir=data_path)

# Simple in-memory cache for price history: {ticker: {date: price, ...}}
# In a real app, use Redis or file cache.
PRICE_CACHE = {}
CACHE_EXPIRY = {} # ticker -> timestamp

# System Status
UPDATE_STATUS = {
    "is_running": False,
    "last_run": None,
    "message": "",
    "progress": 0,
    "summary": None # { "total": 0, "new": 0, "updated": 0 }
}
STOP_EVENT = threading.Event()

def update_progress(msg, pct):
    global UPDATE_STATUS
    UPDATE_STATUS["message"] = msg
    UPDATE_STATUS["progress"] = pct

def run_update_task(target_tickers=None):
    global UPDATE_STATUS
    try:
        UPDATE_STATUS["is_running"] = True
        UPDATE_STATUS["message"] = "Starting Update..."
        UPDATE_STATUS["progress"] = 0
        UPDATE_STATUS["summary"] = None
        print(f"[System] Update started. Targets: {len(target_tickers) if target_tickers else 'ALL'}")
        
        # 1. Load old data for comparison
        old_data = load_universe_data() or {}
        old_keys = set(old_data.keys())
        
        STOP_EVENT.clear()

        # 2. Run the loader with callback
        loader.load_data(progress_callback=update_progress, target_tickers=target_tickers, stop_event=STOP_EVENT)
        
        if STOP_EVENT.is_set():
            UPDATE_STATUS["message"] = "Update Cancelled"
            UPDATE_STATUS["is_running"] = False
            print("[System] Update cancelled by user.")
            return

        # 3. Load new data
        new_data = load_universe_data() or {}
        new_keys = set(new_data.keys())
        
        # 4. Compare
        new_items = new_keys - old_keys
        # simple logic: all existing keys are considered "updated" if they exist in new_keys
        updated_count = len(new_keys.intersection(old_keys))
        
        summary = {
            "total": len(new_keys),
            "new_count": len(new_items),
            "updated_count": updated_count,
            "new_symbols": list(new_items)
        }

        UPDATE_STATUS["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        UPDATE_STATUS["message"] = "Update Completed"
        UPDATE_STATUS["progress"] = 100
        UPDATE_STATUS["summary"] = summary
        
        print(f"[System] Update completed. Summary: {summary}")
        
    except Exception as e:
        UPDATE_STATUS["message"] = f"Error: {str(e)}"
        UPDATE_STATUS["progress"] = 0
        print(f"[System] Update failed: {e}")
    finally:
        UPDATE_STATUS["is_running"] = False

@app.route('/api/simulate', methods=['POST'])
def run_simulation():
    try:
        data = request.json
        # Convert params to format expected by calculator function if needed
        # Frontend sends matching keys: initial_principal, etc.
        # Ensure types (float/int)
        
        results = calculate_div_simulation(data)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def find_data_file():
    # Use absolute path relative to this script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, 'data', 'dividend_universe.json')
    if os.path.exists(file_path):
        return file_path
    return None

def load_universe_data():
    path = os.path.join(data_path, 'dividend_universe.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading universe: {e}")
            return None # Or return {} depending on desired behavior for corrupted file
    return {} # Return empty dict if file not found

@app.route('/')
def index():
    return render_template('index.html')

# ==========================
# API: Universe
# ==========================
@app.route('/api/universe', methods=['GET'])
def get_universe():
    data = load_universe_data()
    if data is None:
        return jsonify({'error': 'Universe data not found'}), 404
    
    # Return as list for easier frontend handling
    # {symbol, data: {...}} format
    result = []
    for symbol, info in data.items():
        result.append({
            "symbol": symbol,
            "data": info
        })
        
    return jsonify(result)

# Legacy support if needed, but /api/universe is preferred
@app.route('/api/etfs') 
def get_etfs():
    return get_universe()

# ==========================
# API: Portfolio
# ==========================
@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    try:
        data = portfolio_storage.load()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio', methods=['POST'])
def update_portfolio_item():
    """
    Body: {"symbol": "069500", "qty": 10}
    qty=0 means delete
    """
    try:
        req = request.json
        symbol = req.get('symbol')
        qty = req.get('qty')
        
        if symbol is None or qty is None:
            return jsonify({'error': 'Missing symbol or qty'}), 400
            
        data, success = portfolio_storage.upsert(str(symbol), int(qty))
        if not success:
            return jsonify({'error': 'Failed to save'}), 500
            
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio/bulk', methods=['POST'])
def update_portfolio_bulk():
    """
    Body: {"positions": {"069500": {"qty": 10}, ...}} 
    OR simplified: {"positions": {"069500": 10, ...}} -> handled by frontend usually sending strict format, 
    but let's support what we defined: body: {"positions":{"069500":10,"491620":5}} per user spec.
    Wait, user spec said: body: {"positions":{"069500":10,"491620":5}}
    PortfolioStorage expects: {'069500': {'qty': 10}} structure?
    Let's align.
    """
    try:
        req = request.json
        raw_positions = req.get('positions', {})
        
        # Convert simple kv to strict storage format if needed
        # Storage format: "069500": {"qty": 10}
        formatted_positions = {}
        for sym, val in raw_positions.items():
            # Handle both simple int and dict w/ qty
            qty = val
            if isinstance(val, dict):
                qty = val.get('qty', 0)
            
            if qty > 0:
                formatted_positions[sym] = {'qty': int(qty)}
        
        data, success = portfolio_storage.bulk_save(formatted_positions)
        if not success:
             return jsonify({'error': 'Failed to save'}), 500
             
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio/clear', methods=['POST'])
def clear_portfolio():
    """Clear all active positions."""
    try:
        data, success = portfolio_storage.clear()
        if not success:
            return jsonify({'error': 'Failed to clear portfolio'}), 500
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================
# API: Named Portfolios
# ==========================
@app.route('/api/portfolio/list', methods=['GET'])
def list_portfolios():
    try:
        names = portfolio_storage.list_portfolios()
        return jsonify(names)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio/save_as', methods=['POST'])
def save_portfolio_as():
    try:
        req = request.json
        name = req.get('name')
        if not name:
            return jsonify({'error': 'Name required'}), 400
            
        success, msg = portfolio_storage.save_as(name)
        if success:
            return jsonify({'message': msg, 'name': name})
        else:
            return jsonify({'error': msg}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio/load', methods=['POST'])
def load_portfolio_named():
    try:
        req = request.json
        name = req.get('name')
        if not name:
            return jsonify({'error': 'Name required'}), 400
            
        data, msg = portfolio_storage.load_named(name)
        if data:
            return jsonify({'message': msg, 'data': data})
        else:
            return jsonify({'error': msg}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio/delete', methods=['POST'])
def delete_portfolio_named():
    try:
        req = request.json
        name = req.get('name')
        if not name:
            return jsonify({'error': 'Name required'}), 400
        
        success, msg = portfolio_storage.delete_portfolio(name)
        if success:
            return jsonify({'message': msg})
        else:
            return jsonify({'error': msg}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio/export', methods=['GET'])
def export_portfolio():
    try:
        name = request.args.get('name')
        fmt = request.args.get('format', 'json') # json or csv
        
        data = None
        if name:
             # Load named portfolio data
            d = portfolio_storage.get_portfolios_dir()
            path = os.path.join(d, f"{name}.json")
            if not os.path.exists(path):
                return jsonify({'error': 'Portfolio not found'}), 404
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            filename_base = name
        else:
            # Load active
            data = portfolio_storage.load()
            filename_base = "active_portfolio"

        if fmt == 'csv':
            # Generate CSV
            output = "Ticker,Qty\n"
            positions = data.get('positions', {})
            for sym, info in positions.items():
                qty = info.get('qty', 0)
                output += f"{sym},{qty}\n"
            
            return flask.Response(
                output,
                mimetype="text/csv",
                headers={"Content-disposition": f"attachment; filename={filename_base}.csv"}
            )
        else:
            # Recursive load if we just want the file? 
            # If name is provided, we can just send the file.
            # If active, we save to temp or just json dump?
            # Existing logic sent file directly. Let's keep it consistent but flexible.
            if name:
                d = portfolio_storage.get_portfolios_dir()
                path = os.path.join(d, f"{name}.json")
                return flask.send_file(path, as_attachment=True, download_name=f"{filename_base}.json")
            else:
                path = portfolio_storage.filepath
                return flask.send_file(path, as_attachment=True, download_name=f"{filename_base}.json")

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio/import', methods=['POST'])
def import_portfolio():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
            
        if file:
            filename = file.filename
            ext = os.path.splitext(filename)[1].lower()
            name_base = os.path.splitext(filename)[0]
            
            # Allow specific name override via form data
            if 'name' in request.form and request.form['name']:
                name_base = request.form['name']

            positions = {}
            
            try:
                if ext == '.csv' or ext == '.txt':
                    # Parse CSV/Text: Ticker, Qty
                    # Assume no header or header "Ticker,Qty"
                    stream = file.read().decode('utf-8').splitlines()
                    for line in stream:
                        parts = line.split(',')
                        if len(parts) < 2: continue
                        t = parts[0].strip()
                        q = parts[1].strip()
                        if t.lower() == 'ticker': continue # Header
                        
                        # Validate ticker (digits)
                        if not t.isdigit() and not (len(t)==6): 
                            # Maybe extended ticker? Let's just create it.
                            pass
                            
                        try:
                            qty_val = int(float(q)) # Handle 10.0
                            if qty_val > 0:
                                positions[t] = {'qty': qty_val}
                        except: continue

                else:
                    # Default JSON
                    content = json.load(file)
                    if 'positions' in content:
                        # Full backup format
                        positions = content['positions']
                    else:
                        # Maybe simplified {"005930": 10}?
                        # Let's assume standard backup format for JSON
                        return jsonify({'error': 'Invalid JSON structure (missing positions)'}), 400

                # Save Check
                if not positions:
                     return jsonify({'warning': 'No valid positions found imported'}), 200

                # Construct Standard Format
                final_data = {
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "positions": positions
                }

                # Save to portfolios dir
                target_path = os.path.join(portfolio_storage.get_portfolios_dir(), f"{name_base}.json")
                with open(target_path, 'w', encoding='utf-8') as f:
                    json.dump(final_data, f, ensure_ascii=False, indent=2)
                    
                return jsonify({'message': 'Imported successfully', 'name': name_base, 'count': len(positions)})

            except Exception as e:
                return jsonify({'error': f"Parse Error: {str(e)}"}), 400
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================
# API: History (On-Demand)
# ==========================
@app.route('/api/history', methods=['POST'])
def get_history():
    """
    Body: { "tickers": ["069500", "491620"] }
    Returns: { "069500": [{"date": "2024-01-01", "price": 10000}, ...], ... }
    """
    try:
        req = request.json
        tickers = req.get('tickers', [])
        if not tickers:
            return jsonify({})

        # Cache check time
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).strftime("%Y%m%d")
        start_date = (now - timedelta(days=365)).strftime("%Y%m%d")
        end_date = now.strftime("%Y%m%d")
        
        result = {}
        
        for t in tickers:
            # Check Cache (Simple 24h expiry or primitive check)
            # For simplicity: if exists and not empty, use it. 
            # Ideally we check if it includes recent dates, but strictly speaking 
            # PyKRX calls are expensive so we want to maximize cache hit.
            if t in PRICE_CACHE and len(PRICE_CACHE[t]) > 0:
                # Refresh if too old? Let's just keep it simple for this session.
                # If we really want, check CACHE_EXPIRY
                if t in CACHE_EXPIRY and (now - CACHE_EXPIRY[t]).seconds < 3600 * 6:
                     result[t] = PRICE_CACHE[t]
                     continue

            # Fetch from KRX
            try:
                # optimization: don't fetch if non-numeric ticker (though all ETF are numeric)
                df = stock.get_etf_ohlcv_by_date(start_date, end_date, t)
                if df.empty:
                    # Try stock API just in case it's misclassified or mixed universe
                    df = stock.get_market_ohlcv_by_date(start_date, end_date, t)
                
                if not df.empty:
                    # Convert to list of dicts: {date: 'YYYY-MM-DD', price: 1234}
                    # DF index is datetime
                    history = []
                    for dt, row in df.iterrows():
                        history.append({
                            "date": dt.strftime("%Y-%m-%d"),
                            "price": int(row['종가'])
                        })
                    
                    PRICE_CACHE[t] = history
                    CACHE_EXPIRY[t] = now
                    result[t] = history
                else:
                    result[t] = []
            except Exception as e:
                print(f"Error fetching history for {t}: {e}")
                if t in PRICE_CACHE:
                    result[t] = PRICE_CACHE[t] # Fallback to old cache
                else:
                    result[t] = []

        return jsonify(result)
        
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

        return jsonify({'error': str(e)}), 500

# ==========================
# API: System / Data Update
# ==========================
@app.route('/api/system/info', methods=['GET'])
def get_system_info():
    return jsonify({
        "app_name": APP_NAME,
        "version": VERSION,
        "author": AUTHOR
    })

@app.route('/api/system/status', methods=['GET'])
def get_system_status():
    return jsonify(UPDATE_STATUS)

@app.route('/api/system/update', methods=['POST'])
def trigger_system_update():
    global UPDATE_STATUS
    if UPDATE_STATUS["is_running"]:
        return jsonify({'message': 'Update already in progress', 'status': UPDATE_STATUS}), 409
    
    # [Targeted Update]
    # To speed up user experience, we prioritize updating only:
    # 1. Tickers in current portfolio
    # 2. Popular tickers (e.g. top 50 by cap - though we don't have cap list easily)
    # 3. If 'full=true' param is passed, update all.
    
    full_update = request.args.get('full', 'false').lower() == 'true'
    target_tickers = None
    
    if not full_update:
        # Collect portfolio tickers
        pfl = portfolio_storage.load()
        p_tickers = list(pfl.keys())
        # Add Universe Seed tickers?
        # seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'universe_seed.json')
        # ... logic to load seeds ...
        # For simplicity, just update portfolio + default basic ones?
        # Actually, let's update ALL if portfolio is empty, otherwise just portfolio.
        if p_tickers:
            target_tickers = p_tickers
            # Also add some defaults like 069500 (KODEX 200) just in case
            if "069500" not in target_tickers: target_tickers.append("069500")

    # Wrapper to pass args
    def _run_wrapper():
        run_update_task(target_tickers)

    # Note: run_update_task signature needs update in flask_app.py too!

    # Start in background
    thread = threading.Thread(target=_run_wrapper)
    thread.daemon = True
    thread.start()
    
    return jsonify({'message': 'Update started', 'status': UPDATE_STATUS})

@app.route('/api/system/stop_update', methods=['POST'])
def stop_system_update():
    global UPDATE_STATUS
    if not UPDATE_STATUS["is_running"]:
         return jsonify({'message': 'No update running'}), 400
         
    STOP_EVENT.set()
    UPDATE_STATUS["message"] = "Stopping..."
    return jsonify({'message': 'Stop signal sent'})

@app.route('/api/system/shutdown', methods=['POST'])
def shutdown():
    """Shuts down the server and exits the process."""
    def kill_process():
        time.sleep(1.0) # Give time for the response to reach the client
        os._exit(0)
    
    threading.Thread(target=kill_process, daemon=True).start()
    return jsonify({"status": "shutting_down", "message": "Goodbye!"})

@app.route('/api/system/manual', methods=['POST'])
def open_manual():
    """Opens the user manual file."""
    try:
        manual_path = os.path.join(os.getcwd(), "Manual.md")
        if not os.path.exists(manual_path):
            # Try to find it in the data folder if bundled
            manual_path = os.path.join(get_base_path(), "Manual.md")
        
        if os.path.exists(manual_path):
            os.startfile(manual_path)
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Manual file not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)