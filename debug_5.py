import os
import re

filepath = r'C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\student\templates\student_dashboard.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(r'<div\s+class=.user-menu-container.>', re.IGNORECASE)
match = pattern.search(content)
if match:
    print(f'Found: {match.group(0)}')
else:
    print('Not found')

