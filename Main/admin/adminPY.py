from flask import Blueprint, render_template, request, session, redirect, url_for, flash
import json
from Main.db import get_db_connection
from werkzeug.security import generate_password_hash

admin = Blueprint('admin', __name__, template_folder='templates')

@admin.before_request
def require_login():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please login as admin first.', 'error')
        return redirect(url_for('auth.admin_login'))

@admin.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(*) as count FROM Students")
    student_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM Teachers")
    teacher_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM Subjects")
    subject_count = cursor.fetchone()['count']
    
    # Fetch submitted reports from teachers
    cursor.execute("""
        SELECT sr.report_id, sr.submission_date, sr.section, t.first_name, t.last_name as teacher_last, 
               sub.subject_code, sub.subject_name
        FROM Submitted_Reports sr
        JOIN Teachers t ON sr.uTID = t.uTID
        JOIN Subjects sub ON sr.subject_id = sub.subject_id
        ORDER BY sr.submission_date DESC
        LIMIT 10
    """)
    submitted_reports = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin_dashboard.html', 
                           student_count=student_count, 
                           teacher_count=teacher_count, 
                           subject_count=subject_count,
                           submitted_reports=submitted_reports)

@admin.route('/view_report/<int:report_id>')
def view_report(report_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT sr.*, t.first_name, t.last_name, s.subject_code, s.subject_name
        FROM Submitted_Reports sr
        JOIN Teachers t ON sr.uTID = t.uTID
        JOIN Subjects s ON sr.subject_id = s.subject_id
        WHERE sr.report_id = %s
    """, (report_id,))
    report = cursor.fetchone()
    
    if not report:
        flash('Report not found.', 'error')
        return redirect(url_for('admin.dashboard'))
        
    summary = json.loads(report['summary_json'])
    
    # Calculate aggregate stats for the Pie Chart from the JSON snapshot
    report_stats = {
        'Present': sum(row.get('days_present', 0) for row in summary),
        'Absent': sum(row.get('days_absent', 0) for row in summary),
        'Late': sum(row.get('days_late', 0) for row in summary)
    }
    
    cursor.close()
    conn.close()
    return render_template('admin_view_report.html', report=report, summary=summary, report_stats=report_stats)

@admin.route('/manage_students', methods=['GET', 'POST'])
def manage_students():
    from datetime import datetime
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        # Auto-generation logic for Student ID (S-YYYY-XXX)
        current_year = datetime.now().year
        prefix = f"S-{current_year}-"
        
        cursor.execute("SELECT uSID FROM Students WHERE uSID LIKE %s ORDER BY uSID DESC LIMIT 1", (prefix + '%',))
        last_student = cursor.fetchone()
        
        if last_student:
            last_id_num = int(last_student['uSID'].split('-')[2])
            new_id_num = last_id_num + 1
        else:
            new_id_num = 1
            
        new_uSID = f"{prefix}{new_id_num:03d}"
        
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        course = request.form.get('course')
        level = request.form.get('level')
        section = request.form.get('section')
        
        # Default password is the ID without the 'S-' prefix (e.g. 2026-001)
        default_password = f"{current_year}-{new_id_num:03d}"
        password_hash = generate_password_hash(default_password)
        
        cursor.execute("""
            INSERT INTO Students (uSID, first_name, last_name, email, course, level, section, password_hash) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (new_uSID, first_name, last_name, email, course, level, section, password_hash))
        conn.commit()
        flash(f'Student added successfully with ID: {new_uSID}', 'success')
        return redirect(url_for('admin.manage_students'))

    cursor.execute("SELECT * FROM Students")
    students = cursor.fetchall()

    # Fetch subjects with their assigned teachers (grouped) and enrollment counts
    cursor.execute("""
        SELECT s.*, 
               GROUP_CONCAT(CONCAT(t.first_name, ' ', t.last_name) SEPARATOR ', ') as teachers,
               (SELECT COUNT(*) FROM Enrollments e WHERE e.subject_id = s.subject_id) as student_count
        FROM Subjects s
        LEFT JOIN Teacher_Assignments ta ON s.subject_id = ta.subject_id
        LEFT JOIN Teachers t ON ta.uTID = t.uTID
        GROUP BY s.subject_id
    """)
    subjects = cursor.fetchall()

    # Fetch students grouped by subjects
    cursor.execute("""
        SELECT s.*, sub.subject_name, sub.subject_code, e.subject_id, e.enrollment_id
        FROM Students s
        JOIN Enrollments e ON s.uSID = e.uSID
        JOIN Subjects sub ON e.subject_id = sub.subject_id
    """)
    enrolled_students = cursor.fetchall()

    # Fetch assignments for enrollment modal
    cursor.execute("""
        SELECT ta.assignment_id, s.subject_code, s.subject_name, ta.section, t.first_name, t.last_name
        FROM Teacher_Assignments ta
        JOIN Subjects s ON ta.subject_id = s.subject_id
        JOIN Teachers t ON ta.uTID = t.uTID
    """)
    all_assignments = cursor.fetchall()

    cursor.execute("SELECT DISTINCT course FROM Students WHERE course IS NOT NULL AND status = 'Active'")
    courses = [row['course'] for row in cursor.fetchall()]

    cursor.close()
    conn.close()
    return render_template('admin_manage_students.html', 
                           students=students, 
                           subjects=subjects, 
                           enrolled_students=enrolled_students,
                           all_assignments=all_assignments,
                           courses=courses)

@admin.route('/edit_student/<uSID>', methods=['POST'])
def edit_student(uSID):
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    course = request.form.get('course')
    level = request.form.get('level')
    section = request.form.get('section')
    status = request.form.get('status')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE Students 
            SET first_name = %s, last_name = %s, email = %s, course = %s, level = %s, section = %s, status = %s
            WHERE uSID = %s
        """, (first_name, last_name, email, course, level, section, status, uSID))
        conn.commit()
        flash('Student updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating student: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin.manage_students'))

@admin.route('/manage_teachers', methods=['GET', 'POST'])
def manage_teachers():
    from datetime import datetime
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        # Auto-generation logic for Teacher ID (T-YYYY-XXX)
        current_year = datetime.now().year
        prefix = f"T-{current_year}-"
        
        cursor.execute("SELECT uTID FROM Teachers WHERE uTID LIKE %s ORDER BY uTID DESC LIMIT 1", (prefix + '%',))
        last_teacher = cursor.fetchone()
        
        if last_teacher:
            last_id_num = int(last_teacher['uTID'].split('-')[2])
            new_id_num = last_id_num + 1
        else:
            new_id_num = 1
            
        new_uTID = f"{prefix}{new_id_num:03d}"
        
        first_name = request.form.get('first_name')
        middle_name = request.form.get('middle_name')
        last_name = request.form.get('last_name')
        department = request.form.get('department')
        email = request.form.get('email')
        
        # Default password is the ID without the 'T-' prefix (e.g. 2026-001)
        default_password = f"{current_year}-{new_id_num:03d}"
        password_hash = generate_password_hash(default_password)
        
        cursor.execute("""
            INSERT INTO Teachers (uTID, first_name, middle_name, last_name, department, email, password_hash) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (new_uTID, first_name, middle_name, last_name, department, email, password_hash))
        conn.commit()
        flash(f'Teacher added successfully with ID: {new_uTID}', 'success')
        return redirect(url_for('admin.manage_teachers'))

    cursor.execute("SELECT * FROM Teachers")
    teachers = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_manage_teachers.html', teachers=teachers)

@admin.route('/edit_teacher/<uTID>', methods=['POST'])
def edit_teacher(uTID):
    first_name = request.form.get('first_name')
    middle_name = request.form.get('middle_name')
    last_name = request.form.get('last_name')
    department = request.form.get('department')
    email = request.form.get('email')
    status = request.form.get('status')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE Teachers 
            SET first_name = %s, middle_name = %s, last_name = %s, department = %s, email = %s, status = %s
            WHERE uTID = %s
        """, (first_name, middle_name, last_name, department, email, status, uTID))
        conn.commit()
        flash('Teacher updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating teacher: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin.manage_teachers'))

@admin.route('/manage_subjects', methods=['GET', 'POST'])
def manage_subjects():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        subject_code = request.form.get('subject_code')
        subject_name = request.form.get('subject_name')
        
        cursor.execute("INSERT INTO Subjects (subject_code, subject_name) VALUES (%s, %s)", (subject_code, subject_name))
        conn.commit()
        flash('Subject added successfully.', 'success')
        return redirect(url_for('admin.manage_subjects'))
        
    cursor.execute("SELECT * FROM Subjects")
    subjects = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_manage_subjects.html', subjects=subjects)

@admin.route('/edit_subject/<int:subject_id>', methods=['POST'])
def edit_subject(subject_id):
    subject_code = request.form.get('subject_code')
    subject_name = request.form.get('subject_name')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Subjects SET subject_code = %s, subject_name = %s WHERE subject_id = %s", 
                   (subject_code, subject_name, subject_id))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Subject updated successfully.', 'success')
    return redirect(url_for('admin.manage_subjects'))

@admin.route('/delete_subject/<int:subject_id>')
def delete_subject(subject_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Subjects WHERE subject_id = %s", (subject_id,))
        conn.commit()
        flash('Subject deleted successfully.', 'success')
    except Exception as e:
        flash('Cannot delete subject. It might have active enrollments or assignments.', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin.manage_subjects'))


@admin.route('/assign_classes', methods=['GET', 'POST'])
def assign_classes():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        uTID = request.form.get('uTID')
        subject_id = request.form.get('subject_id')
        section = request.form.get('section')
        
        cursor.execute("INSERT INTO Teacher_Assignments (uTID, subject_id, section) VALUES (%s, %s, %s)", (uTID, subject_id, section))
        conn.commit()
        flash('Class successfully assigned to teacher.', 'success')
        return redirect(url_for('admin.assign_classes'))

    cursor.execute("SELECT * FROM Teachers WHERE status = 'Active'")
    teachers = cursor.fetchall()
    
    cursor.execute("SELECT * FROM Subjects")
    subjects = cursor.fetchall()
    
    cursor.execute("""
        SELECT ta.assignment_id, t.first_name, t.last_name, s.subject_code, s.subject_name, ta.section
        FROM Teacher_Assignments ta
        JOIN Teachers t ON ta.uTID = t.uTID
        JOIN Subjects s ON ta.subject_id = s.subject_id
    """)
    assignments = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin_assign_classes.html', teachers=teachers, subjects=subjects, assignments=assignments)

@admin.route('/enroll_student', methods=['POST'])
def enroll_student():
    uSID = request.form.get('uSID')
    assignment_id = request.form.get('assignment_id') # Selected from Teacher_Assignments
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get assignment details
        cursor.execute("SELECT * FROM Teacher_Assignments WHERE assignment_id = %s", (assignment_id,))
        assignment = cursor.fetchone()
        
        if not assignment:
            flash('Selected class assignment not found.', 'error')
            return redirect(url_for('admin.manage_students'))
            
        # Check if already enrolled
        cursor.execute("SELECT * FROM Enrollments WHERE uSID = %s AND subject_id = %s AND section = %s", 
                       (uSID, assignment['subject_id'], assignment['section']))
        if cursor.fetchone():
            flash('Student is already enrolled in this subject and section.', 'warning')
        else:
            cursor.execute("INSERT INTO Enrollments (uSID, subject_id, section) VALUES (%s, %s, %s)", 
                           (uSID, assignment['subject_id'], assignment['section']))
            conn.commit()
            flash('Student successfully enrolled in the subject.', 'success')
            
    except Exception as e:
        flash(f'Error enrolling student: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin.manage_students'))

@admin.route('/manage_schedules', methods=['GET', 'POST'])
def manage_schedules():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        assignment_id = request.form.get('assignment_id')
        day = request.form.get('day_of_week')
        start = request.form.get('start_time')
        end = request.form.get('end_time')
        room = request.form.get('room')
        
        # Get details from Teacher_Assignments
        cursor.execute("SELECT * FROM Teacher_Assignments WHERE assignment_id = %s", (assignment_id,))
        ta = cursor.fetchone()
        
        if ta:
            # Conflict Check: Does this teacher or room already have a class at this time?
            # A conflict exists if: (ExistingStart < NewEnd) AND (ExistingEnd > NewStart)
            conflict_query = """
                SELECT sch.*, s.subject_code 
                FROM schedule sch
                JOIN Subjects s ON sch.subject_id = s.subject_id
                WHERE sch.day_of_week = %s 
                AND (%s < sch.end_time AND %s > sch.start_time)
                AND (sch.uTID = %s OR sch.room = %s)
            """
            cursor.execute(conflict_query, (day, start, end, ta['uTID'], room))
            conflict = cursor.fetchone()
            
            if conflict:
                conflict_type = "Teacher" if conflict['uTID'] == ta['uTID'] else "Room"
                flash(f"Conflict Detected! {conflict_type} is already busy with {conflict['subject_code']} at this time.", "error")
            else:
                cursor.execute("""
                    INSERT INTO schedule (subject_id, uTID, section, day_of_week, start_time, end_time, room)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (ta['subject_id'], ta['uTID'], ta['section'], day, start, end, room))
                conn.commit()
                flash('Schedule added successfully.', 'success')
        
    cursor.execute("""
        SELECT ta.assignment_id, t.first_name, t.last_name, s.subject_code, s.subject_name, ta.section
        FROM Teacher_Assignments ta
        JOIN Teachers t ON ta.uTID = t.uTID
        JOIN Subjects s ON ta.subject_id = s.subject_id
    """)
    assignments = cursor.fetchall()
    
    cursor.execute("""
        SELECT sch.*, s.subject_code, s.subject_name, t.first_name, t.last_name
        FROM schedule sch
        JOIN Subjects s ON sch.subject_id = s.subject_id
        JOIN Teachers t ON sch.uTID = t.uTID
    """)
    schedules = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin_manage_schedules.html', assignments=assignments, schedules=schedules)

@admin.route('/remove_schedule/<int:schedule_id>')
def remove_schedule(schedule_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM schedule WHERE schedule_id = %s", (schedule_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Schedule removed successfully.', 'success')
    return redirect(url_for('admin.manage_schedules'))

@admin.route('/remove_enrollment/<int:enrollment_id>')
def remove_enrollment(enrollment_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Enrollments WHERE enrollment_id = %s", (enrollment_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Enrollment removed successfully.', 'success')
    return redirect(url_for('admin.manage_students'))

@admin.route('/archive_student/<uSID>')
def archive_student(uSID):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Students SET status = 'Archived' WHERE uSID = %s", (uSID,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Student archived successfully.', 'success')
    return redirect(url_for('admin.manage_students'))

@admin.route('/unarchive_student/<uSID>')
def unarchive_student(uSID):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Students SET status = 'Active' WHERE uSID = %s", (uSID,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Student unarchived successfully.', 'success')
    return redirect(url_for('admin.manage_students'))

@admin.route('/archive_teacher/<uTID>')
def archive_teacher(uTID):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Teachers SET status = 'Archived' WHERE uTID = %s", (uTID,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Teacher archived successfully.', 'success')
    return redirect(url_for('admin.manage_teachers'))

@admin.route('/unarchive_teacher/<uTID>')
def unarchive_teacher(uTID):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Teachers SET status = 'Active' WHERE uTID = %s", (uTID,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Teacher unarchived successfully.', 'success')
    return redirect(url_for('admin.manage_teachers'))

@admin.route('/remove_assignment/<int:assignment_id>')
def remove_assignment(assignment_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM Teacher_Assignments WHERE assignment_id = %s", (assignment_id,))
        conn.commit()
        flash('Assignment removed successfully.', 'success')
    except Exception as e:
        flash(f'Error removing assignment: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin.assign_classes'))

@admin.route('/drop_requests')
def drop_requests():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT dr.*, s.first_name as s_first, s.last_name as s_last, 
               sub.subject_code, sub.subject_name,
               t.first_name as t_first, t.last_name as t_last
        FROM Drop_Requests dr
        JOIN Students s ON dr.uSID = s.uSID
        JOIN Subjects sub ON dr.subject_id = sub.subject_id
        JOIN Teachers t ON dr.uTID = t.uTID
        WHERE dr.status = 'Pending'
        ORDER BY dr.created_at DESC
    """
    cursor.execute(query)
    requests = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin_drop_requests.html', requests=requests)

@admin.route('/approve_drop/<int:request_id>')
def approve_drop(request_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM Drop_Requests WHERE request_id = %s", (request_id,))
    req = cursor.fetchone()
    
    if req:
        cursor.execute("UPDATE Drop_Requests SET status = 'Approved' WHERE request_id = %s", (request_id,))
        cursor.execute("UPDATE Students SET status = 'Archived' WHERE uSID = %s", (req['uSID'],))
        conn.commit()
        flash('Drop request approved and student archived.', 'success')
    
    cursor.close()
    conn.close()
    return redirect(url_for('admin.drop_requests'))

@admin.route('/reject_drop/<int:request_id>')
def reject_drop(request_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Drop_Requests SET status = 'Rejected' WHERE request_id = %s", (request_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Drop request rejected.', 'info')
    return redirect(url_for('admin.drop_requests'))

@admin.route('/bulk_enroll', methods=['POST'])
def bulk_enroll():
    assignment_id = request.form.get('assignment_id')
    try:
        count = int(request.form.get('count', 0))
    except ValueError:
        count = 0
    course_filter = request.form.get('course_filter')
    
    if count <= 0:
        flash('Please enter a valid number of students.', 'error')
        return redirect(url_for('admin.manage_students'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get assignment details
        cursor.execute("SELECT * FROM Teacher_Assignments WHERE assignment_id = %s", (assignment_id,))
        assignment = cursor.fetchone()
        
        if not assignment:
            flash('Selected class assignment not found.', 'error')
            return redirect(url_for('admin.manage_students'))
            
        # Get students who are NOT enrolled in THIS subject (regardless of section)
        # to avoid double enrollment in the same course.
        query = """
            SELECT uSID FROM Students 
            WHERE status = 'Active'
            AND uSID NOT IN (SELECT uSID FROM Enrollments WHERE subject_id = %s)
        """
        params = [assignment['subject_id']]
        
        if course_filter:
            query += " AND course = %s"
            params.append(course_filter)
            
        query += " ORDER BY RAND() LIMIT %s"
        params.append(count)
        
        cursor.execute(query, tuple(params))
        students_to_enroll = cursor.fetchall()
        
        if not students_to_enroll:
            flash('No eligible students found for bulk enrollment matching your criteria.', 'warning')
        else:
            enroll_query = "INSERT INTO Enrollments (uSID, subject_id, section) VALUES (%s, %s, %s)"
            enroll_data = [(s['uSID'], assignment['subject_id'], assignment['section']) for s in students_to_enroll]
            
            cursor.executemany(enroll_query, enroll_data)
            conn.commit()
            flash(f'Successfully enrolled {len(students_to_enroll)} students into {assignment["section"]}.', 'success')
            
    except Exception as e:
        flash(f'Error in bulk enrollment: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin.manage_students'))