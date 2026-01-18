
import os
import re

file_path = r'c:\Users\MINI-PC\Downloads\dividend-calculator\kr_etf_investor\templates\index.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# We need to handle multi-line string matching carefully.
# The corrupted blocks usually look like this:
# ${isInCurrent ? '<span
#    class="pf-badge ... " > ... </span> ' ...

# I will use a regex-like approach or just replace chunks with generous whitespace matching.

replacements = [
    # isInCurrent badge
    (
        """${isInCurrent ? '<span
                                    class="pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-blue-600 text-white font-normal" > 보유중</span> '
                                : ''""",
        """${isInCurrent ? '<span class="pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-blue-600 text-white font-normal">보유중</span>' : ''"""
    ),
    # isInOther badge
    (
        """${
                    isInOther ? '<span
                                    class="pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 font-normal border border-gray-700" > 타
                                    계좌 보유</span> ' : ''}""",
        """${isInOther ? '<span class="pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 font-normal border border-gray-700">타 계좌 보유</span>' : ''}"""
    ),
    # dist_warning badge (Guessing the corruption based on others)
    (
        """${d.dist_warning ? '<span
                                    class="badge-warn text-yellow-500 text-[10px] cursor-help border border-yellow-500 rounded px-1"
                            title="FnGuide 데이터 미제공/히스토리 파싱 실패/신규 상장 등"
                                    onclick="event.stopPropagation(); alert(\'FnGuide 데이터 미제공/히스토리 파싱 실패/신규 상장 등\')">정보없음</span>'
                                : ''""",
        """${d.dist_warning ? '<span class="badge-warn text-yellow-500 text-[10px] cursor-help border border-yellow-500 rounded px-1" title="FnGuide 데이터 미제공/히스토리 파싱 실패/신규 상장 등" onclick="event.stopPropagation(); alert(\'FnGuide 데이터 미제공/히스토리 파싱 실패/신규 상장 등\')">정보없음</span>' : ''"""
    )
]

new_content = content

# Helper to remove newlines/spaces for matching if strict fails
# Or try to construct the exact broken string from the file view earlier.
# The file view lines were:
# 1442:                                 ${isInCurrent ? '<span
# 1443:                                     class="pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-blue-600 text-white font-normal" > 보유중</span> '
# 1444:                                 : ''

def normalize_space(s):
    return ' '.join(s.split())

for old, new in replacements:
    if old in new_content:
        new_content = new_content.replace(old, new)
        print("Replaced exact block.")
    else:
        # Try to find it by looser matching?
        # Actually, let's just search for the KEY parts and replace the whole block if found.
        pass

# Fallback: Replace known corrupted start/end sequences
# Badge 1
if "${isInCurrent ? '<span" in new_content and "보유중</span> '" in new_content:
   # regex replacement to collapse the multi-line string
   # Pattern: ${isInCurrent ? '<span ...whitespace... class= ...whitespace... > 보유중</span> '
   pass

# I will use a very specific replace based on what I saw in Step 517
# 1442:                                 ${isInCurrent ? '<span
# 1443:                                     class="pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-blue-600 text-white font-normal" > 보유중</span> '
# 1444:                                 : ''

chunk1_old = """${isInCurrent ? '<span
                                    class="pf-badge ml-2 text-[10px] px-1.5 py-0.5 rounded bg-blue-600 text-white font-normal" > 보유중</span> '
                                : ''"""
# The indentation in file might differ. I will try to match substring.
new_content = new_content.replace("' <span\n                                    class=", "'<span class=") 
# No, spaces differ.

# Brute force normalization
# I'll replace the specific broken fragments
new_content = new_content.replace("'<span\n                                    class=\"pf-badge", "'<span class=\"pf-badge")
new_content = new_content.replace("'<span\n                                    class=\"badge-warn", "'<span class=\"badge-warn")

# Fix the "> 보유중</span> " part which has space
new_content = new_content.replace("\" > 보유중</span> '", "\">보유중</span>'") 
new_content = new_content.replace("\" > 타\n                                    계좌 보유</span> '", "\">타 계좌 보유</span>'") 

# Fix the start of the strings
new_content = new_content.replace("${isInCurrent ? '<span\n", "${isInCurrent ? '<span ")
new_content = new_content.replace("${isInOther ? '<span\n", "${isInOther ? '<span ")
new_content = new_content.replace("${\n                    isInOther", "${isInOther") # Fix variable split if any

# Fix dist_warning
new_content = new_content.replace("${d.dist_warning ? '<span\n", "${d.dist_warning ? '<span ")
new_content = new_content.replace("</span>'\n                                : ''", "</span>' : ''")

# Final sanity check for </option>
new_content = new_content.replace("< option", "<option")
new_content = new_content.replace("</option >", "</option>")

if new_content != content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("File updated.")
else:
    print("No changes.")
