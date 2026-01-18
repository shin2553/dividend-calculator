
import shutil
import os

# Define paths using raw strings to handle backslashes
src = r'c:\Users\MINI-PC\Downloads\dividend-calculator\backups\kr_etf_investor_backup_v1.0.3_20260103_1436\kr_etf_investor\templates\index.html'
dst = r'c:\Users\MINI-PC\Downloads\dividend-calculator\kr_etf_investor\templates\index.html'

try:
    if not os.path.exists(src):
        print(f"Error: Source file not found: {src}")
    else:
        shutil.copy2(src, dst)
        print(f"Successfully restored index.html from {src}")
except Exception as e:
    print(f"Error copying file: {e}")
