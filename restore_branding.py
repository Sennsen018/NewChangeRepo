import os
import re

directories = [
    r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\student\templates",
    r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\teacher\templates",
    r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\admin\templates"
]

# Using double quotes for the pattern and escaping internal quotes
logo_block_pattern = re.compile(r'<div class="logo-wrapper">.*?<img src="{{ url_for\(\'static\', filename=\'images/logo\.jpg\'\)\s*}}" alt="Attendeez Logo" class="main-logo">.*?</div>', re.DOTALL)

replacement = """<div>
                    <i class="fas fa-fingerprint"></i>
                    <span>Attendeez</span>
                </div>"""

for base_dir in directories:
    if not os.path.exists(base_dir): continue
    for filename in os.listdir(base_dir):
        if filename.endswith(".html"):
            filepath = os.path.join(base_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if "logo.jpg" in content:
                new_content = logo_block_pattern.sub(replacement, content)
                
                if new_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Updated {filename} in {os.path.basename(base_dir)}")

print("Done.")
