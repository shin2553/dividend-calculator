import PyInstaller.__main__
import os
import shutil
import re

# ==========================================
# CONFIGURATION
# ==========================================
PROJECT_NAME = "KR_ETF_Dividend_Insight"
VERSION = "v1.1.2"
TARGET_HTML = 'kr_etf_investor/templates/index.html'
# ==========================================

def update_version_in_files():
    """Updates version strings in the target HTML file."""
    print(f"Updating version to {VERSION} in {TARGET_HTML}...")
    
    if not os.path.exists(TARGET_HTML):
        print(f"Error: {TARGET_HTML} not found!")
        return

    with open(TARGET_HTML, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex patterns to find current versions
    # 1. Header: <span class="...">v1.0.X</span>
    # 2. Title: <title>... v1.0.X</title>
    # 3. About/Detail: Version 1.0.X (Stable)
    
    # Simple replacement logic: find "v1.0.X" or "Version 1.0.X" patterns
    
    # 1. Replace <title> tag version
    content = re.sub(r'(<title>.*?v)\d+\.\d+\.\d+(</title>)', fr'\g<1>{VERSION[1:]}\g<2>', content)
    
    # 2. Replace Header Badge "v1.0.X"
    # Looking for >v1.0.X< inside a span specifically might be tricky with regex if class varies, 
    # but based on our file it's: <span ...>v1.0.X</span>
    content = re.sub(r'>v\d+\.\d+\.\d+<', f'>{VERSION}<', content)

    # 3. Replace "Version 1.0.X (Stable)"
    content = re.sub(r'Version \d+\.\d+\.\d+ \(Stable\)', f'Version {VERSION[1:]} (Stable)', content)
    
    with open(TARGET_HTML, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Version updated successfully.")

def build():
    # Update Version Strings First
    update_version_in_files()

    # Clean previous builds
    if os.path.exists('dist'):
        # On Windows, sometimes file locking prevents immediate deletion. 
        # Ignoring errors might leave some files, but usually dist is recreated.
        shutil.rmtree('dist', ignore_errors=True)
    if os.path.exists('build'):
        shutil.rmtree('build', ignore_errors=True)

    print(f"Starting PyInstaller build for {VERSION}...")
    
    PyInstaller.__main__.run([
        'entry_point.py',
        f'--name={PROJECT_NAME}_{VERSION}',
        '--onefile',
        '--windowed',
        '--add-data=kr_etf_investor/templates;templates',
        '--add-data=kr_etf_investor/data/dividend_universe.json;data',
        '--add-data=kr_etf_investor/data/manual_dividend_history.json;data',
        '--add-data=Manual.md;.',
        '--add-data=ReleaseNotes.md;.',
        '--collect-all=pykrx',
        '--collect-all=pandas',
        '--collect-all=pystray',
        '--collect-all=PIL',
        '--icon=app.ico',
        '--hidden-import=jinja2',
        '--hidden-import=flask',
        '--hidden-import=services.calculator',
        '--hidden-import=kr_etf_investor.loader',
        '--hidden-import=kr_etf_investor.portfolio',
        '--hidden-import=kr_etf_investor.flask_app',
    ])

    # Copy documentation to dist
    for doc in ['Manual.md', 'ReleaseNotes.md']:
        if os.path.exists(doc):
            if not os.path.exists('dist'):
                os.makedirs('dist')
            shutil.copy(doc, os.path.join('dist', doc))

    print(f"\nBuild finished! Check the 'dist' folder for KR_ETF_Dividend_Insight_{VERSION}.exe")

if __name__ == "__main__":
    build()
