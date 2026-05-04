import os
import re

def clean_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple regex to keep the HEAD version and discard the rest of the conflict
    # This assumes we want to keep the HEAD (current changes)
    cleaned = re.sub(r'<<<<<<< HEAD\n(.*?)\n=======\n(.*?)\n>>>>>>> [a-f0-9]+\n', r'\1\n', content, flags=re.DOTALL)
    
    # Also clean up simple empty markers if they exist
    cleaned = re.sub(r'<<<<<<< HEAD\n\n=======\n>>>>>>> [a-f0-9]+\n', '', cleaned)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(cleaned)

files = [
    r'c:\Users\XZONG\Desktop\Final-Attendeez - Copy\Main\admin\templates\admin_attendance_analytics.html',
    r'c:\Users\XZONG\Desktop\Final-Attendeez - Copy\Main\admin\templates\admin_drop_requests.html'
]

for file in files:
    if os.path.exists(file):
        print(f"Cleaning {file}...")
        clean_file(file)
    else:
        print(f"File not found: {file}")
