
import os

file_path = r'c:\Users\MINI-PC\Downloads\dividend-calculator\kr_etf_investor\templates\index.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Target the specific corrupted dist_warning block
# It has a distinct pattern with 'badge-warn' and 'onclick'
# I will use a simple replace of the multiline string if it matches
# or regex if indent is tricky.

old_block = """${d.dist_warning ? '<span class="badge-warn text-yellow-500 text-[10px] cursor-help border border-yellow-500 rounded px-1"
                            title="FnGuide 데이터 미제공/히스토리 파싱 실패/신규 상장 등"
                                    onclick="event.stopPropagation(); alert(\'FnGuide 데이터 미제공/히스토리 파싱 실패/신규 상장 등\')">정보없음</span>' : ''"""

new_block = """${d.dist_warning ? '<span class="badge-warn text-yellow-500 text-[10px] cursor-help border border-yellow-500 rounded px-1" title="FnGuide 데이터 미제공/히스토리 파싱 실패/신규 상장 등" onclick="event.stopPropagation(); alert(\'FnGuide 데이터 미제공/히스토리 파싱 실패/신규 상장 등\')">정보없음</span>' : ''"""

new_content = content
if old_block in new_content:
    new_content = new_content.replace(old_block, new_block)
    print("Replaced dist_warning block.")
else:
    # Try with adjusted indentation?
    # In Step 544:
    # 1448 starts with 29 spaces? (after ${d.dist_warning ?)
    # No, the code is:
    # 1448:                             ${d.dist_warning ? '<span class="badge-warn ...
    # 1449:                             title="FnGuide ...
    # 1450:                                     onclick="...
    
    # I'll just try to normalize spaces in the search
    pass

# Manual string construction based on visual inspection
# Matches the exact indentation from view_file if used carefully.

# Let's try flexible replacement
# Find unique start and end
start_marker = "${d.dist_warning ? '<span class=\"badge-warn"
end_marker = "\')\">정보없음</span>' : ''"

if start_marker in new_content:
    # Find the full block
    start_idx = new_content.find(start_marker)
    # Find end
    end_idx = new_content.find(end_marker, start_idx)
    if end_idx != -1:
        full_match = new_content[start_idx : end_idx + len(end_marker)]
        if "\n" in full_match:
             print("Found corrupted newline match.")
             new_content = new_content.replace(full_match, new_block)

# Fix HTML comment
new_content = new_content.replace("< !--Price -->", "<!-- Price -->")

if new_content != content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("File updated.")
else:
    print("No changes.")
