from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
import json
from Main.db import get_db_connection, log_system_action
import uuid
import random
import string
from datetime import datetime, timedelta

teacher = Blueprint('teacher', __name__, template_folder='templates')

@teacher.before_request
def require_login():
    if 'user_id' not in session or session.get('role') != 'teacher':
        flash('Please login as teacher first.', 'error')
        return redirect(url_for('auth.teacher_login'))

@teacher.route('/dashboard')
def dashboard():
    uTID = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get Assigned Classes
    query = """
    SELECT s.subject_id, s.subject_code, s.subject_name, ta.section 
    FROM Teacher_Assignments ta
    JOIN Subjects s ON ta.subject_id = s.subject_id
    WHERE ta.uTID = %s
    """
    cursor.execute(query, (uTID,))
    classes = cursor.fetchall()
    
    # For each class, get some stats for the cards
    for c in classes:
        # Get count of enrolled students
        cursor.execute("SELECT COUNT(*) as count FROM Enrollments WHERE subject_id = %s AND section = %s", (c['subject_id'], c['section']))
        c['student_count'] = cursor.fetchone()['count']
        
        # Get today's attendance summary for this specific class
        cursor.execute("""
            SELECT a.status, COUNT(*) as count 
            FROM Attendance a
            JOIN Sessions s ON a.session_id = s.session_id
            WHERE s.uTID = %s AND s.subject_id = %s AND s.section = %s AND DATE(a.scan_time) = CURDATE()
            GROUP BY a.status
        """, (uTID, c['subject_id'], c['section']))
        stats = {row['status']: row['count'] for row in cursor.fetchall()}
        c['today_stats'] = stats
        c['today_present'] = stats.get('Present', 0)
        c['today_absent'] = stats.get('Absent', 0)
        c['today_late'] = stats.get('Late', 0)
    
    cursor.close()
    conn.close()
    
    return render_template('teacher_dashboard.html', 
                           name=session.get('name'), 
                           classes=classes)

@teacher.route('/profile')
def profile():
    uTID = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM Teachers WHERE uTID = %s", (uTID,))
    teacher_data = cursor.fetchone()

    # Assigned classes with subject info
    cursor.execute("""
        SELECT s.subject_code, s.subject_name, ta.section
        FROM Teacher_Assignments ta
        JOIN Subjects s ON ta.subject_id = s.subject_id
        WHERE ta.uTID = %s
        ORDER BY s.subject_code
    """, (uTID,))
    assignments = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('teacher_profile.html',
                           teacher=teacher_data,
                           assignments=assignments,
                           name=session.get('name'))

@teacher.route('/qr_generator', methods=['GET'])
def qr_generator():
    subject_id = request.args.get('subject_id')
    section = request.args.get('section')
    return render_template('qr_generator.html', subject_id=subject_id, section=section)

@teacher.route('/start_session', methods=['POST'])
def start_session():
    """
    Initiates a new attendance session for a given subject and section.
    Session duration defaults to 1 minute, with a max of 10.
    """
    data = request.json
    subject_id = data.get('subject_id')
    section = data.get('section')
    lat = data.get('lat')
    lon = data.get('lon')
    duration_mins = int(data.get('duration', 1)) # Default 1 min
    
    # Cap duration at 10 minutes
    if duration_mins > 10: duration_mins = 10
    if duration_mins < 1: duration_mins = 1
    
    uTID = session['user_id']
    session_id = f"session_{uuid.uuid4().hex[:8]}"
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    
    start_time = datetime.now()
    expires_at = start_time + timedelta(minutes=duration_mins)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Sessions (session_id, uTID, subject_id, section, random_token, start_time, expires_at, latitude, longitude, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Active')
        """, (session_id, uTID, subject_id, section, token, start_time, expires_at, lat, lon))
        
        # Audit Logging
        log_system_action(cursor, 'Sessions', session_id, 'Create', uTID, 'teacher', f"Session started for Subject {subject_id}, Section {section}")
        
        conn.commit()
        return jsonify({'success': True, 'session_id': session_id, 'token': token, 'expires_at': expires_at.isoformat()})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@teacher.route('/end_session', methods=['POST'])
def end_session():
    """
    Ends an active attendance session and automatically marks enrolled students
    who haven't scanned their QR code as 'Absent'.
    """
    data = request.json
    session_id = data.get('session_id')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Get session info
        cursor.execute("SELECT * FROM Sessions WHERE session_id = %s", (session_id,))
        ses = cursor.fetchone()
        if not ses:
            return jsonify({'success': False, 'message': 'Session not found'})

        # 2. Mark session as Ended
        cursor.execute("UPDATE Sessions SET status = 'Ended' WHERE session_id = %s", (session_id,))
        
        # Audit Logging
        log_system_action(cursor, 'Sessions', session_id, 'Update', session['user_id'], session.get('role', 'teacher'), "Session ended manually")
        
        # 3. Auto-Absent Logic: Mark enrolled students who didn't scan
        cursor.execute("""
            INSERT INTO Attendance (session_id, uSID, scan_time, status, remarks, is_valid)
            SELECT %s, e.uSID, NOW(), 'Absent', 'Auto-marked: Session ended', 'Valid'
            FROM Enrollments e
            LEFT JOIN Attendance a ON e.uSID = a.uSID AND a.session_id = %s
            WHERE e.subject_id = %s AND e.section = %s AND a.attendance_id IS NULL
        """, (session_id, session_id, ses['subject_id'], ses['section']))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@teacher.route('/session_monitoring/<session_id>')
def session_monitoring(session_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT ses.*, sub.subject_name, sub.subject_code 
        FROM Sessions ses
        JOIN Subjects sub ON ses.subject_id = sub.subject_id
        WHERE ses.session_id = %s
    """, (session_id,))
    session_data = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not session_data:
        flash('Session not found.', 'error')
        return redirect(url_for('teacher.dashboard'))
    return render_template('session_monitoring.html', session=session_data)

@teacher.route('/api/session_stats/<session_id>')
def get_session_stats(session_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            s.uSID, s.first_name, s.middle_name, s.last_name,
            a.status, a.scan_time, a.is_valid, a.behavior_flags, a.distance_meters
        FROM Sessions ses
        JOIN Enrollments e ON ses.subject_id = e.subject_id AND ses.section = e.section
        JOIN Students s ON e.uSID = s.uSID
        LEFT JOIN Attendance a ON s.uSID = a.uSID AND a.session_id = ses.session_id
        WHERE ses.session_id = %s
        ORDER BY s.last_name, s.first_name
    """, (session_id,))
    students = cursor.fetchall()
    
    for s in students:
        if s['behavior_flags']:
            try: s['behavior_flags'] = json.loads(s['behavior_flags'])
            except: s['behavior_flags'] = []
        else: s['behavior_flags'] = []
            
    cursor.close()
    conn.close()
    return jsonify({
        'students': students,
        'present_count': len([s for s in students if s['status'] == 'Present']),
        'total_count': len(students)
    })


@teacher.route('/manage_students', methods=['GET', 'POST'])
def manage_students():
    # Get the logged-in teacher's ID from the session
    uTID = session['user_id']
    subject_id = request.args.get('subject_id', type=int)
    section = request.args.get('section')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all assigned classes for the selector view
    cursor.execute("""
        SELECT s.subject_id, s.subject_code, s.subject_name, ta.section 
        FROM Teacher_Assignments ta
        JOIN Subjects s ON ta.subject_id = s.subject_id
        WHERE ta.uTID = %s
    """, (uTID,))
    uTID = session['user_id']
    subject_id = request.args.get('subject_id')
    section = request.args.get('section')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        sid = request.form.get('uSID')
        action = request.form.get('action')
        reason = request.form.get('reason', 'No reason provided')
        subj_id = request.form.get('subject_id')

        if action == 'request_drop':
            try:
                # Check if a pending request already exists
                cursor.execute("""
                    SELECT * FROM Drop_Requests 
                    WHERE uSID = %s AND subject_id = %s AND status = 'Pending'
                """, (sid, subj_id))
                if cursor.fetchone():
                    flash('A drop request for this student is already pending.', 'warning')
                else:
                    cursor.execute("""
                        INSERT INTO Drop_Requests (uTID, uSID, subject_id, reason)
                        VALUES (%s, %s, %s, %s)
                    """, (uTID, sid, subj_id, reason))
                    conn.commit()
                    flash('Drop request submitted to admin.', 'success')
            except Exception as e:
                flash(f'Error submitting request: {str(e)}', 'error')
        
        return redirect(url_for('teacher.manage_students', subject_id=subject_id, section=section))

    # Fetch classes for selection
    cursor.execute("""
        SELECT ta.*, s.subject_name, s.subject_code 
        FROM Teacher_Assignments ta
        JOIN Subjects s ON ta.subject_id = s.subject_id
        WHERE ta.uTID = %s
    """, (uTID,))
    classes = cursor.fetchall()

    selected_class = None
    students = []
    if subject_id and section:
        # Get class info
        cursor.execute("""
            SELECT ta.*, s.subject_name, s.subject_code 
            FROM Teacher_Assignments ta
            JOIN Subjects s ON ta.subject_id = s.subject_id
            WHERE ta.uTID = %s AND ta.subject_id = %s AND ta.section = %s
        """, (uTID, subject_id, section))
        selected_class = cursor.fetchone()

        if selected_class:
            if request.args.get('clear'):
                session.pop('teacher_students_search', None)
                return redirect(url_for('teacher.manage_students', subject_id=subject_id, section=section))

            # Persist search in session
            search_param = request.args.get('search')
            if search_param is not None:
                session['teacher_students_search'] = search_param.strip()
            search = session.get('teacher_students_search', '')
    

            # Get students in this class with search filter
            query = """
                SELECT s.* 
                FROM Students s
                JOIN Enrollments e ON s.uSID = e.uSID
                WHERE e.subject_id = %s AND e.section = %s
            """
            params = [subject_id, section]
            
            if search:
                query += " AND (s.first_name LIKE %s OR s.middle_name LIKE %s OR s.last_name LIKE %s OR s.uSID LIKE %s)"
                search_val = f"%{search}%"
                params.extend([search_val, search_val, search_val, search_val])
            
            query += " ORDER BY s.last_name"
            cursor.execute(query, params)
            students = cursor.fetchall()
            

    cursor.close()
    conn.close()
    return render_template('manage_students.html', 
                           classes=classes, 
                           selected_class=selected_class, 
                           students=students,
                           search=session.get('teacher_students_search', ''),
                           name=session.get('name'))

@teacher.route('/reports')
def reports():
    uTID = session['user_id']
    subject_id = request.args.get('subject_id', type=int)
    section = request.args.get('section')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch all assigned classes to show in the selector
    cursor.execute("""
        SELECT s.subject_id, s.subject_code, s.subject_name, ta.section 
        FROM Teacher_Assignments ta
        JOIN Subjects s ON ta.subject_id = s.subject_id
        WHERE ta.uTID = %s
    """, (uTID,))
    classes = cursor.fetchall()
    
    summary = []
    daily_logs = []
    daily_trends = []
    weekly_trends = []
    monthly_trends = []
    selected_class = None
    
    if subject_id and section:
        # Find the specific class details
        for c in classes:
            if c['subject_id'] == subject_id and c['section'] == section:
                selected_class = c
                break
        
        if selected_class:
            # Summary Report: Specific to THIS subject + section
            query_summary = """
            SELECT s.uSID, s.first_name, s.middle_name, s.last_name,
                   COUNT(a.attendance_id) as total_classes,
                   SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as days_present,
                   SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as days_absent,
                   SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as days_late,
                   SUM(CASE WHEN a.status = 'Flagged' THEN 1 ELSE 0 END) as days_flagged
            FROM Students s
            JOIN Enrollments e ON s.uSID = e.uSID
            LEFT JOIN Attendance a ON s.uSID = a.uSID 
                AND a.attendance_id IN (
                    SELECT MAX(a2.attendance_id)
                    FROM Attendance a2
                    JOIN Sessions ses2 ON a2.session_id = ses2.session_id
                    WHERE ses2.uTID = %s AND ses2.subject_id = %s AND ses2.section = %s
                    GROUP BY DATE(a2.scan_time), a2.uSID
                )
            WHERE e.subject_id = %s AND e.section = %s
            GROUP BY s.uSID
            """
            cursor.execute(query_summary, (uTID, subject_id, section, subject_id, section))
            summary = cursor.fetchall()
            
            for row in summary:
                if row['total_classes'] > 0:
                    row['percentage'] = round((row['days_present'] / row['total_classes']) * 100, 1)
                else:
                    row['percentage'] = 0.0

            # Daily Report: Raw Logs
            query_daily = """
            SELECT DATE(a.scan_time) as date, s.first_name, s.middle_name, s.last_name, a.status, a.is_valid
            FROM Attendance a
            JOIN (
                SELECT MAX(a2.attendance_id) as max_id
                FROM Attendance a2
                JOIN Sessions ses2 ON a2.session_id = ses2.session_id
                WHERE ses2.uTID = %s AND ses2.subject_id = %s AND ses2.section = %s
                GROUP BY DATE(a2.scan_time), a2.uSID
            ) max_a ON a.attendance_id = max_a.max_id
            JOIN Students s ON a.uSID = s.uSID
            ORDER BY date DESC, s.last_name ASC, s.first_name ASC
            """
            cursor.execute(query_daily, (uTID, subject_id, section))
            daily_logs = cursor.fetchall()
            # Convert date objects to strings so Jinja groupby works correctly
            for row in daily_logs:
                if row['date'] and not isinstance(row['date'], str):
                    row['date'] = row['date'].strftime('%Y-%m-%d')

            # Daily Trends
            cursor.execute("""
                SELECT DATE(a.scan_time) as period,
                       COUNT(a.attendance_id) as total_scans,
                       SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
                       SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
                       SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as late_count,
                       SUM(CASE WHEN a.status = 'Flagged' THEN 1 ELSE 0 END) as flagged_count
                FROM Attendance a
                JOIN (
                    SELECT MAX(a2.attendance_id) as max_id
                    FROM Attendance a2
                    JOIN Sessions ses2 ON a2.session_id = ses2.session_id
                    WHERE ses2.uTID = %s AND ses2.subject_id = %s AND ses2.section = %s
                    GROUP BY DATE(a2.scan_time), a2.uSID
                ) max_a ON a.attendance_id = max_a.max_id
                GROUP BY DATE(a.scan_time)
                ORDER BY period DESC
            """, (uTID, subject_id, section))
            daily_trends = cursor.fetchall()

            # Weekly Trends - Week 1-4 of each month with actual date range
            cursor.execute("""
                SELECT CONCAT('Week ', CEIL(DAY(a.scan_time) / 7), ' - ', MONTHNAME(a.scan_time), ' ', YEAR(a.scan_time)) as period,
                       YEAR(a.scan_time) as yr,
                       MONTH(a.scan_time) as mo,
                       CEIL(DAY(a.scan_time) / 7) as wk,
                       MIN(DATE(a.scan_time)) as week_start,
                       MAX(DATE(a.scan_time)) as week_end,
                       COUNT(a.attendance_id) as total_scans,
                       SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
                       SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
                       SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as late_count,
                       SUM(CASE WHEN a.status = 'Flagged' THEN 1 ELSE 0 END) as flagged_count
                FROM Attendance a
                JOIN (
                    SELECT MAX(a2.attendance_id) as max_id
                    FROM Attendance a2
                    JOIN Sessions ses2 ON a2.session_id = ses2.session_id
                    WHERE ses2.uTID = %s AND ses2.subject_id = %s AND ses2.section = %s
                    GROUP BY DATE(a2.scan_time), a2.uSID
                ) max_a ON a.attendance_id = max_a.max_id
                GROUP BY YEAR(a.scan_time), MONTH(a.scan_time), CEIL(DAY(a.scan_time) / 7), period
                ORDER BY yr ASC, mo ASC, wk ASC
            """, (uTID, subject_id, section))
            weekly_trends = cursor.fetchall()
            for row in weekly_trends:
                if row['week_start'] and not isinstance(row['week_start'], str):
                    row['week_start'] = row['week_start'].strftime('%b %d')
                if row['week_end'] and not isinstance(row['week_end'], str):
                    row['week_end'] = row['week_end'].strftime('%b %d, %Y')

            # Monthly Trends - January through December with year
            cursor.execute("""
                SELECT CONCAT(MONTHNAME(a.scan_time), ' ', YEAR(a.scan_time)) as period,
                       YEAR(a.scan_time) as yr,
                       MONTH(a.scan_time) as mo,
                       COUNT(a.attendance_id) as total_scans,
                       SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
                       SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
                       SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as late_count,
                       SUM(CASE WHEN a.status = 'Flagged' THEN 1 ELSE 0 END) as flagged_count
                FROM Attendance a
                JOIN (
                    SELECT MAX(a2.attendance_id) as max_id
                    FROM Attendance a2
                    JOIN Sessions ses2 ON a2.session_id = ses2.session_id
                    WHERE ses2.uTID = %s AND ses2.subject_id = %s AND ses2.section = %s
                    GROUP BY DATE(a2.scan_time), a2.uSID
                ) max_a ON a.attendance_id = max_a.max_id
                GROUP BY YEAR(a.scan_time), MONTH(a.scan_time), period
                ORDER BY yr ASC, mo ASC
            """, (uTID, subject_id, section))
            monthly_trends = cursor.fetchall()


            # Overall Stats for Pie Chart: Specific to THIS subject + section
            cursor.execute("""
                SELECT a.status, COUNT(*) as count 
                FROM Attendance a
                JOIN (
                    SELECT MAX(a2.attendance_id) as max_id
                    FROM Attendance a2
                    JOIN Sessions ses2 ON a2.session_id = ses2.session_id
                    WHERE ses2.uTID = %s AND ses2.subject_id = %s AND ses2.section = %s
                    GROUP BY DATE(a2.scan_time), a2.uSID
                ) max_a ON a.attendance_id = max_a.max_id
                GROUP BY a.status
            """, (uTID, subject_id, section))
            class_stats = {row['status']: row['count'] for row in cursor.fetchall()}

    # Check if a report has already been submitted for this class
    already_submitted = False
    if selected_class:
        cursor.execute("""
            SELECT COUNT(*) as count FROM Submitted_Reports 
            WHERE uTID = %s AND subject_id = %s AND section = %s
        """, (uTID, subject_id, section))
        already_submitted = cursor.fetchone()['count'] > 0
    
    cursor.close()
    conn.close()
    return render_template('reports.html', 
                           summary=summary, 
                           daily_logs=daily_logs, 
                           daily_trends=daily_trends,
                           weekly_trends=weekly_trends,
                           monthly_trends=monthly_trends,
                           classes=classes, 
                           selected_class=selected_class,
                           class_stats=class_stats if selected_class else {},
                           already_submitted=already_submitted)

@teacher.route('/submit_report', methods=['POST'])
def submit_report():
    uTID = session['user_id']
    subject_id = request.form.get('subject_id', type=int)
    section = request.form.get('section')
    teacher_message = request.form.get('teacher_message', '').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Calculate the summary (snapshot of current status)
    query_summary = """
    SELECT s.uSID, s.first_name, s.middle_name, s.last_name,
           COUNT(a.attendance_id) as total_classes,
           SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as days_present,
           SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as days_absent,
           SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as days_late,
           SUM(CASE WHEN a.status = 'Flagged' THEN 1 ELSE 0 END) as days_flagged
    FROM Students s
    JOIN Enrollments e ON s.uSID = e.uSID
    LEFT JOIN Attendance a ON s.uSID = a.uSID 
        AND a.attendance_id IN (
            SELECT MAX(a2.attendance_id)
            FROM Attendance a2
            JOIN Sessions ses2 ON a2.session_id = ses2.session_id
            WHERE ses2.uTID = %s AND ses2.subject_id = %s AND ses2.section = %s
            GROUP BY DATE(a2.scan_time), a2.uSID
        )
    WHERE e.subject_id = %s AND e.section = %s
    GROUP BY s.uSID
    """
    cursor.execute(query_summary, (uTID, subject_id, section, subject_id, section))
    summary = cursor.fetchall()
    
    # Convert Decimals to serializable types (MySQL SUM returns Decimals)
    for row in summary:
        row['days_present'] = int(row['days_present']) if row['days_present'] is not None else 0
        row['days_absent'] = int(row['days_absent']) if row['days_absent'] is not None else 0
        row['days_late'] = int(row['days_late']) if row['days_late'] is not None else 0
        row['days_flagged'] = int(row['days_flagged']) if row['days_flagged'] is not None else 0
        
        if row['total_classes'] > 0:
            row['percentage'] = round((row['days_present'] / row['total_classes']) * 100, 1)
        else:
            row['percentage'] = 0.0
            
    # Save the snapshot to Submitted_Reports table
    summary_json = json.dumps(summary)
    cursor.execute("""
        INSERT INTO Submitted_Reports (uTID, subject_id, section, summary_json, teacher_message)
        VALUES (%s, %s, %s, %s, %s)
    """, (uTID, subject_id, section, summary_json, teacher_message))
    
    
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('files successfully sent to the admin', 'success')
    return redirect(url_for('teacher.reports', subject_id=subject_id, section=section))

@teacher.route('/delete_daily_attendance', methods=['POST'])
def delete_daily_attendance():
    """
    Deletes all attendance records for a specific class on a specific date.
    Logs each deletion action into Attendance_Audit_Log.
    """
    uTID = session['user_id']
    role = session.get('role', 'teacher')
    subject_id = request.form.get('subject_id')
    section = request.form.get('section')
    date_str = request.form.get('date')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch records to delete for logging
        cursor.execute("""
            SELECT a.attendance_id, a.status 
            FROM Attendance a
            JOIN Sessions ses ON a.session_id = ses.session_id
            WHERE ses.uTID = %s AND ses.subject_id = %s AND ses.section = %s AND DATE(a.scan_time) = %s
        """, (uTID, subject_id, section, date_str))
        records_to_delete = cursor.fetchall()
        
        if records_to_delete:
            cursor.execute("""
                DELETE a FROM Attendance a
                JOIN Sessions ses ON a.session_id = ses.session_id
                WHERE ses.uTID = %s AND ses.subject_id = %s AND ses.section = %s AND DATE(a.scan_time) = %s
            """, (uTID, subject_id, section, date_str))
            
            for rec in records_to_delete:
                cursor.execute("""
                    INSERT INTO Attendance_Audit_Log (attendance_id, action, old_status, changed_by_user_id, changed_by_role)
                    VALUES (%s, 'Delete', %s, %s, %s)
                """, (rec['attendance_id'], rec['status'], uTID, role))
                
            conn.commit()
            flash(f'Attendance records for {date_str} successfully deleted.', 'success')
        else:
            flash(f'No attendance records found for {date_str}.', 'info')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting records: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('teacher.reports', subject_id=subject_id, section=section))

@teacher.route('/manage_marks')
def manage_marks():
    uTID = session['user_id']
    subject_id = request.args.get('subject_id', type=int)
    section = request.args.get('section')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch all assigned classes for the selector
    cursor.execute("""
        SELECT s.subject_id, s.subject_code, s.subject_name, ta.section 
        FROM Teacher_Assignments ta
        JOIN Subjects s ON ta.subject_id = s.subject_id
        WHERE ta.uTID = %s
    """, (uTID,))
    classes = cursor.fetchall()
    
    attendance_records = []
    selected_class = None
    
    # Initialize defaults for template
    total_pages = 1
    current_page = 1
    search = ''
    status_filter = ''
    
    if subject_id and section:
        # Find the specific class details
        for c in classes:
            if c['subject_id'] == subject_id and c['section'] == section:
                selected_class = c
                break
        
        if selected_class:
            if request.args.get('clear'):
                session.pop('marks_search', None)
                session.pop('marks_status', None)
                return redirect(url_for('teacher.manage_marks', subject_id=subject_id, section=section))

            current_page = request.args.get('page', 1, type=int)
            per_page = 20
            offset = (current_page - 1) * per_page
            
            # Persist search and filters in session
            search_param = request.args.get('search')
            if search_param is not None:
                session['marks_search'] = search_param.strip()
            search = session.get('marks_search', '')

            status_param = request.args.get('status_filter')
            if status_param is not None:
                session['marks_status'] = status_param.strip()
            status_filter = session.get('marks_status', '')
    
            

            # Subquery to get unique attendance IDs (latest scan per student per day)
            subquery = """
                SELECT MAX(a2.attendance_id) as max_id
                FROM Attendance a2
                JOIN Sessions ses2 ON a2.session_id = ses2.session_id
                WHERE ses2.uTID = %s AND ses2.subject_id = %s AND ses2.section = %s
                GROUP BY DATE(a2.scan_time), a2.uSID
            """
            
            # Base query
            query = f"""
            FROM Attendance a
            JOIN ({subquery}) max_a ON a.attendance_id = max_a.max_id
            JOIN Students s ON a.uSID = s.uSID
            JOIN Sessions ses ON a.session_id = ses.session_id
            JOIN Subjects sub ON ses.subject_id = sub.subject_id
            WHERE 1=1
            """
            params = [uTID, subject_id, section]

            if search:
                query += " AND (s.first_name LIKE %s OR s.last_name LIKE %s OR s.uSID LIKE %s)"
                search_val = f"%{search}%"
                params.extend([search_val, search_val, search_val])
            
            if status_filter:
                query += " AND a.status = %s"
                params.append(status_filter)

            # Count total
            cursor.execute("SELECT COUNT(*) as total " + query, params)
            total_count = cursor.fetchone()['total']
            total_pages = (total_count + per_page - 1) // per_page

            # Select data
            select_query = "SELECT a.attendance_id, s.first_name, s.middle_name, s.last_name, s.uSID, sub.subject_name, a.scan_time, a.status, a.is_valid, a.remarks, a.behavior_flags, a.distance_meters " + query
            select_query += " ORDER BY DATE(a.scan_time) DESC, s.last_name ASC, s.first_name ASC LIMIT %s OFFSET %s"
            params.extend([per_page, offset])

            cursor.execute(select_query, params)
            attendance_records = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('manage_marks.html', 
                           records=attendance_records, 
                           classes=classes, 
                           selected_class=selected_class,
                           total_pages=total_pages,
                           current_page=current_page,
                           search=search,
                           status_filter=status_filter)

@teacher.route('/update_mark', methods=['POST'])
def update_mark():
    """
    Manually overrides a student's attendance status (e.g. change Absent -> Present).
    Logs the update action including the previous and new status.
    """
    uTID = session['user_id']
    role = session.get('role', 'teacher')
    
    attendance_id = request.form.get('attendance_id')
    new_status = request.form.get('status')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT status FROM Attendance WHERE attendance_id = %s", (attendance_id,))
    record = cursor.fetchone()
    
    if record and record['status'] != new_status:
        old_status = record['status']
        cursor.execute("UPDATE Attendance SET status = %s WHERE attendance_id = %s", (new_status, attendance_id))
        
        cursor.execute("""
            INSERT INTO Attendance_Audit_Log (attendance_id, action, old_status, new_status, changed_by_user_id, changed_by_role)
            VALUES (%s, 'Update', %s, %s, %s, %s)
        """, (attendance_id, old_status, new_status, uTID, role))
        
        # Audit Logging
        log_system_action(cursor, 'Attendance', attendance_id, 'Update', uTID, role, f"Attendance status updated: {old_status} -> {new_status}")
        
        conn.commit()
        flash('Attendance mark updated successfully.', 'success')
    else:
        flash('No changes made to attendance.', 'info')
        
    cursor.close()
    conn.close()
    
    subject_id = request.form.get('subject_id')
    section = request.form.get('section')
    if subject_id and section:
        return redirect(url_for('teacher.manage_marks', subject_id=subject_id, section=section))
    return redirect(url_for('teacher.manage_marks'))

@teacher.route('/delete_mark', methods=['POST'])
def delete_mark():
    """
    Deletes a single attendance record.
    Logs the deletion in Attendance_Audit_Log.
    """
    uTID = session['user_id']
    role = session.get('role', 'teacher')
    
    attendance_id = request.form.get('attendance_id')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT status FROM Attendance WHERE attendance_id = %s", (attendance_id,))
        record = cursor.fetchone()
        
        if record:
            cursor.execute("DELETE FROM Attendance WHERE attendance_id = %s", (attendance_id,))
            
            cursor.execute("""
                INSERT INTO Attendance_Audit_Log (attendance_id, action, old_status, changed_by_user_id, changed_by_role)
                VALUES (%s, 'Delete', %s, %s, %s)
            """, (attendance_id, record['status'], uTID, role))
            
            # Audit Logging
            log_system_action(cursor, 'Attendance', attendance_id, 'Delete', uTID, role, f"Attendance record deleted. Old Status: {record['status']}")
            
            conn.commit()
            flash('Attendance record deleted successfully.', 'success')
        else:
            flash('Record not found.', 'error')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting record: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
        
    # We don't have the subject_id and section easily accessible here to redirect back to the exact class view
    # But wait, we can pass them in the form!
    subject_id = request.form.get('subject_id')
    section = request.form.get('section')
    
    if subject_id and section:
        return redirect(url_for('teacher.manage_marks', subject_id=subject_id, section=section))
    return redirect(url_for('teacher.manage_marks'))



# =========================================
# MANUAL ATTENDANCE — GET: Show student checklist for selected class
# =========================================
@teacher.route('/manual_attendance', methods=['GET'])
def manual_attendance():
    uTID = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all classes (subject + section) assigned to this teacher
    cursor.execute("""
        SELECT ta.assignment_id, ta.subject_id, ta.section,
               s.subject_code, s.subject_name
        FROM Teacher_Assignments ta
        JOIN Subjects s ON ta.subject_id = s.subject_id
        WHERE ta.uTID = %s
    """, (uTID,))
    classes = cursor.fetchall()

    # Read which class was selected from the URL query string
    selected_subject_id = request.args.get('subject_id', type=int)
    selected_section    = request.args.get('section', '')
    students            = []
    selected_class      = None
    already_recorded    = False

    if selected_subject_id and selected_section:
        # Find the label for the currently selected class
        for c in classes:
            if c['subject_id'] == selected_subject_id and c['section'] == selected_section:
                selected_class = c
                break

        # Fetch all ACTIVE students enrolled in this specific subject + section
        cursor.execute("""
            SELECT s.uSID, s.first_name, s.middle_name, s.last_name, s.email, s.level
            FROM Enrollments e
            JOIN Students s ON e.uSID = s.uSID
            WHERE e.subject_id = %s
              AND e.section    = %s
              AND s.status     = 'Active'
            ORDER BY s.last_name, s.first_name
        """, (selected_subject_id, selected_section))
        students = cursor.fetchall()

        # Check if attendance is already recorded for today for this class
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM Sessions 
            WHERE uTID = %s AND subject_id = %s AND section = %s 
              AND DATE(start_time) = CURDATE()
        """, (uTID, selected_subject_id, selected_section))
        already_recorded = cursor.fetchone()['count'] > 0

    cursor.close()
    conn.close()

    # Render the manual attendance checklist page
    return render_template(
        'manual_attendance.html',
        name=session.get('name'),
        classes=classes,
        students=students,
        selected_subject_id=selected_subject_id,
        selected_section=selected_section,
        selected_class=selected_class,
        already_recorded=already_recorded
    )


# =========================================
# MANUAL ATTENDANCE — POST: Save submitted checkbox attendance
# =========================================
@teacher.route('/submit_manual_attendance', methods=['POST'])
def submit_manual_attendance():
    """
    Saves manually recorded attendance by a teacher.
    Prevents duplicate submissions for the same day and sends notifications.
    """
    uTID        = session['user_id']
    subject_id  = request.form.get('subject_id', type=int)
    section     = request.form.get('section', '')

    # 'present_ids' = list of uSIDs whose checkbox was CHECKED (Present)
    present_ids = request.form.getlist('present_ids')
    # 'all_ids'     = hidden list of ALL student uSIDs shown on the form
    all_ids     = request.form.getlist('all_ids')

    now = datetime.now()

    # Build a unique session ID for this manual event
    # Format: MANUAL-{uTID}-{subject_id}-{section}-{timestamp}
    manual_session_id = f"MANUAL-{uTID}-{subject_id}-{section}-{now.strftime('%Y%m%d%H%M%S')}"

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Prevent duplication: check if attendance already exists for today
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM Sessions 
            WHERE uTID = %s AND subject_id = %s AND section = %s 
              AND DATE(start_time) = CURDATE()
        """, (uTID, subject_id, section))
        
        if cursor.fetchone()['count'] > 0:
            flash('Attendance for this class has already been recorded today. Please use Manage Marks to edit it.', 'warning')
            cursor.close()
            conn.close()
            return redirect(url_for('teacher.manage_marks', subject_id=subject_id, section=section))

        # STEP 1: Create a Session record for this manual attendance event.
        # lat/lon = 0 because this is not a QR / GPS session.
        # status = 'Ended' immediately since it is teacher-submitted.
        cursor.execute("""
            INSERT INTO Sessions
                (session_id, uTID, subject_id, section,
                 random_token, start_time, expires_at,
                 latitude, longitude, status)
            VALUES (%s, %s, %s, %s, 'MANUAL', %s, %s, 0, 0, 'Ended')
        """, (manual_session_id, uTID, subject_id, section, now, now))
        
        # Audit Logging
        log_system_action(cursor, 'Sessions', manual_session_id, 'Create', uTID, 'teacher', f"Manual session created for Subject {subject_id}, Section {section}")

        # STEP 2: Loop through ALL students and insert an attendance row.
        # Checked box  → Present  |  Unchecked → Absent
        for uSID in all_ids:
            status  = 'Present' if uSID in present_ids else 'Absent'
            remarks = 'Manual attendance by teacher'

            cursor.execute("""
                INSERT INTO Attendance
                    (session_id, uSID, scan_time, status, remarks, is_valid)
                VALUES (%s, %s, %s, %s, %s, 'Valid')
            """, (manual_session_id, uSID, now, status, remarks))

            # STEP 3: Insert a Notification so the student knows their status.
            if status == 'Present':
                msg   = f'You were marked Present by your teacher on {now.strftime("%Y-%m-%d %H:%M")}.'
                ntype = 'Info'
            else:
                msg   = f'You were marked Absent by your teacher on {now.strftime("%Y-%m-%d %H:%M")}.'
                ntype = 'Warning'

            cursor.execute("""
                INSERT INTO Notifications (uSID, message, type)
                VALUES (%s, %s, %s)
            """, (uSID, msg, ntype))

        conn.commit()

        # Build summary counts for the flash message
        total_present = len(present_ids)
        total_absent  = len(all_ids) - total_present
        flash(
            f'Attendance saved! \u2705 {total_present} Present \u00b7 \u274c {total_absent} Absent.',
            'success'
        )

    except Exception as e:
        conn.rollback()
        flash(f'Error saving attendance: {str(e)}', 'error')

    finally:
        cursor.close()
        conn.close()

    # Redirect back to the same class view so teacher can verify
    return redirect(url_for(
        'teacher.manual_attendance',
        subject_id=subject_id,
        section=section
    ))

@teacher.route('/view_excuses')
def view_excuses():
    uTID = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.args.get('clear'):
        session.pop('excuses_search', None)
        return redirect(url_for('teacher.view_excuses'))

    # Persist search in session
    search_param = request.args.get('search')
    if search_param is not None:
        session['excuses_search'] = search_param.strip()
    search = session.get('excuses_search', '')
    

    query = """
        SELECT el.*, s.subject_code, s.subject_name, st.first_name, st.middle_name, st.last_name
        FROM Excuse_Letters el
        JOIN Subjects s ON el.subject_id = s.subject_id
        JOIN Students st ON el.uSID = st.uSID
        WHERE el.uTID = %s
    """
    params = [uTID]
    
    if search:
        query += " AND (st.first_name LIKE %s OR st.last_name LIKE %s OR st.uSID LIKE %s OR s.subject_code LIKE %s OR s.subject_name LIKE %s)"
        search_val = f"%{search}%"
        params.extend([search_val, search_val, search_val, search_val, search_val])
        
    query += " ORDER BY el.created_at DESC"
    cursor.execute(query, params)
    letters = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('view_excuses.html', letters=letters, search=search, name=session.get('name'))

@teacher.route('/update_excuse_status', methods=['POST'])
def update_excuse_status():
    letter_id = request.form.get('letter_id')
    new_status = request.form.get('status')
    uTID = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Verify teacher owns this letter and get subject name
        cursor.execute("""
            SELECT el.*, s.subject_name, s.subject_code
            FROM Excuse_Letters el
            JOIN Subjects s ON el.subject_id = s.subject_id
            WHERE el.letter_id = %s AND el.uTID = %s
        """, (letter_id, uTID))
        letter = cursor.fetchone()
        
        if not letter:
            flash('Excuse letter not found or unauthorized.', 'error')
        else:
            cursor.execute("UPDATE Excuse_Letters SET status = %s WHERE letter_id = %s", (new_status, letter_id))
            
            # Audit Logging
            log_system_action(cursor, 'Excuse_Letters', letter_id, 'Update', uTID, 'teacher', f"Excuse letter status updated to {new_status}")
            
            # Notify student with proper subject name
            subject_label = f"{letter['subject_code']} - {letter['subject_name']}"
            msg = f"Your excuse letter for {subject_label} has been {new_status}."
            cursor.execute("INSERT INTO Notifications (uSID, message, type) VALUES (%s, %s, %s)", 
                           (letter['uSID'], msg, 'Info' if new_status == 'Approved' else 'Warning'))
            
            conn.commit()
            flash(f'Excuse letter {new_status.lower()} successfully.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error updating status: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('teacher.view_excuses'))

@teacher.route('/my_schedule')
def my_schedule():
    uTID = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
    SELECT s.subject_code, s.subject_name, sch.day_of_week, sch.start_time, sch.end_time, sch.room, sch.section
    FROM schedule sch
    JOIN Subjects s ON sch.subject_id = s.subject_id
    WHERE sch.uTID = %s
    ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'), start_time
    """
    cursor.execute(query, (uTID,))
    schedule_raw = cursor.fetchall()
    
    # Process schedule for grid
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_map = {day: i+2 for i, day in enumerate(days)} # Column index
    
    processed_schedule = []
    for item in schedule_raw:
        # Helper to convert time/timedelta to row index
        def get_row_index(t):
            # MySQL TIME columns return timedelta objects
            total_seconds = t.total_seconds() if hasattr(t, 'total_seconds') else (t.hour * 3600 + t.minute * 60)
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
    
    return render_template('teacher_schedule.html', 
                           schedule=processed_schedule, 
                           days=days, 
                           time_labels=time_labels,
                           name=session.get('name'))