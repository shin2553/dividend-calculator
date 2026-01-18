import PyInstaller.__main__
import os
import shutil

def build():
    # Clean previous builds
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists('build'):
        shutil.rmtree('build')

    print("Starting PyInstaller build...")
    
    PyInstaller.__main__.run([
        'entry_point.py',
        '--name=KR_ETF_Dividend_Insight_v1.0.3',
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
        '--icon=NONE',
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
            shutil.copy(doc, os.path.join('dist', doc))

    print("\nBuild finished! Check the 'dist' folder for KR_ETF_Dividend_Insight_v1.0.3.exe")

if __name__ == "__main__":
    build()
