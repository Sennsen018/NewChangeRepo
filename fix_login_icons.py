import os
import re

admin_file = r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\auth\templates\admin_login.html"
teacher_file = r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\auth\templates\teacher_login.html"

# Admin replacement
if os.path.exists(admin_file):
    with open(admin_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pattern = re.compile(r'<div class="brand-logo">.*?<span>Attendeez</span>.*?</div>', re.DOTALL)
    replacement = """<div class="brand-icon">
                <i class="fas fa-user-shield"></i>
            </div>
            <h1 class="brand-title">Attendeez</h1>"""
    
    new_content = pattern.sub(replacement, content)
    with open(admin_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Updated admin_login.html")

# Teacher replacement
if os.path.exists(teacher_file):
    with open(teacher_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pattern = re.compile(r'<div class="brand-logo">.*?<span>Attendeez</span>.*?</div>', re.DOTALL)
    replacement = """<div class="brand-icon">
                <i class="fas fa-chalkboard-teacher"></i>
            </div>
            <h1 class="brand-title">Attendeez</h1>"""
    
    new_content = pattern.sub(replacement, content)
    with open(teacher_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Updated teacher_login.html")
