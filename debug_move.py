import os

base_dir = r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main"
subfolders = ["student", "teacher", "admin"]

for folder in subfolders:
    template_dir = os.path.join(base_dir, folder, "templates")
    if not os.path.exists(template_dir):
        print(f"Folder not found: {template_dir}")
        continue
    
    print(f"Checking folder: {template_dir}")
    for filename in os.listdir(template_dir):
        if filename.endswith(".html"):
            filepath = os.path.join(template_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            has_menu = '<div class="user-menu-container">' in content
            has_logo = '<div class="sidebar-logo">' in content
            print(f"  File: {filename}, has_menu: {has_menu}, has_logo: {has_logo}")
