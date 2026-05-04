import os
import re

base_dir = r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main"
subfolders = ["student", "teacher", "admin"]

def move_menu(content, filename):
    if '<div class="user-menu-container">' not in content:
        print(f"  {filename}: menu container not found")
        return None
    if '<div class="sidebar-logo">' not in content:
        print(f"  {filename}: sidebar logo not found")
        return None
    
    if re.search(r'<div class="sidebar-logo">.*?<div class="user-menu-container">', content, re.DOTALL):
        print(f"  {filename}: already moved")
        return None

    start_tag = '<div class="user-menu-container">'
    start_idx = content.find(start_tag)
    
    stack = 0
    idx = start_idx
    end_idx = -1
    while idx < len(content):
        if content[idx:idx+4] == '<div':
            stack += 1
            idx += 4
        elif content[idx:idx+6] == '</div':
            stack -= 1
            idx += 6
            if stack == 0:
                end_idx = idx
                break
        else:
            idx += 1
    
    if end_idx == -1:
        print(f"  {filename}: end tag not found (stack: {stack})")
        return None
    
    print(f"  {filename}: found menu block (len: {end_idx - start_idx})")
    return "something"

for folder in subfolders:
    template_dir = os.path.join(base_dir, folder, "templates")
    if not os.path.exists(template_dir):
        continue
    
    print(f"Checking {folder}")
    for filename in os.listdir(template_dir):
        if filename.endswith(".html"):
            filepath = os.path.join(template_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            move_menu(content, filename)
