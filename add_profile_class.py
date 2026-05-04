import os
import re

directories = [
    (r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\student\templates", "user.profile"),
    (r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\teacher\templates", "teacher.profile")
]

for base_dir, profile_url in directories:
    if not os.path.exists(base_dir): continue
    for filename in os.listdir(base_dir):
        if filename.endswith(".html"):
            filepath = os.path.join(base_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find the nav item we just added
            pattern = re.compile(f'<a href="{{{{ url_for\(\'{profile_url}\'\) }}}}" class="nav-item">', re.DOTALL)
            replacement = f'<a href="{{{{ url_for(\'{profile_url}\') }}}}" class="nav-item profile-nav-item">'
            
            new_content = pattern.sub(replacement, content)
            
            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated {filename} in {os.path.basename(base_dir)}")

print("Done.")
