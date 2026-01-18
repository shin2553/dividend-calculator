
import os

file_path = r'c:\Users\MINI-PC\Downloads\dividend-calculator\kr_etf_investor\templates\index.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    # renderUniverse bgClass (Syntax Error)
    (
        "const bgClass = isInCurrent ? 'bg-[#121621] hover:bg-[#1a2030]' : (isInOther ? 'bg-[#0d1017]\n                        hover:bg-[#151a26]' : 'hover:bg-[#151515]');",
        "const bgClass = isInCurrent ? 'bg-[#121621] hover:bg-[#1a2030]' : (isInOther ? 'bg-[#0d1017] hover:bg-[#151a26]' : 'hover:bg-[#151515]');"
    ),
    # renderUniverse div.className (Ugly but valid JS)
    (
        "div.className = `grid grid-cols-12 px-4 py-4 border-b border-[#222] items-center cursor-pointer\n                        transition group ${bgClass}`;",
        "div.className = `grid grid-cols-12 px-4 py-4 border-b border-[#222] items-center cursor-pointer transition group ${bgClass}`;"
    ),
    # renderYieldMini (Ugly HTML)
    (
        "return `< div class=\"text-yield font-bold\" > ${ d.dist_ttm_yield.toFixed(2) }%</div>`;",
        "return `<div class=\"text-yield font-bold\">${d.dist_ttm_yield.toFixed(2)}%</div>`;"
    ),
    (
        "return `< div class=\"text-gray-400 font-bold\" > ${ d.est_annual_yield.toFixed(2) }% (E)</div>`;",
        "return `<div class=\"text-gray-400 font-bold\">${d.est_annual_yield.toFixed(2)}% (E)</div>`;"
    ),
    (
        "return `< div class=\"text-gray-600\" > -</div>`;",
        "return `<div class=\"text-gray-600\">-</div>`;"
    ),
    # renderYieldRight (Ugly HTML)
    (
        "< div class=\"text-sm font-bold text-white\" > 연 ${ d.dist_ttm_yield.toFixed(2) }%</div >",
        "<div class=\"text-sm font-bold text-white\">연 ${d.dist_ttm_yield.toFixed(2)}%</div>"
    ),
    (
        "< div class=\"text-sm font-bold text-white\" > 연 ${ d.est_annual_yield.toFixed(2) }%</div >",
        "<div class=\"text-sm font-bold text-white\">연 ${d.est_annual_yield.toFixed(2)}%</div>"
    ),
    (
        "return `< div class=\"text-sm text-gray-600\" > -</div>`;",
        "return `<div class=\"text-sm text-gray-600\">-</div>`;"
    )
]

new_content = content

# Helper to normalize newlines in replacement keys if needed
# My input string has \n, which matches file view. 
# But let's be careful about indentation.
# I'll use partial matching for the tricky bgClass one if exact fail.

for old, new in replacements:
    if old in new_content:
        new_content = new_content.replace(old, new)
        print("Replaced exact match.")
    else:
        # Try finding substrings
        pass

# Manual patch for bgClass exact content based on view_file (lines 1430-1431)
# 1430: const bgClass = isInCurrent ? 'bg-[#121621] hover:bg-[#1a2030]' : (isInOther ? 'bg-[#0d1017]
# 1431:                         hover:bg-[#151a26]' : 'hover:bg-[#151515]');
chunk_old = "const bgClass = isInCurrent ? 'bg-[#121621] hover:bg-[#1a2030]' : (isInOther ? 'bg-[#0d1017]\n                        hover:bg-[#151a26]' : 'hover:bg-[#151515]');"
chunk_new = "const bgClass = isInCurrent ? 'bg-[#121621] hover:bg-[#1a2030]' : (isInOther ? 'bg-[#0d1017] hover:bg-[#151a26]' : 'hover:bg-[#151515]');"

# If indent differs (checked 1431 has 24 spaces?)
# Step 487: "1431:                         hover:bg..." (24 spaces)
# My chunk_old has 24 spaces.

if chunk_old in new_content:
    new_content = new_content.replace(chunk_old, chunk_new)
    print("Replaced bgClass chunk.")
elif chunk_old.replace("                        ", "                         ") in new_content: # 25 spaces?
    new_content = new_content.replace(chunk_old.replace("                        ", "                         "), chunk_new)
    print("Replaced bgClass chunk (adjusted indent).")

# Clean up < div tags generally?
new_content = new_content.replace("< div ", "<div ")
new_content = new_content.replace("</div >", "</div>")
new_content = new_content.replace("< span", "<span") # Just in case
new_content = new_content.replace("</span >", "</span>")

# Verify change
if new_content != content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("File updated.")
else:
    print("No changes.")
