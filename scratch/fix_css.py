import os

file_path = r'Main\static\css\style.css'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Normalize line endings to \n for easier replacement
original_line_endings = '\r\n' if '\r\n' in content else '\n'
content = content.replace('\r\n', '\n')

# Restore loading text properties that were accidentally removed
loading_text_old = '.loading-text {\n    font-size: 0.85rem;\n    color: var(--text-muted);\n}'
loading_text_new = '.loading-text {\n    font-size: 0.85rem;\n    color: var(--text-muted);\n    font-weight: 500;\n    letter-spacing: 0.05em;\n}'
content = content.replace(loading_text_old, loading_text_new)

# Remove the first block of duplicated code
# The duplication starts with the first "PAGINATION" comment and ends before the second one.
start_marker = '/* =========================================\n   PAGINATION'
first_pos = content.find(start_marker)
second_pos = content.find(start_marker, first_pos + len(start_marker))

if first_pos != -1 and second_pos != -1:
    print(f"Removing duplicate block from {first_pos} to {second_pos}")
    content = content[:first_pos] + content[second_pos:]

# Convert back to original line endings
content = content.replace('\n', original_line_endings)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
