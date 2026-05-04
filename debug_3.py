import os

filepath = r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\student\templates\student_dashboard.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

header_tag = '<header class="top-header">'
header_idx = content.find(header_tag)
print(f"header_idx: {header_idx}")

if header_idx != -1:
    header_end = content.find('</header>', header_idx)
    header_content = content[header_idx:header_end]
    print(f"header_content len: {len(header_content)}")
    print(f"menu in header: {'<div class="user-menu-container">' in header_content}")

