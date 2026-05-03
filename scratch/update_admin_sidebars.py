import re, os

base = r'c:\Users\XZONG\Desktop\Final-Attendeez - Copy\Main\admin\templates'

def make_admin_sidebar(active_key):
    items = [
        ('admin.dashboard',           'fa-house',             'Admin Dashboard',      'dashboard'),
        ('admin.manage_students',     'fa-user-graduate',     'Manage Students',       'students'),
        ('admin.manage_teachers',     'fa-chalkboard-teacher', 'Manage Teachers',       'teachers'),
        ('admin.manage_subjects',     'fa-book',              'Manage Subjects',       'subjects'),
        ('admin.manual_enroll',       'fa-user-plus',         'Manual Enrollment',     'enroll'),
        ('admin.assign_classes',      'fa-link',              'Assign Classes',        'assign'),
        ('admin.manage_schedules',    'fa-calendar-alt',      'Manage Schedules',      'schedules'),
        ('admin.attendance_analytics','fa-chart-pie',         'Attendance Analytics',  'analytics'),
        ('admin.drop_requests',       'fa-user-minus',        'Drop Requests',         'drops'),
        ('admin.audit_logs',          'fa-clipboard-list',    'Audit Logs',            'audit'),
    ]
    
    nav_items = ''
    for route, icon, label, key in items:
        cls = 'nav-item active' if key == active_key else 'nav-item'
        nav_items += f'                <a href="{{{{ url_for(\'{route}\') }}}}" class="{cls}"><i class="fas {icon}"></i> {label}</a>\n'

    return (
        '        <aside class="sidebar">\n'
        '            <div class="sidebar-logo">\n'
        '                <i class="fas fa-fingerprint"></i>\n'
        '                <span>Attendeez</span>\n'
        '            </div>\n'
        '            <nav class="sidebar-nav">\n'
        + nav_items +
        '            </nav>\n'
        '            <div class="sidebar-bottom-actions">\n'
        '                <a href="{{ url_for(\'auth.logout\') }}" class="btn btn-danger w-full"><i class="fas fa-sign-out-alt"></i> Logout</a>\n'
        '            </div>\n'
        '        </aside>'
    )

files = {
    'admin_dashboard.html':          'dashboard',
    'admin_manage_students.html':    'students',
    'admin_manage_teachers.html':    'teachers',
    'admin_manage_subjects.html':    'subjects',
    'manual_enroll.html':            'enroll',
    'admin_assign_classes.html':     'assign',
    'admin_manage_schedules.html':   'schedules',
    'admin_attendance_analytics.html':'analytics',
    'admin_drop_requests.html':      'drops',
    'admin_audit_logs.html':         'audit',
    'admin_view_report.html':        'dashboard', # Default to dashboard for reports
}

for fname, active_key in files.items():
    fpath = os.path.join(base, fname)
    if not os.path.exists(fpath):
        print(f"File not found: {fpath}")
        continue
        
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_sidebar = make_admin_sidebar(active_key)
    # Match from <aside class="sidebar"> to </aside>
    pattern = r'<aside class="sidebar">.*?</aside>'
    new_content = re.sub(pattern, new_sidebar, content, flags=re.DOTALL)

    if new_content != content:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated: {fname}')
    else:
        print(f'No change: {fname}')
