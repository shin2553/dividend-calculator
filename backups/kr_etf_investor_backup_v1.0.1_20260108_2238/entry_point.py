import os
import sys
import webbrowser
import threading
import time
from PIL import Image, ImageDraw
import pystray
from kr_etf_investor.flask_app import app, APP_NAME

def open_browser():
    # Wait for server to start
    time.sleep(1.5)
    # Open the local ETF Dashboard
    webbrowser.open("http://127.0.0.1:5000")

def create_image():
    # Create a simple icon (Blue circle with white chart emoji-like arrow)
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), color=(17, 24, 39)) # Dark background
    dc = ImageDraw.Draw(image)
    dc.ellipse((8, 8, 56, 56), fill=(59, 130, 246)) # Blue circle
    # Simple line chart representation
    dc.line((16, 48, 28, 36, 40, 44, 48, 24), fill=(255, 255, 255), width=4)
    return image

def on_quit(icon, item):
    icon.stop()
    os._exit(0)

def on_open(icon, item):
    webbrowser.open("http://127.0.0.1:5001")

def setup_tray():
    try:
        menu = pystray.Menu(
            pystray.MenuItem("Open " + APP_NAME, on_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", on_quit)
        )
        icon = pystray.Icon("KR_ETF_Dividend_Insight", create_image(), APP_NAME, menu)
        icon.run()
    except Exception as e:
        print(f"Tray Icon Error: {e}")

if __name__ == "__main__":
    # Wait for server to start before opening browser
    def start_browser():
        time.sleep(2.0)
        webbrowser.open("http://127.0.0.1:5001")

    # Start browser in a separate thread
    threading.Thread(target=start_browser, daemon=True).start()
    
    # Start Tray in a separate thread
    tray_thread = threading.Thread(target=setup_tray, daemon=True)
    tray_thread.start()
    
    # Run server
    try:
        app.run(host="127.0.0.1", port=5001, debug=False)
    except Exception as e:
        print(f"Flask Server Error: {e}")
        os._exit(1)
