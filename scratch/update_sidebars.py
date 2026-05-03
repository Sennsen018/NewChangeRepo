import re, os

base = r'c:\Users\XZONG\Desktop\Final-Attendeez - Copy\Main\teacher\templates'

def make_sidebar(active):
    items = [
        ('teacher.dashboard',        'fa-house',             'Teacher Dashboard', 'dashboard'),
        ('teacher.manage_students',  'fa-users',             'Manage Students',   'students'),
        ('teacher.manual_attendance','fa-clipboard-check',   'Manual Attendance', 'attendance'),
        ('teacher.manage_marks',     'fa-star-half-alt',     'Manage Marks',      'marks'),
        ('teacher.view_excuses',     'fa-envelope-open-text','View Excuse Letters','excuses'),
        ('teacher.reports',          'fa-chart-bar',         'Reports',           'reports'),
    ]
    nav_items = ''
    for route, icon, label, key in items:
        cls = 'nav-item active' if key == active else 'nav-item'
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
        '                <a href="{{ url_for(\'teacher.profile\') }}" class="btn btn-secondary w-full"><i class="fas fa-user-circle"></i> My Profile</a>\n'
        '                <a href="{{ url_for(\'auth.logout\') }}" class="btn btn-danger w-full"><i class="fas fa-sign-out-alt"></i> Logout</a>\n'
        '            </div>\n'
        '        </aside>'
    )

files = {
    'teacher_dashboard.html':  'dashboard',
    'manual_attendance.html':  'attendance',
    'manage_students.html':    'students',
    'manage_marks.html':       'marks',
    'reports.html':            'reports',
    'view_excuses.html':       'excuses',
    'qr_generator.html':       'attendance',
    'teacher_profile.html':    None,
    'teacher_schedule.html':   'dashboard',
    'session_monitoring.html': 'dashboard',
}

for fname, active in files.items():
    fpath = os.path.join(base, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_sidebar = make_sidebar(active)
    pattern = r'<aside class="sidebar">.*?</aside>'
    new_content = re.sub(pattern, new_sidebar, content, flags=re.DOTALL)

    if new_content != content:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated: {fname}')
    else:
        print(f'No change (pattern not found): {fname}')
