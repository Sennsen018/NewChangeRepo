import re, os

base = r'c:\Users\XZONG\Desktop\Final-Attendeez - Copy\Main\student\templates'

def make_sidebar(active):
    # Main nav items
    items = [
        ('user.dashboard',          'fa-house',             'Student Dashboard',    'dashboard'),
        ('user.timetable',          'fa-calendar-alt',      'Class Timetable',      'timetable'),
        ('user.notifications_page', 'fa-bell',               'Notifications',        'notifications'),
        ('user.submit_excuse',      'fa-envelope-open-text', 'Excuse Letters',       'excuses'),
    ]
    
    nav_items = ''
    for route, icon, label, key in items:
        cls = 'nav-item active' if key == active else 'nav-item'
        badge = ''
        if key == 'notifications':
            badge = '{% if unread_count > 0 %}<span id="notif-badge-sidebar" class="badge badge-danger" style="margin-left: auto;">{{ unread_count }}</span>{% endif %}'
        
        nav_items += f'                <a href="{{{{ url_for(\'{route}\') }}}}" class="{cls}"><i class="fas {icon}"></i> {label} {badge}</a>\n'

    subject_loop = (
        '            <div class="nav-group" style="margin-top: 1.5rem;">\n'
        '                <p class="nav-label" style="font-size: 0.7rem; opacity: 0.8;">My Subjects</p>\n'
        '                {% for s in subjects %}\n'
        '                <a href="{{ url_for(\'user.subject_performance\', subject_id=s.subject_id) }}" class="nav-item" style="font-size: 0.85rem; padding: 0.6rem 1rem;">\n'
        '                    <i class="fas fa-book" style="font-size: 0.8rem;"></i> {{ s.subject_code }}\n'
        '                </a>\n'
        '                {% endfor %}\n'
        '            </div>\n'
    )

    return (
        '        <aside class="sidebar">\n'
        '            <div class="sidebar-logo">\n'
        '                <i class="fas fa-fingerprint"></i>\n'
        '                <span>Attendeez</span>\n'
        '            </div>\n'
        '            <nav class="sidebar-nav">\n'
        + nav_items +
        '            </nav>\n'
        + subject_loop +
        '            <div class="sidebar-bottom-actions">\n'
        '                <a href="{{ url_for(\'user.profile\') }}" class="btn btn-secondary w-full"><i class="fas fa-user-circle"></i> My Profile</a>\n'
        '                <a href="{{ url_for(\'auth.logout\') }}" class="btn btn-danger w-full"><i class="fas fa-sign-out-alt"></i> Logout</a>\n'
        '            </div>\n'
        '        </aside>'
    )

files = {
    'student_dashboard.html': 'dashboard',
    'timetable.html':         'timetable',
    'notifications.html':     'notifications',
    'submit_excuse.html':     'excuses',
    'profile.html':           None,
    'qr_scan.html':           None,
    'subject_view.html':      None,
}

for fname, active in files.items():
    fpath = os.path.join(base, fname)
    if not os.path.exists(fpath):
        print(f'File not found: {fname}')
        continue
        
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
        print(f'No change: {fname}')

print('Student sidebars update complete.')
