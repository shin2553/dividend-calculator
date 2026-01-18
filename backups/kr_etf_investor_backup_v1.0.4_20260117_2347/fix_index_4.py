
import os

file_path = r'c:\Users\MINI-PC\Downloads\dividend-calculator\kr_etf_investor\templates\index.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    (
        "select.innerHTML = dropdownNames.map(name => `< option value = \"${name}\"",
        "select.innerHTML = dropdownNames.map(name => `<option value=\"${name}\""
    ),
    (
        "${ name === currentAccountName ? 'selected' : '' }> ${ name }</option > `).join('');",
        "${ name === currentAccountName ? 'selected' : '' }>${name}</option>`).join('');"
    )
]

new_content = content
for old, new in replacements:
    if old in new_content:
        new_content = new_content.replace(old, new)
        print("Replaced typo.")
    else:
        # Try relaxed matching
        pass

# Also cleanup broad pattern for </option >
new_content = new_content.replace("</option >", "</option>")
new_content = new_content.replace("< option", "<option")
new_content = new_content.replace("value = \"", "value=\"")

# Inject Console Logs for Debugging
# Find function renderPortfolio() {
# Insert console.log at start
if "function renderPortfolio() {" in new_content:
    new_content = new_content.replace("function renderPortfolio() {", "function renderPortfolio() { console.log('DEBUG: renderPortfolio defined and called');")

if "async function loadPortfolio() {" in new_content:
    new_content = new_content.replace("async function loadPortfolio() {", "async function loadPortfolio() { console.log('DEBUG: loadPortfolio called');")

if "window.onload = function() {" in new_content:
    new_content = new_content.replace("window.onload = function() {", "window.onload = function() { console.log('DEBUG: window.onload called');")

# Also fix the weird "value = " in select loop if strict replace failed
# (The first replacement pair above might fail due to whitespace in map line)

if new_content != content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("File updated.")
else:
    print("No changes.")
