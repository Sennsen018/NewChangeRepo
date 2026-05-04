import os
import re

base_dir = r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main"

folders = {
    "student": "theme-student",
    "teacher": "theme-teacher",
    "admin": "theme-admin"
}

modified_count = 0

for folder, theme_class in folders.items():
    template_dir = os.path.join(base_dir, folder, "templates")
    if not os.path.exists(template_dir):
        continue
    
    for filename in os.listdir(template_dir):
        if filename.endswith(".html"):
            filepath = os.path.join(template_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            if theme_class in content:
                continue
            
            def body_repl(match):
                body_tag = match.group(0)
                if 'class="' in body_tag:
                    return body_tag.replace('class="', f'class="{theme_class} ')
                else:
                    return body_tag.replace('<body', f'<body class="{theme_class}"')
            
            new_content, count = re.subn(r'<body[^>]*>', body_repl, content)
            
            if count > 0:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                modified_count += 1
                print(f"Updated {filepath}")

print(f"Done. Modified {modified_count} files.")
