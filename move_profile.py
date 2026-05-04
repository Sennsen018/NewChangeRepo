import os
import re

directories = [
    (r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\student\templates", "user.profile"),
    (r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\teacher\templates", "teacher.profile")
]

# Pattern for the bottom profile button
profile_btn_pattern = re.compile(r'<a href="{{ url_for\(\'(?:user|teacher)\.profile\'\)\s*}}" class="btn btn-secondary[^>]*>.*?My Profile</a>', re.DOTALL)

for base_dir, profile_url in directories:
    if not os.path.exists(base_dir): continue
    for filename in os.listdir(base_dir):
        if filename.endswith(".html"):
            filepath = os.path.join(base_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if profile_url in content and "btn-secondary" in content:
                # 1. Remove the button from the bottom
                new_content = profile_btn_pattern.sub("", content)
                
                # 2. Add it to the top of sidebar-nav
                nav_item = f'<a href="{{{{ url_for(\'{profile_url}\') }}}}" class="nav-item"><i class="fas fa-user-circle"></i> My Profile</a>'
                new_content = new_content.replace('<nav class="sidebar-nav">', f'<nav class="sidebar-nav">\n                {nav_item}')
                
                # 3. Clean up empty sidebar-bottom-actions (handling both 2 and 4 space indents)
                new_content = re.sub(r'<div class="sidebar-bottom-actions">\s*</div>', "", new_content, flags=re.DOTALL)
                
                if new_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Updated {filename} in {os.path.basename(base_dir)}")

print("Done.")
