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
        '--name=KR_ETF_Dividend_Insight_v1.0.1',
        '--onefile',
        '--windowed',
        '--add-data=kr_etf_investor/templates;templates',
        '--add-data=kr_etf_investor/data/dividend_universe.json;data',
        '--add-data=kr_etf_investor/data/manual_dividend_history.json;data',
        '--collect-all=pykrx',
        '--collect-all=pandas',
        '--icon=NONE', # You can add an icon here
        '--hidden-import=jinja2',
        '--hidden-import=flask',
    ])

    # Copy documentation to dist
    for doc in ['Manual.md', 'ReleaseNotes.md']:
        if os.path.exists(doc):
            shutil.copy(doc, os.path.join('dist', doc))

    print("\nBuild finished! Check the 'dist' folder for KR_ETF_Dividend_Insight_v1.0.1.exe")

if __name__ == "__main__":
    build()
