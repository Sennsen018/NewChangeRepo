import os
import re

directories = [
    r"C:\Users\Admin\OneDrive\Desktop\NewChangeRepo\Main\admin\templates"
]

# The correct sidebar from admin_dashboard.html
# Using single curly braces for Jinja and properly escaping quotes
correct_sidebar = """<aside class="sidebar">
            <div class="sidebar-logo">
                <div>
                    <i class="fas fa-fingerprint"></i>
                    <span>Attendeez</span>
                </div>
                <div class="user-menu-container">
                    <button class="burger-btn" onclick="toggleUserMenu()">
                        <i class="fas fa-ellipsis-v"></i>
                    </button>
                    <div id="user-dropdown" class="user-dropdown">
                        <div style="padding: 1rem; border-bottom: 1px solid var(--border-color); margin-bottom: 0.5rem;">
                            <p style="font-size: 0.85rem; font-weight: 600; color: var(--text-main); margin: 0;">{{ session.get('name', 'Admin') }}</p>
                            <p style="font-size: 0.75rem; color: var(--text-muted); margin: 0;">Administrator</p>
                        </div>
                        <a href="{{ url_for('auth.change_password') }}" class="dropdown-item">
                            <i class="fas fa-key"></i> Change Password
                        </a>
                        <a href="{{ url_for('auth.logout') }}" class="dropdown-item" style="color: var(--danger);">
                            <i class="fas fa-sign-out-alt"></i> Logout
                        </a>
                    </div>
                </div>
            </div>
            <nav class="sidebar-nav">
                <a href="{{ url_for('admin.dashboard') }}" class="nav-item {{ 'active' if request.endpoint == 'admin.dashboard' else '' }}"><i class="fas fa-house"></i> Admin Dashboard</a>
                <a href="{{ url_for('admin.manage_students') }}" class="nav-item {{ 'active' if request.endpoint == 'admin.manage_students' else '' }}"><i class="fas fa-user-graduate"></i> Manage Students</a>
                <a href="{{ url_for('admin.manage_teachers') }}" class="nav-item {{ 'active' if request.endpoint == 'admin.manage_teachers' else '' }}"><i class="fas fa-chalkboard-teacher"></i> Manage Teachers</a>
                <a href="{{ url_for('admin.manage_subjects') }}" class="nav-item {{ 'active' if request.endpoint == 'admin.manage_subjects' else '' }}"><i class="fas fa-book"></i> Manage Subjects</a>
                <a href="{{ url_for('admin.manual_enroll') }}" class="nav-item {{ 'active' if request.endpoint == 'admin.manual_enroll' else '' }}"><i class="fas fa-user-plus"></i> Manual Enrollment</a>
                <a href="{{ url_for('admin.assign_classes') }}" class="nav-item {{ 'active' if request.endpoint == 'admin.assign_classes' else '' }}"><i class="fas fa-link"></i> Assign Classes</a>
                <a href="{{ url_for('admin.manage_schedules') }}" class="nav-item {{ 'active' if request.endpoint == 'admin.manage_schedules' else '' }}"><i class="fas fa-calendar-alt"></i> Manage Schedules</a>
                <a href="{{ url_for('admin.attendance_analytics') }}" class="nav-item {{ 'active' if request.endpoint == 'admin.attendance_analytics' else '' }}"><i class="fas fa-chart-pie"></i> Attendance Analytics</a>
                <a href="{{ url_for('admin.drop_requests') }}" class="nav-item {{ 'active' if request.endpoint == 'admin.drop_requests' else '' }}"><i class="fas fa-user-minus"></i> Drop Requests</a>
                <a href="{{ url_for('admin.audit_logs') }}" class="nav-item {{ 'active' if request.endpoint == 'admin.audit_logs' else '' }}"><i class="fas fa-clipboard-list"></i> Audit Logs</a>
            </nav>
            <div class="sidebar-bottom-actions">
            </div>
        </aside>"""

top_header = """<header class="top-header">
                <button class="sidebar-toggle" onclick="toggleSidebar()">
                    <i class="fas fa-bars"></i>
                </button>
                <div class="header-left">
                    <h2 class="auth-title" style="font-size: 1.25rem; margin: 0;">Admin Portal</h2>
                </div>
            </header>"""

for base_dir in directories:
    if not os.path.exists(base_dir): continue
    for filename in os.listdir(base_dir):
        if filename.endswith(".html"):
            filepath = os.path.join(base_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace sidebar
            sidebar_pattern = re.compile(r'<aside class="sidebar">.*?</aside>', re.DOTALL)
            new_content = sidebar_pattern.sub(correct_sidebar, content)
            
            # Ensure top-header exists
            if '<header class="top-header">' not in new_content:
                # Insert it before main-content-inner
                new_content = new_content.replace('<div class="main-content-inner">', top_header + '\n\n            <div class="main-content-inner">')
            
            # Ensure main.js exists at the end
            if "static/js/main.js" not in new_content:
                new_content = new_content.replace('</body>', '<script src="{{ url_for(\'static\', filename=\'js/main.js\') }}"></script>\n</body>')

            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated {filename}")

print("Done.")
