
import os

file_path = r'c:\Users\MINI-PC\Downloads\dividend-calculator\kr_etf_investor\templates\index.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    (
        "const bgClass = isInCurrent ? 'bg-[#121621] hover:bg-[#1a2030]' : (isInOther ? 'bg-[#0d1017]\n                    hover: bg - [#151a26]' : 'hover: bg - [#151515]');",
        "const bgClass = isInCurrent ? 'bg-[#121621] hover:bg-[#1a2030]' : (isInOther ? 'bg-[#0d1017] hover:bg-[#151a26]' : 'hover:bg-[#151515]');"
    ),
    (
        "listRow.className = `grid grid-cols-12 px-4 py-4 border-b border-[#222] items-center cursor-pointer\n                    transition group ${bgClass}`;",
        "listRow.className = `grid grid-cols-12 px-4 py-4 border-b border-[#222] items-center cursor-pointer transition group ${bgClass}`;"
    ),
    (
        "nameDiv.insertAdjacentHTML('beforeend', '<span\n                        class= \"pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-blue-600 text-white font-normal\" > 보유중</span > ');",
        "nameDiv.insertAdjacentHTML('beforeend', '<span class=\"pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-blue-600 text-white font-normal\">보유중</span>');"
    ),
    (
        "nameDiv.insertAdjacentHTML('beforeend', '<span\n                        class= \"pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 font-normal border border-gray-700\" > 타\n                        계좌 보유</span > ');",
        "nameDiv.insertAdjacentHTML('beforeend', '<span class=\"pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 font-normal border border-gray-700\">타 계좌 보유</span>');"
    )
]

new_content = content
for old, new in replacements:
    # Try normalized matching if exact fails?
    # Simply replace for now. The file view lines need to be combined.
    # The file view output showed newlines. I included \n in old strings.
    if old in new_content:
        new_content = new_content.replace(old, new)
        print("Replaced chunk.")
    else:
        # Try finding partials?
        # The file view might have different indent.
        # Let's try to be smarter.
        pass

# Since exact matching failed for me last time due to hidden whitespace,
# I will use a more robust search logic for these specific messy strings.
# I'll rely on unique substrings.

if "hover: bg - [#151515]" in new_content:
     # Start of bgClass block
     import re
     # Regex to match the corrupted bgClass line covering multiple lines
     pattern1 = re.escape("const bgClass = isInCurrent ? 'bg-[#121621] hover:bg-[#1a2030]' : (isInOther ? 'bg-[#0d1017]") + r"\s+hover:\s*bg\s*-\s*\[#151a26\]'\s*:\s*'hover:\s*bg\s*-\s*\[#151515\]'\);"
     # No, regex is hard with escaped chars.
     
     # I'll just use string replace of the KEY corrupted parts if unique.
     new_content = new_content.replace("hover: bg - [#151a26]'", "hover:bg-[#151a26]'")
     new_content = new_content.replace("hover: bg - [#151515]'", "hover:bg-[#151515]'")
     new_content = new_content.replace("bg-[#0d1017]\n                    hover:", "bg-[#0d1017] hover:") # Join lines

if "transition group ${bgClass}" in new_content:
    new_content = new_content.replace("cursor-pointer\n                    transition group", "cursor-pointer transition group")

if "class= \"pf-badge" in new_content:
    # Fix the span tags
    # "class= \"pf-badge ... > 보유중</span >"
    # Join lines first
    # This is tricky without risk.
    pass

# Direct replacement based on copied text from Step 468
# Pattern 1
p1_old = """const bgClass = isInCurrent ? 'bg-[#121621] hover:bg-[#1a2030]' : (isInOther ? 'bg-[#0d1017]
                    hover: bg - [#151a26]' : 'hover: bg - [#151515]');"""
p1_new = "const bgClass = isInCurrent ? 'bg-[#121621] hover:bg-[#1a2030]' : (isInOther ? 'bg-[#0d1017] hover:bg-[#151a26]' : 'hover:bg-[#151515]');"

# Pattern 2
p2_old = """listRow.className = `grid grid-cols-12 px-4 py-4 border-b border-[#222] items-center cursor-pointer
                    transition group ${bgClass}`;"""
p2_new = "listRow.className = `grid grid-cols-12 px-4 py-4 border-b border-[#222] items-center cursor-pointer transition group ${bgClass}`;"

# Pattern 3
p3_old = """nameDiv.insertAdjacentHTML('beforeend', '<span
                        class= "pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-blue-600 text-white font-normal" > 보유중</span > ');"""
p3_new = """nameDiv.insertAdjacentHTML('beforeend', '<span class="pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-blue-600 text-white font-normal">보유중</span>');"""

# Pattern 4
p4_old = """nameDiv.insertAdjacentHTML('beforeend', '<span
                        class= "pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 font-normal border border-gray-700" > 타
                        계좌 보유</span > ');"""
p4_new = """nameDiv.insertAdjacentHTML('beforeend', '<span class="pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 font-normal border border-gray-700">타 계좌 보유</span>');"""

for old, new in [(p1_old, p1_new), (p2_old, p2_new), (p3_old, p3_new), (p4_old, p4_new)]:
    if old in new_content:
        new_content = new_content.replace(old, new)
        print("Replaced block.")
    else:
        # Try aggressive whitespace normalization?
        # Maybe spaces are tabs?
        pass

if new_content != content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("File updated.")
else:
    print("No changes.")
