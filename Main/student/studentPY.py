from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from Main.db import get_db_connection, log_system_action
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import json
import os
from werkzeug.utils import secure_filename

user = Blueprint('user', __name__, template_folder='templates')

@user.before_request
def require_login():
    if 'user_id' not in session or session.get('role') != 'student':
        flash('Please login as student first.', 'error')
        return redirect(url_for('auth.student_login'))

@user.route('/dashboard')
def dashboard():
    usid = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get Enrolled Subjects with their specific stats
    cursor.execute("""
    SELECT s.subject_id, s.subject_code, s.subject_name, t.first_name as teacher_first, t.last_name as teacher_last
    FROM Enrollments e
    JOIN Teacher_Assignments ta ON e.assignment_id = ta.assignment_id
    JOIN Subjects s ON ta.subject_id = s.subject_id
    JOIN Teachers t ON ta.utid = t.utid
    WHERE e.usid = %s
    """, (usid,))
    subjects_raw = cursor.fetchall()
    
    subjects_with_stats = []
    overall_stats = {'Present': 0, 'Absent': 0, 'Late': 0}
    
    for s in subjects_raw:
        cursor.execute("""
            SELECT a.status, COUNT(*) as count 
            FROM Attendance a
            JOIN Sessions s_tab ON a.session_id = s_tab.session_id
            JOIN Teacher_Assignments ta ON s_tab.utid = ta.utid AND s_tab.subject_id = ta.subject_id AND s_tab.section = ta.section
            JOIN Enrollments e ON ta.assignment_id = e.assignment_id
            WHERE a.usid = %s AND s_tab.subject_id = %s AND e.usid = %s
            GROUP BY a.status
        """, (usid, s['subject_id'], usid))
        s_stats = {row['status']: row['count'] for row in cursor.fetchall()}
        s_total = sum(s_stats.values())
        s_present = s_stats.get('Present', 0)
        s_pct = (s_present / s_total * 100) if s_total > 0 else 100
        
        # Accumulate overall stats
        for status in overall_stats:
            overall_stats[status] += s_stats.get(status, 0)
            
        subjects_with_stats.append({
            **s,
            'stats': s_stats,
            'attendance_pct': round(s_pct, 1)
        })

    # Overall calculation
    total = sum(overall_stats.values())
    present = overall_stats.get('Present', 0)
    attendance_pct = (present / total * 100) if total > 0 else 100
    low_attendance = attendance_pct < 75
    
    # Get Notifications
    cursor.execute("SELECT * FROM Notifications WHERE usid = %s ORDER BY created_at DESC", (usid,))
    notifications = cursor.fetchall()
    unread_notifs = [n for n in notifications if not n['is_read']]
    
    cursor.close()
    conn.close()
    
    return render_template('student_dashboard.html', 
                           name=session.get('name'), 
                           subjects=subjects_with_stats,
                           attendance_pct=round(attendance_pct, 1),
                           low_attendance=low_attendance,
                           stats=overall_stats,
                           notifications=notifications,
                           unread_count=len(unread_notifs))

@user.route('/subject/<int:subject_id>')
def subject_performance(subject_id):
    usid = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get Subject Info and Teacher Info
    cursor.execute("""
        SELECT s.*, t.first_name as teacher_first, t.last_name as teacher_last, ta.section
        FROM Subjects s
        JOIN Teacher_Assignments ta ON s.subject_id = ta.subject_id
        JOIN Enrollments e ON ta.assignment_id = e.assignment_id
        JOIN Teachers t ON ta.utid = t.utid
        WHERE s.subject_id = %s AND e.usid = %s
    """, (subject_id, usid))
    subject = cursor.fetchone()
    
    if not subject:
        flash('Subject not found.', 'error')
        return redirect(url_for('user.dashboard'))
        
    # Get stats for this subject
    cursor.execute("""
        SELECT a.status, COUNT(*) as count 
        FROM Attendance a
        JOIN Sessions s_tab ON a.session_id = s_tab.session_id
        WHERE a.usid = %s AND s_tab.subject_id = %s
        GROUP BY a.status
    """, (usid, subject_id))
    stats = {row['status']: row['count'] for row in cursor.fetchall()}
    total = sum(stats.values())
    present = stats.get('Present', 0)
    attendance_pct = (present / total * 100) if total > 0 else 100

    # Get schedule for this subject
    cursor.execute("""
        SELECT sch.day_of_week, sch.start_time, sch.end_time, sch.room
        FROM schedule sch
        JOIN Teacher_Assignments ta ON sch.subject_id = ta.subject_id AND sch.section = ta.section AND sch.utid = ta.utid
        JOIN Enrollments e ON ta.assignment_id = e.assignment_id
        WHERE sch.subject_id = %s AND e.usid = %s
        ORDER BY CASE sch.day_of_week
            WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
            WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 WHEN 'Sunday' THEN 7
        END
    """, (subject_id, usid))
    schedules = cursor.fetchall()

    # Format times for display
    for sch in schedules:
        for key in ('start_time', 'end_time'):
            t = sch[key]
            if hasattr(t, 'strftime'):
                sch[key] = t.strftime('%I:%M %p')
            elif hasattr(t, 'total_seconds'):
                secs = int(t.total_seconds())
                h, m = secs // 3600, (secs % 3600) // 60
                sch[key] = f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"

    # Get Sidebar Data
    cursor.execute("""
    SELECT s.subject_id, s.subject_code, s.subject_name 
    FROM Enrollments e
    JOIN Teacher_Assignments ta ON e.assignment_id = ta.assignment_id
    JOIN Subjects s ON ta.subject_id = s.subject_id
    WHERE e.usid = %s
    """, (usid,))
    subjects = cursor.fetchall()
    
    cursor.execute("SELECT * FROM Notifications WHERE usid = %s AND is_read = FALSE", (usid,))
    unread_count = len(cursor.fetchall())
    
    cursor.close()
    conn.close()
    
    return render_template('subject_view.html',
                           subject=subject,
                           stats=stats,
                           attendance_pct=round(attendance_pct, 1),
                           subjects=subjects,
                           schedules=schedules,
                           unread_count=unread_count)

@user.route('/mark_notifications_read', methods=['POST'])
def mark_notifications_read():
    usid = session['user_id']
    data = request.get_json(silent=True) or {}
    notif_id = data.get('notification_id')
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    if notif_id:
        cursor.execute("UPDATE Notifications SET is_read = TRUE WHERE notification_id = %s AND usid = %s", (notif_id, usid))
    else:
        cursor.execute("UPDATE Notifications SET is_read = TRUE WHERE usid = %s", (usid,))
        
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})

@user.route('/delete_all_notifications', methods=['POST'])
def delete_all_notifications():
    usid = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Notifications WHERE usid = %s", (usid,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})

@user.route('/api/notifications')
def get_notifications():
    usid = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM Notifications WHERE usid = %s ORDER BY created_at DESC LIMIT 10", (usid,))
    notifications = cursor.fetchall()
    
    # Convert datetime to string for JSON serialization
    for n in notifications:
        if isinstance(n['created_at'], datetime):
            n['created_at'] = n['created_at'].strftime('%Y-%m-%d %H:%M')
            
    cursor.close()
    conn.close()
    return jsonify({'notifications': notifications})

@user.route('/notifications')
def notifications_page():
    usid = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get Enrolled Subjects for Sidebar
    cursor.execute("""
    SELECT s.subject_id, s.subject_code, s.subject_name 
    FROM Enrollments e
    JOIN Teacher_Assignments ta ON e.assignment_id = ta.assignment_id
    JOIN Subjects s ON ta.subject_id = s.subject_id
    WHERE e.usid = %s
    """, (usid,))
    subjects = cursor.fetchall()
    
    # Get all notifications
    cursor.execute("SELECT * FROM Notifications WHERE usid = %s ORDER BY created_at DESC", (usid,))
    notifications = cursor.fetchall()
    unread_count = len([n for n in notifications if not n['is_read']])
    
    cursor.close()
    conn.close()
    
    return render_template('notifications.html',
                           subjects=subjects,
                           notifications=notifications,
                           unread_count=unread_count,
                           name=session.get('name'))

@user.route('/scan_qr', methods=['GET'])
def scan_qr():
    usid = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get Enrolled Subjects for Sidebar
    cursor.execute("""
    SELECT s.subject_id, s.subject_code, s.subject_name 
    FROM Enrollments e
    JOIN Teacher_Assignments ta ON e.assignment_id = ta.assignment_id
    JOIN Subjects s ON ta.subject_id = s.subject_id
    WHERE e.usid = %s
    """, (usid,))
    subjects = cursor.fetchall()
    
    # Get Notifications for Sidebar
    cursor.execute("SELECT * FROM Notifications WHERE usid = %s ORDER BY created_at DESC", (usid,))
    notifications = cursor.fetchall()
    unread_count = len([n for n in notifications if not n['is_read']])

    subject_id = request.args.get('subject_id')
    cursor.execute("SELECT * FROM Subjects WHERE subject_id = %s", (subject_id,))
    current_subject = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return render_template('qr_scan.html', 
                           subject=current_subject,
                           subjects=subjects,
                           notifications=notifications,
                           unread_count=unread_count)

@user.route('/submit_attendance', methods=['POST'])
def submit_attendance():
    """
    Records a student's attendance.
    Validates session token, prevents duplicate attendance per student/date/subject,
    calculates distance using Haversine formula, and inserts the record.
    """
    data = request.json
    session_id = data.get('session_id')
    token = data.get('token')
    s_lat = data.get('lat')
    s_lon = data.get('lon')
    tab_switched = data.get('tab_switched', False)
    behavior_flags = data.get('behavior_flags', [])
    
    if tab_switched:
        behavior_flags.append("Tab Switched")
    
    usid = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # 1. Validate Session and Token
        cursor.execute("SELECT * FROM Sessions WHERE session_id = %s", (session_id,))
        ses = cursor.fetchone()
        
        if not ses:
            return jsonify({'success': False, 'message': 'Session not found.'})
        
        if ses['status'] != 'Active':
            return jsonify({'success': False, 'message': 'Session has already ended.'})
            
        if ses['random_token'] != token:
            return jsonify({'success': False, 'message': 'Invalid QR Token.'})
            
        if datetime.now() > ses['expires_at']:
            return jsonify({'success': False, 'message': 'QR Code has expired.'})

        # 2. Check if already marked (Same student + same date + same subject)
        cursor.execute("""
            SELECT a.attendance_id 
            FROM Attendance a
            JOIN Sessions s ON a.session_id = s.session_id
            WHERE a.usid = %s AND s.subject_id = %s AND a.scan_time::date = CURRENT_DATE
        """, (usid, ses['subject_id']))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Attendance already recorded for this subject today.'})

        # 3. Calculate Distance (Haversine Formula)
        import math
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371000 # radius of Earth in meters
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
            return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

        distance = haversine(float(s_lat), float(s_lon), float(ses['latitude']), float(ses['longitude']))
        
        # 4. Mark Validity and Flags
        is_valid = 'Valid'
        if distance > 100: # Example: more than 100 meters
            behavior_flags.append(f"Far Location: {round(distance)}m")
            is_valid = 'Invalid'
            
        if tab_switched:
            is_valid = 'Invalid'

        # 5. Insert Record
        status = 'Present' if is_valid == 'Valid' else 'Flagged'
        cursor.execute("""
            INSERT INTO Attendance 
            (session_id, usid, scan_time, status, remarks, is_valid, student_lat, student_lon, distance_meters, behavior_flags)
            VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s) RETURNING attendance_id
        """, (session_id, usid, status, f"Distance: {round(distance)}m", is_valid, s_lat, s_lon, distance, json.dumps(behavior_flags)))
        attendance_id = cursor.fetchone()['attendance_id']
        
        # Audit Logging
        log_system_action(cursor, 'Attendance', attendance_id, 'Create', usid, 'student', f"Attendance recorded via QR. Status: {status}")
        
        # Notification is now handled automatically by database triggers
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Attendance recorded successfully.'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'})
    finally:
        cursor.close()
        conn.close()


@user.route('/timetable')
def timetable():
    usid = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
    SELECT s.subject_code, s.subject_name, t.first_name, t.middle_name, t.last_name, 
           sch.day_of_week, sch.start_time, sch.end_time, sch.room, sch.section
    FROM Enrollments e
    JOIN Teacher_Assignments ta ON e.assignment_id = ta.assignment_id
    JOIN Subjects s ON ta.subject_id = s.subject_id
    JOIN schedule sch ON ta.subject_id = sch.subject_id AND ta.section = sch.section AND ta.utid = sch.utid
    JOIN Teachers t ON ta.utid = t.utid
    WHERE e.usid = %s
    """
    cursor.execute(query, (usid,))
    schedule_raw = cursor.fetchall()
    
    # Process schedule for grid
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_map = {day: i+2 for i, day in enumerate(days)} # Column index
    
    processed_schedule = []
    for item in schedule_raw:
        # Helper to convert time/timedelta to row index
        def get_row_index(t):
            # Postgres TIME columns return datetime.time objects
            if hasattr(t, 'total_seconds'): # MySQL compatibility
                total_seconds = t.total_seconds()
            else:
                total_seconds = (t.hour * 3600 + t.minute * 60 + t.second)
            
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds // 60) % 60)
            # Row index calculation: 7am is row 2. 30min intervals.
            return (hours * 2 + (1 if minutes >= 30 else 0)) - 14 + 2

        start_row = get_row_index(item['start_time'])
        end_row = get_row_index(item['end_time'])
        
        item['grid_column'] = day_map.get(item['day_of_week'], 0)
        item['grid_row_start'] = start_row
        item['grid_row_end'] = end_row
        processed_schedule.append(item)

    # Get Enrolled Subjects for Sidebar
    cursor.execute("""
    SELECT s.subject_id, s.subject_code, s.subject_name 
    FROM Enrollments e
    JOIN Teacher_Assignments ta ON e.assignment_id = ta.assignment_id
    JOIN Subjects s ON ta.subject_id = s.subject_id
    WHERE e.usid = %s
    """, (usid,))
    subjects = cursor.fetchall()
    
    # Get Notifications for Sidebar
    cursor.execute("SELECT * FROM Notifications WHERE usid = %s ORDER BY created_at DESC", (usid,))
    notifications = cursor.fetchall()
    unread_count = len([n for n in notifications if not n['is_read']])

    # Generate time slots for the left column (7 AM - 7 PM)
    time_labels = []
    for h in range(7, 19): # 7am to 6pm start times
        for m in [0, 30]:
            h2, m2 = (h, 30) if m == 0 else (h + 1, 0)
            
            p1 = "AM" if h < 12 else "PM"
            dh1 = h if h <= 12 else h - 12
            
            p2 = "AM" if h2 < 12 else "PM"
            dh2 = h2 if h2 <= 12 else h2 - 12
            
            time_labels.append(f"{dh1}:{m:02d} {p1} - {dh2}:{m2:02d} {p2}")

    cursor.close()
    conn.close()
    return render_template('timetable.html', 
                           schedule=processed_schedule, 
                           days=days, 
                           time_labels=time_labels,
                           subjects=subjects,
                           notifications=notifications,
                           unread_count=unread_count)

@user.route('/profile')
def profile():
    usid = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get Student Profile
    cursor.execute("SELECT * FROM Students WHERE usid = %s", (usid,))
    student = cursor.fetchone()
    
    # Get Enrolled Subjects with Teacher Info
    query = """
    SELECT s.subject_code, s.subject_name, ta.section, t.first_name, t.middle_name, t.last_name
    FROM Enrollments e
    JOIN Teacher_Assignments ta ON e.assignment_id = ta.assignment_id
    JOIN Subjects s ON ta.subject_id = s.subject_id
    LEFT JOIN Teachers t ON ta.utid = t.utid
    WHERE e.usid = %s
    """
    cursor.execute(query, (usid,))
    enrollments = cursor.fetchall()
    
    # Get Sidebar Data
    cursor.execute("""
    SELECT s.subject_id, s.subject_code, s.subject_name 
    FROM Enrollments e
    JOIN Teacher_Assignments ta ON e.assignment_id = ta.assignment_id
    JOIN Subjects s ON ta.subject_id = s.subject_id
    WHERE e.usid = %s
    """, (usid,))
    subjects = cursor.fetchall()
    
    cursor.execute("SELECT * FROM Notifications WHERE usid = %s ORDER BY created_at DESC", (usid,))
    notifications = cursor.fetchall()
    unread_count = len([n for n in notifications if not n['is_read']])
    
    cursor.close()
    conn.close()
    
    return render_template('profile.html', 
                           student=student, 
                           enrollments=enrollments,
                           subjects=subjects,
                           notifications=notifications,
                           unread_count=unread_count)

@user.route('/request_email_otp', methods=['POST'])
def request_email_otp():
    from Main.auth.loginPY import generate_otp, send_otp_email
    new_email = request.form.get('new_email')
    
    if not new_email:
        return jsonify({'success': False, 'message': 'Email is required.'})
        
    otp = generate_otp()
    session['email_change_otp'] = otp
    session['pending_new_email'] = new_email
    session['email_otp_expiry'] = (datetime.now() + timedelta(minutes=10)).timestamp()
    
    if send_otp_email(new_email, otp):
        return jsonify({'success': True, 'message': 'OTP sent to your new email.'})
    else:
        # Fallback for demo
        return jsonify({'success': True, 'message': f'Failed to send email. (Demo OTP: {otp})'})

@user.route('/verify_email_change', methods=['POST'])
def verify_email_change():
    entered_otp = request.form.get('otp')
    usid = session['user_id']
    
    if not entered_otp:
        return jsonify({'success': False, 'message': 'OTP is required.'})
        
    if datetime.now().timestamp() > session.get('email_otp_expiry', 0):
        return jsonify({'success': False, 'message': 'OTP has expired.'})
        
    if entered_otp == session.get('email_change_otp'):
        new_email = session.get('pending_new_email')
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("UPDATE Students SET email = %s WHERE usid = %s", (new_email, usid))
            conn.commit()
            
            # Clear session
            session.pop('email_change_otp', None)
            session.pop('pending_new_email', None)
            session.pop('email_otp_expiry', None)
            
            return jsonify({'success': True, 'message': 'Email updated successfully.'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Update failed: {str(e)}'})
        finally:
            cursor.close()
            conn.close()
    else:
        return jsonify({'success': False, 'message': 'Invalid OTP code.'})

@user.route('/submit_excuse', methods=['GET', 'POST'])
def submit_excuse():
    usid = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        class_data = request.form.get('class_id') # Format: subject_id|utid
        message = request.form.get('message')
        file = request.files.get('excuse_file')
        
        if not class_data or not message:
            flash('Please select a class and provide a reason.', 'error')
        elif len(message) > 600:
            flash('Reason/Message must not exceed 600 characters.', 'error')
            return redirect(url_for('user.submit_excuse'))
        else:
            try:
                subject_id, utid = class_data.split('|')
                
                # Check daily limit (max 3 per day)
                cursor.execute("""
                    SELECT COUNT(*) as count FROM Excuse_Letters
                    WHERE usid = %s AND created_at::date = CURRENT_DATE
                """, (usid,))
                if cursor.fetchone()['count'] >= 3:
                    flash('You have reached the maximum of 3 excuse letter submissions for today.', 'error')
                    return redirect(url_for('user.submit_excuse'))
                
                filename = None
                
                if file and file.filename != '':
                    # Ensure upload directory exists
                    upload_dir = os.path.join('Main', 'static', 'uploads', 'excuses')
                    try:
                        if not os.path.exists(upload_dir):
                            os.makedirs(upload_dir, exist_ok=True)
                    except OSError as e:
                        if e.errno == 30: # Read-only file system
                            flash('Server Error: File system is read-only. Please contact admin to configure cloud storage.', 'error')
                            return redirect(url_for('user.submit_excuse'))
                        raise e
                        
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    allowed_ext = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg'}
                    
                    if ext not in allowed_ext:
                        flash('Invalid file type. Only PDF, Word, and Images are allowed.', 'error')
                        return redirect(url_for('user.submit_excuse'))

                    # Check file size (< 10 MB)
                    file.seek(0, 2)  # seek to end
                    file_size = file.tell()
                    file.seek(0)     # reset
                    if file_size >= 10 * 1024 * 1024:
                        flash('File size must be less than 10 MB.', 'error')
                        return redirect(url_for('user.submit_excuse'))
                        
                    filename = secure_filename(f"{usid}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                    file_path = os.path.join(upload_dir, filename)
                    
                    try:
                        file.save(file_path)
                    except OSError as e:
                        if e.errno == 30: # Read-only file system
                            flash('Upload Failed: The server filesystem is read-only (likely Vercel). Persistent uploads require Cloud Storage (Supabase/S3).', 'error')
                            return redirect(url_for('user.submit_excuse'))
                        raise e

                cursor.execute("""
                    INSERT INTO Excuse_Letters (usid, utid, subject_id, message, file_path)
                    VALUES (%s, %s, %s, %s, %s) RETURNING letter_id
                """, (usid, utid, subject_id, message, filename))
                letter_id = cursor.fetchone()['letter_id']
                
                # Audit Logging
                log_system_action(cursor, 'Excuse_Letters', letter_id, 'Create', usid, 'student', f"Excuse letter submitted for Subject {subject_id}")
                conn.commit()
                flash('Excuse letter submitted successfully!', 'success')
                return redirect(url_for('user.submit_excuse'))
            except Exception as e:
                conn.rollback()
                flash(f'Error submitting excuse: {str(e)}', 'error')

    # GET request: Prepare data for the form
    # 1. Enrollments with Teacher Info
    query = """
    SELECT s.subject_id, s.subject_code, s.subject_name, ta.utid, t.first_name, t.middle_name, t.last_name
    FROM Enrollments e
    JOIN Teacher_Assignments ta ON e.assignment_id = ta.assignment_id
    JOIN Subjects s ON ta.subject_id = s.subject_id
    JOIN Teachers t ON ta.utid = t.utid
    WHERE e.usid = %s
    """
    cursor.execute(query, (usid,))
    enrollments = cursor.fetchall()
    
    # 2. Previous Letters
    cursor.execute("""
        SELECT el.*, s.subject_code, t.first_name, t.middle_name, t.last_name
        FROM Excuse_Letters el
        JOIN Subjects s ON el.subject_id = s.subject_id
        JOIN Teachers t ON el.utid = t.utid
        WHERE el.usid = %s
        ORDER BY el.created_at DESC
    """, (usid,))
    previous_letters = cursor.fetchall()
    
    # 3. Sidebar Data
    cursor.execute("""
    SELECT s.subject_id, s.subject_code, s.subject_name 
    FROM Enrollments e
    JOIN Teacher_Assignments ta ON e.assignment_id = ta.assignment_id
    JOIN Subjects s ON ta.subject_id = s.subject_id
    WHERE e.usid = %s
    """, (usid,))
    subjects = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) as count FROM Notifications WHERE usid = %s AND is_read = FALSE", (usid,))
    unread_count = cursor.fetchone()['count']
    
    cursor.close()
    conn.close()
    
    return render_template('submit_excuse.html', 
                           enrollments=enrollments, 
                           previous_letters=previous_letters,
                           subjects=subjects,
                           unread_count=unread_count,
                           name=session.get('name'))
