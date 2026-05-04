import os
import re

def extract_block(content, start_tag):
    start_idx = content.find(start_tag)
    if start_idx == -1: return None, content
    
    # Use regex to find tags to avoid manual index issues
    tag_pattern = re.compile(r'<(/?div)[\s>]', re.IGNORECASE)
    
    stack = 0
    # Find all div tags after start_idx
    for match in tag_pattern.finditer(content, start_idx):
        tag = match.group(1).lower()
        if tag == 'div':
            stack += 1
        else:
            stack -= 1
        
        if stack == 0:
            end_idx = match.end()
            # If the match was <div ...> then match.end() is after div, not after >
            # Wait, our regex is <(/?div)[\s>]
            # If it matched </div>, it matches until >.
            # If it matched <div ..., it matches until the space or >.
            # We need to find the ACTUAL closing > of that div.
            
            # Find the closing > of the current tag
            closing_bracket = content.find('>', match.start())
            end_idx = closing_bracket + 1
            return content[start_idx:end_idx], content[:start_idx] + content[idx:] # idx is not defined here
            
    return None, content

# Re-implementing correctly
def extract_block_v2(content, start_tag):
    start_idx = content.find(start_tag)
    if start_idx == -1: return None, content
    
    stack = 0
    idx = start_idx
    while idx < len(content):
        # Match <div (start of tag)
        if content[idx:idx+4].lower() == '<div':
            # Check if it is a div tag and not just text starting with <div
            if idx + 4 < len(content) and content[idx+4] in (' ', '\n', '\t', '>'):
                stack += 1
                # Find the closing > of this opening tag
                idx = content.find('>', idx) + 1
                continue
        # Match </div (closing tag)
        if content[idx:idx+6].lower() == '</div':
            if idx + 6 < len(content) and content[idx+6] == '>':
                stack -= 1
                idx += 7 # past </div>
                if stack == 0:
                    return content[start_idx:idx], content[:start_idx] + content[idx:]
                continue
        idx += 1
    return None, content

filepath = r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\student\templates\student_dashboard.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

menu_block, without = extract_block_v2(content, '<div class="user-menu-container">')
print(f"menu_block: {menu_block is not None}")
if menu_block:
    print(f"menu_block len: {len(menu_block)}")

