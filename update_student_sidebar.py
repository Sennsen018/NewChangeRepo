import os
import re

base_dir = r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\student\templates"

accordion_html = """
                <div class="nav-accordion">
                    <button class="nav-item-btn accordion-trigger" onclick="toggleAccordion(this)">
                        <i class="fas fa-graduation-cap"></i>
                        <span>My Classes</span>
                        <i class="fas fa-chevron-down arrow"></i>
                    </button>
                    <div class="accordion-content">
                        {% for s in subjects %}
                        <a href="{{ url_for('user.subject_performance', subject_id=s.subject_id) }}" class="nav-item">
                            <i class="fas fa-book"></i> {{ s.subject_code }}
                        </a>
                        {% endfor %}
                    </div>
                </div>
"""

for filename in os.listdir(base_dir):
    if filename.endswith(".html"):
        filepath = os.path.join(base_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "nav-accordion" in content: continue
        
        # Simpler search
        if 'Student\n                    Dashboard' in content or 'Student Dashboard' in content:
            # We'll just look for the </a> of the dashboard link
            parts = content.split('Student\n                    Dashboard </a>')
            if len(parts) < 2:
                parts = content.split('Student Dashboard </a>')
            
            if len(parts) >= 2:
                new_content = parts[0] + 'Student Dashboard </a>' + accordion_html + parts[1]
                
                # Try to remove old group
                if '<div class="nav-group"' in new_content:
                    g_start = new_content.find('<div class="nav-group"')
                    g_end = new_content.find('</div>', g_start) + 6
                    new_content = new_content[:g_start] + new_content[g_end:]
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated {filename}")

print("Done.")
