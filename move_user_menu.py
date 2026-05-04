import os
import re

base_dir = r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main"
subfolders = ["student", "teacher", "admin"]

def extract_menu_block(content, filename):
    header_start = content.find('<header class="top-header">')
    if header_start == -1: return None, content
    header_end = content.find('</header>', header_start)
    if header_end == -1: return None, content
    
    header_html = content[header_start:header_end]
    if 'class="user-menu-container"' not in header_html: return None, content
    
    menu_start_local = header_html.find('<div class="user-menu-container">')
    if menu_start_local == -1: 
        menu_start_local = header_html.find('<div class="user-menu-container"')
        if menu_start_local == -1: return None, content
    
    menu_start_abs = header_start + menu_start_local
    
    # Use regex to find all div tags
    # <div or </div>
    tag_re = re.compile(r'<(/?div)(\s|>|/)', re.IGNORECASE)
    
    stack = 0
    menu_end_abs = -1
    
    for match in tag_re.finditer(content, menu_start_abs):
        tag = match.group(1).lower()
        if tag == 'div':
            stack += 1
        else:
            stack -= 1
        
        if stack == 0:
            # Find the closing > of this </div> tag
            closing_idx = content.find('>', match.start())
            if closing_idx != -1:
                menu_end_abs = closing_idx + 1
                break
            
    if menu_end_abs == -1: 
        print(f"End of menu block not found in {filename} (stack: {stack})")
        return None, content
    
    menu_block = content[menu_start_abs:menu_end_abs]
    new_content = content[:menu_start_abs].rstrip() + "\n" + content[menu_end_abs:].lstrip()
    return menu_block, new_content

def inject_menu_into_sidebar(content, menu_block):
    logo_start = content.find('<div class="sidebar-logo">')
    if logo_start == -1: return content
    
    logo_end = content.find('</div>', logo_start)
    if logo_end == -1: return content
    
    logo_inner = content[logo_start + len('<div class="sidebar-logo">'):logo_end].strip()
    
    new_logo_inner = f"""
                <div>
                    {logo_inner}
                </div>
                {menu_block.strip()}
            """
    
    new_content = content[:logo_start + len('<div class="sidebar-logo">')] + new_logo_inner + content[logo_end:]
    return new_content

modified_count = 0
for folder in subfolders:
    template_path = os.path.join(base_dir, folder, "templates")
    if not os.path.exists(template_path): continue
    
    for filename in os.listdir(template_path):
        if filename.endswith(".html"):
            filepath = os.path.join(template_path, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            menu_block, content_without_menu = extract_menu_block(content, filename)
            if menu_block:
                final_content = inject_menu_into_sidebar(content_without_menu, menu_block)
                if final_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(final_content)
                    modified_count += 1
                    print(f"Updated {filename}")

print(f"Successfully updated {modified_count} files.")
