from flask import Blueprint, render_template, request, session, redirect, url_for, flash
import json
from Main.db import get_db_connection, log_system_action
from psycopg2.extras import RealDictCursor
import re

def validate_user_data(first_name, middle_name, last_name, email):
    """
    Validates user data for empty fields, trim spaces, name length, and character restrictions.
    Returns: (is_valid, error_message, (trimmed_first, trimmed_middle, trimmed_last, trimmed_email))
    """
    first_name = (first_name or '').strip()
    middle_name = (middle_name or '').strip()
    last_name = (last_name or '').strip()
    email = (email or '').strip()
    
    if not first_name or not middle_name or not last_name or not email:
        return False, "All fields (first name, middle name, last name, email) are required.", None
        
    # Email Format Validation
    email_pattern = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    if not email_pattern.match(email):
        return False, "Invalid email format.", None
        
    name_pattern = re.compile(r"^[A-Za-z\s\-\.']+$")
    if not name_pattern.match(first_name) or not name_pattern.match(middle_name) or not name_pattern.match(last_name):
        return False, "Names can only contain letters, spaces, hyphens, periods, and apostrophes.", None
        
    if not (2 <= len(first_name) <= 100) or not (2 <= len(middle_name) <= 100) or not (2 <= len(last_name) <= 100):
        return False, "Names must be between 2 and 100 characters long.", None
        
    return True, "", (first_name, middle_name, last_name, email)


admin = Blueprint('admin', __name__, template_folder='templates')

@admin.before_request
def require_login():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please login as admin first.', 'error')
        return redirect(url_for('auth.admin_login'))

@admin.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("SELECT COUNT(*) as count FROM Students")
    student_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM Teachers")
    teacher_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM Subjects")
    subject_count = cursor.fetchone()['count']
    
    # Fetch submitted reports from teachers
    cursor.execute("""
        SELECT sr.report_id, sr.submission_date, sr.section, t.first_name, t.middle_name as teacher_middle, t.last_name as teacher_last, 
               sub.subject_code, sub.subject_name
        FROM Submitted_Reports sr
        JOIN Teachers t ON sr.uTID = t.uTID
        JOIN Subjects sub ON sr.subject_id = sub.subject_id
        ORDER BY sr.submission_date DESC
        LIMIT 10
    """)
    submitted_reports = cursor.fetchall()
    
    # New metrics for a better dashboard
    cursor.execute("SELECT COUNT(*) as count FROM Drop_Requests WHERE status = 'Pending'")
    pending_drops = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM Teacher_Assignments")
    total_classes = cursor.fetchone()['count']
    
    cursor.execute("""
        SELECT log_id, timestamp, performed_by_id, action, table_name, details 
        FROM System_Audit_Log 
        ORDER BY timestamp DESC 
        LIMIT 5
    """)
    recent_logs = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin_dashboard.html', 
                           student_count=student_count, 
                           teacher_count=teacher_count, 
                           subject_count=subject_count,
                           submitted_reports=submitted_reports,
                           pending_drops=pending_drops,
                           total_classes=total_classes,
                           recent_logs=recent_logs)
    

@admin.route('/view_report/<int:report_id>')
def view_report(report_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT sr.*, t.first_name, t.middle_name, t.last_name, s.subject_code, s.subject_name
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
    """
    Handles creating new students and viewing the list of students.
    Validates required fields, name format, and email uniqueness before insertion.
    """
    from datetime import datetime
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        # Auto-generation logic for Student ID (S-YYYY-XXX)
        current_year = datetime.now().year
        prefix = f"S-{current_year}-"
        
        cursor.execute("SELECT uSID FROM Students WHERE uSID LIKE %s ORDER BY uSID DESC LIMIT 1", (prefix + '%',))
        last_student = cursor.fetchone()
        
        if last_student:
            last_id_num = int(last_student['usid'].split('-')[2])
            new_id_num = last_id_num + 1
        else:
            new_id_num = 1
            
        new_uSID = f"{prefix}{new_id_num:03d}"
        
        # Check if Student ID already exists
        cursor.execute("SELECT uSID FROM Students WHERE uSID = %s", (new_uSID,))
        if cursor.fetchone():
            flash('Student ID already exists', 'error')
            return redirect(url_for('admin.manage_students'))
            
        first_name = request.form.get('first_name')
        middle_name = request.form.get('middle_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        course = request.form.get('course')
        level = request.form.get('level')
        section = request.form.get('section')
        
        is_valid, error_msg, validated_data = validate_user_data(first_name, middle_name, last_name, email)
        if not is_valid:
            flash(error_msg, 'error')
            return redirect(url_for('admin.manage_students'))
            
        first_name, middle_name, last_name, email = validated_data
        
        # Check duplicate email in Students and Teachers
        cursor.execute("SELECT email FROM Students WHERE email = %s UNION SELECT email FROM Teachers WHERE email = %s", (email, email))
        if cursor.fetchone():
            flash('Email already exists. Please use a different email.', 'error')
            return redirect(url_for('admin.manage_students'))
        
        # Default password is the ID without the 'S-' prefix (e.g. 2026-001)
        default_password = f"{current_year}-{new_id_num:03d}"
        password_hash = generate_password_hash(default_password)
        
        cursor.execute("""
            INSERT INTO Students (uSID, first_name, middle_name, last_name, email, course, level, section, password_hash) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (new_uSID, first_name, middle_name, last_name, email, course, level, section, password_hash))
        
        # Audit Logging
        log_system_action(cursor, 'Students', new_uSID, 'Create', session['user_id'], session['role'], f"Student created: {first_name} {last_name}")
        
        conn.commit()
        flash(f'Student added successfully with ID: {new_uSID}', 'success')
        return redirect(url_for('admin.manage_students'))

    # Pagination, Search and Filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    
    if request.args.get('clear'):
        session.pop('students_search', None)
        session.pop('students_course', None)
        session.pop('students_status', None)
        return redirect(url_for('admin.manage_students'))

    # Persist search and filters in session
    search_param = request.args.get('search')
    if search_param is not None:
        session['students_search'] = search_param.strip()
    search = session.get('students_search', '')

    course_param = request.args.get('course_filter')
    if course_param is not None:
        session['students_course'] = course_param.strip()
    course_filter = session.get('students_course', '')

    status_param = request.args.get('status_filter')
    if status_param is not None:
        session['students_status'] = status_param.strip()
    status_filter = session.get('students_status', 'All')
    
    # Base query for students
    
    query = "SELECT * FROM Students WHERE 1=1"
    count_query = "SELECT COUNT(*) as total FROM Students WHERE 1=1"
    params = []
    
    if search:
        search_clause = " AND (uSID LIKE %s OR first_name LIKE %s OR middle_name LIKE %s OR last_name LIKE %s OR email LIKE %s)"
        query += search_clause
        count_query += search_clause
        search_val = f"%{search}%"
        params.extend([search_val, search_val, search_val, search_val, search_val])
        
    if course_filter:
        query += " AND course = %s"
        count_query += " AND course = %s"
        params.append(course_filter)
        
    if status_filter and status_filter != 'All':
        query += " AND status = %s"
        count_query += " AND status = %s"
        params.append(status_filter)
        
    # Get total count for pagination
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()['total']
    total_pages = (total_count + per_page - 1) // per_page
    
    # Final paginated query
    query += " ORDER BY uSID DESC LIMIT %s OFFSET %s"
    query_params = params + [per_page, offset]
    
    cursor.execute(query, query_params)
    students = cursor.fetchall()

    # Fetch subjects with their assigned teachers (grouped) and enrollment counts (respecting search/filters)
    subject_count_subquery = """
        SELECT COUNT(*) FROM Enrollments e 
        JOIN Students st ON e.uSID = st.uSID 
        WHERE e.subject_id = s.subject_id
    """
    subject_count_params = []
    if search:
        subject_count_subquery += " AND (st.uSID LIKE %s OR st.first_name LIKE %s OR st.middle_name LIKE %s OR st.last_name LIKE %s OR st.email LIKE %s)"
        subject_count_params.extend([search_val, search_val, search_val, search_val, search_val])
    if course_filter:
        subject_count_subquery += " AND st.course = %s"
        subject_count_params.append(course_filter)
    if status_filter and status_filter != 'All':
        subject_count_subquery += " AND st.status = %s"
        subject_count_params.append(status_filter)

    cursor.execute(f"""
        SELECT s.*, 
               STRING_AGG(CONCAT(t.first_name, ' ', t.middle_name, ' ', t.last_name), ', ') as teachers,
               ({subject_count_subquery}) as student_count
        FROM Subjects s
        LEFT JOIN Teacher_Assignments ta ON s.subject_id = ta.subject_id
        LEFT JOIN Teachers t ON ta.uTID = t.uTID
        GROUP BY s.subject_id, s.subject_code, s.subject_name
    """, tuple(subject_count_params))
    subjects = cursor.fetchall()

    # Fetch students grouped by subjects (respecting search/filters)
    enrolled_query = """
        SELECT s.*, sub.subject_name, sub.subject_code, e.subject_id, e.enrollment_id
        FROM Students s
        JOIN Enrollments e ON s.uSID = e.uSID
        JOIN Subjects sub ON e.subject_id = sub.subject_id
        WHERE 1=1
    """
    enrolled_params = []
    if search:
        enrolled_query += " AND (s.uSID LIKE %s OR s.first_name LIKE %s OR s.middle_name LIKE %s OR s.last_name LIKE %s OR s.email LIKE %s)"
        enrolled_params.extend([search_val, search_val, search_val, search_val, search_val])
    if course_filter:
        enrolled_query += " AND s.course = %s"
        enrolled_params.append(course_filter)
    if status_filter and status_filter != 'All':
        enrolled_query += " AND s.status = %s"
        enrolled_params.append(status_filter)

    cursor.execute(enrolled_query, enrolled_params)
    enrolled_students = cursor.fetchall()
    

    # Fetch assignments for enrollment modal
    cursor.execute("""
        SELECT ta.assignment_id, s.subject_code, s.subject_name, ta.section, t.first_name, t.middle_name, t.last_name
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
                           courses=courses,
                           total_pages=total_pages,
                           current_page=page,
                           search=search,
                           course_filter=course_filter,
                           status_filter=status_filter)

@admin.route('/edit_student/<uSID>', methods=['POST'])
def edit_student(uSID):
    """
    Handles updating an existing student's details.
    Validates required fields, name format, and prevents email duplication.
    """
    first_name = request.form.get('first_name')
    middle_name = request.form.get('middle_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    course = request.form.get('course')
    level = request.form.get('level')
    section = request.form.get('section')
    status = request.form.get('status')

    is_valid, error_msg, validated_data = validate_user_data(first_name, middle_name, last_name, email)
    if not is_valid:
        flash(error_msg, 'error')
        return redirect(url_for('admin.manage_students'))
        
    first_name, middle_name, last_name, email = validated_data

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check duplicate email in Students and Teachers
    cursor.execute("SELECT email FROM Students WHERE email = %s AND uSID != %s UNION SELECT email FROM Teachers WHERE email = %s", (email, uSID, email))
    if cursor.fetchone():
        flash('Email already exists. Please use a different email.', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('admin.manage_students'))
    
    try:
        cursor.execute("""
            UPDATE Students 
            SET first_name = %s, middle_name = %s, last_name = %s, email = %s, course = %s, level = %s, section = %s, status = %s
            WHERE uSID = %s
        """, (first_name, middle_name, last_name, email, course, level, section, status, uSID))
        
        # Audit Logging
        log_system_action(cursor, 'Students', uSID, 'Update', session['user_id'], session['role'], f"Student updated: {first_name} {last_name}, Status: {status}")
        
        conn.commit()
        flash('Student updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating student: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin.manage_students'))
    
@admin.route('/delete_student/<uSID>')
def delete_student(uSID):
    """
    Deletes a student record only if they have no attendance history.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Check for attendance records
        cursor.execute("SELECT COUNT(*) as count FROM Attendance WHERE uSID = %s", (uSID,))
        if cursor.fetchone()['count'] > 0:
            flash('Cannot delete: student has attendance records', 'error')
            return redirect(url_for('admin.manage_students'))
            
        cursor.execute("DELETE FROM Students WHERE uSID = %s", (uSID,))
        
        # Audit Logging
        log_system_action(cursor, 'Students', uSID, 'Delete', session['user_id'], session['role'], f"Student deleted (ID: {uSID})")
        
        conn.commit()
        flash('Student deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting student: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin.manage_students'))

@admin.route('/manage_teachers', methods=['GET', 'POST'])
def manage_teachers():
    """
    Handles creating new teachers and viewing the list of teachers.
    Validates required fields, name format, and email uniqueness before insertion.
    """
    from datetime import datetime
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        # Auto-generation logic for Teacher ID (T-YYYY-XXX)
        current_year = datetime.now().year
        prefix = f"T-{current_year}-"
        
        cursor.execute("SELECT uTID FROM Teachers WHERE uTID LIKE %s ORDER BY uTID DESC LIMIT 1", (prefix + '%',))
        last_teacher = cursor.fetchone()
        
        if last_teacher:
            last_id_num = int(last_teacher['utid'].split('-')[2])
            new_id_num = last_id_num + 1
        else:
            new_id_num = 1
            
        new_uTID = f"{prefix}{new_id_num:03d}"
        
        first_name = request.form.get('first_name')
        middle_name = request.form.get('middle_name')
        last_name = request.form.get('last_name')
        department = request.form.get('department')
        email = request.form.get('email')
        
        is_valid, error_msg, validated_data = validate_user_data(first_name, middle_name, last_name, email)
        if not is_valid:
            flash(error_msg, 'error')
            return redirect(url_for('admin.manage_teachers'))
            
        first_name, middle_name, last_name, email = validated_data
        
        # Check duplicate email
        cursor.execute("SELECT email FROM Students WHERE email = %s UNION SELECT email FROM Teachers WHERE email = %s", (email, email))
        if cursor.fetchone():
            flash('Email already exists. Please use a different email.', 'error')
            return redirect(url_for('admin.manage_teachers'))
        
        # Default password is the ID without the 'T-' prefix (e.g. 2026-001)
        default_password = f"{current_year}-{new_id_num:03d}"
        password_hash = generate_password_hash(default_password)
        
        cursor.execute("""
            INSERT INTO Teachers (uTID, first_name, middle_name, last_name, department, email, password_hash) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (new_uTID, first_name, middle_name, last_name, department, email, password_hash))
        
        # Audit Logging
        log_system_action(cursor, 'Teachers', new_uTID, 'Create', session['user_id'], session['role'], f"Teacher created: {first_name} {last_name}")
        
        conn.commit()
        flash(f'Teacher added successfully with ID: {new_uTID}', 'success')
        return redirect(url_for('admin.manage_teachers'))

    # Pagination, Search and Filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    
    # Persist search and filters in session
    if request.args.get('clear'):
        session.pop('teachers_search', None)
        session.pop('teachers_dept', None)
        session.pop('teachers_status', None)
        return redirect(url_for('admin.manage_teachers'))

    search_param = request.args.get('search')
    if search_param is not None:
        session['teachers_search'] = search_param.strip()
    search = session.get('teachers_search', '')

    dept_param = request.args.get('dept_filter')
    if dept_param is not None:
        session['teachers_dept'] = dept_param.strip()
    dept_filter = session.get('teachers_dept', '')

    status_param = request.args.get('status_filter')
    if status_param is not None:
        session['teachers_status'] = status_param.strip()
    status_filter = session.get('teachers_status', 'All')
    
    # Base query for teachers
    
    query = "SELECT * FROM Teachers WHERE 1=1"
    count_query = "SELECT COUNT(*) as total FROM Teachers WHERE 1=1"
    params = []
    
    if search:
        search_clause = " AND (uTID LIKE %s OR first_name LIKE %s OR middle_name LIKE %s OR last_name LIKE %s OR email LIKE %s)"
        query += search_clause
        count_query += search_clause
        search_val = f"%{search}%"
        params.extend([search_val, search_val, search_val, search_val, search_val])
        
    if dept_filter:
        query += " AND department = %s"
        count_query += " AND department = %s"
        params.append(dept_filter)
        
    if status_filter and status_filter != 'All':
        query += " AND status = %s"
        count_query += " AND status = %s"
        params.append(status_filter)
        
    # Get total count for pagination
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()['total']
    total_pages = (total_count + per_page - 1) // per_page
    
    # Final paginated query
    query += " ORDER BY uTID DESC LIMIT %s OFFSET %s"
    query_params = params + [per_page, offset]
    
    cursor.execute(query, query_params)
    teachers = cursor.fetchall()
    
    # Fetch unique departments for filter
    cursor.execute("SELECT DISTINCT department FROM Teachers WHERE department IS NOT NULL AND department != ''")
    departments = [row['department'] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return render_template('admin_manage_teachers.html', 
                           teachers=teachers,
                           total_pages=total_pages,
                           current_page=page,
                           search=search,
                           dept_filter=dept_filter,
                           status_filter=status_filter,
                           departments=departments)

@admin.route('/edit_teacher/<uTID>', methods=['POST'])
def edit_teacher(uTID):
    """
    Handles updating an existing teacher's details.
    Validates required fields, name format, and prevents email duplication.
    """
    first_name = request.form.get('first_name')
    middle_name = request.form.get('middle_name')
    last_name = request.form.get('last_name')
    department = request.form.get('department')
    email = request.form.get('email')
    status = request.form.get('status')

    is_valid, error_msg, validated_data = validate_user_data(first_name, middle_name, last_name, email)
    if not is_valid:
        flash(error_msg, 'error')
        return redirect(url_for('admin.manage_teachers'))
        
    first_name, middle_name, last_name, email = validated_data

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check duplicate email
    cursor.execute("SELECT email FROM Teachers WHERE email = %s AND uTID != %s UNION SELECT email FROM Students WHERE email = %s", (email, uTID, email))
    if cursor.fetchone():
        flash('Email already exists. Please use a different email.', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('admin.manage_teachers'))
    
    try:
        cursor.execute("""
            UPDATE Teachers 
            SET first_name = %s, middle_name = %s, last_name = %s, department = %s, email = %s, status = %s
            WHERE uTID = %s
        """, (first_name, middle_name, last_name, department, email, status, uTID))
        
        # Audit Logging
        log_system_action(cursor, 'Teachers', uTID, 'Update', session['user_id'], session['role'], f"Teacher updated: {first_name} {last_name}, Status: {status}")
        
        conn.commit()
        flash('Teacher updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating teacher: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin.manage_teachers'))

@admin.route('/delete_teacher/<uTID>')
def delete_teacher(uTID):
    """
    Deletes a teacher record only if they have no active assignments.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Check for assignments or sessions
        cursor.execute("SELECT COUNT(*) as count FROM Teacher_Assignments WHERE uTID = %s", (uTID,))
        if cursor.fetchone()['count'] > 0:
            flash('Cannot delete: teacher has assigned classes.', 'error')
            return redirect(url_for('admin.manage_teachers'))
            
        cursor.execute("DELETE FROM Teachers WHERE uTID = %s", (uTID,))
        
        # Audit Logging
        log_system_action(cursor, 'Teachers', uTID, 'Delete', session['user_id'], session['role'], f"Teacher deleted (ID: {uTID})")
        
        conn.commit()
        flash('Teacher deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting teacher: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin.manage_teachers'))

@admin.route('/manage_subjects', methods=['GET', 'POST'])
def manage_subjects():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        subject_code = request.form.get('subject_code')
        subject_name = request.form.get('subject_name')
        
        cursor.execute("INSERT INTO Subjects (subject_code, subject_name) VALUES (%s, %s) RETURNING subject_id", (subject_code, subject_name))
        subject_id = cursor.fetchone()['subject_id']
        
        # Audit Logging
        log_system_action(cursor, 'Subjects', subject_id, 'Create', session['user_id'], session['role'], f"Subject created: {subject_code} - {subject_name}")
        
        conn.commit()
        flash('Subject added successfully.', 'success')
        return redirect(url_for('admin.manage_subjects'))
        
    if request.args.get('clear'):
        session.pop('subjects_search', None)
        return redirect(url_for('admin.manage_subjects'))

    # Persist search in session
    search_param = request.args.get('search')
    if search_param is not None:
        session['subjects_search'] = search_param.strip()
    search = session.get('subjects_search', '')
    
    
    query = "SELECT * FROM Subjects WHERE 1=1"
    params = []
    if search:
        query += " AND (subject_code LIKE %s OR subject_name LIKE %s)"
        search_val = f"%{search}%"
        params.extend([search_val, search_val])
        
    cursor.execute(query, params)
    subjects = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_manage_subjects.html', subjects=subjects, search=search)

@admin.route('/edit_subject/<int:subject_id>', methods=['POST'])
def edit_subject(subject_id):
    subject_code = request.form.get('subject_code')
    subject_name = request.form.get('subject_name')
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("UPDATE Subjects SET subject_code = %s, subject_name = %s WHERE subject_id = %s", 
                   (subject_code, subject_name, subject_id))
    
    # Audit Logging
    log_system_action(cursor, 'Subjects', subject_id, 'Update', session['user_id'], session['role'], f"Subject updated: {subject_code} - {subject_name}")
    
    conn.commit()
    cursor.close()
    conn.close()
    flash('Subject updated successfully.', 'success')
    return redirect(url_for('admin.manage_subjects'))

@admin.route('/delete_subject/<int:subject_id>')
def delete_subject(subject_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("DELETE FROM Subjects WHERE subject_id = %s", (subject_id,))
        
        # Audit Logging
        log_system_action(cursor, 'Subjects', subject_id, 'Delete', session['user_id'], session['role'], f"Subject deleted (ID: {subject_id})")
        
        conn.commit()
        flash('Subject deleted successfully.', 'success')
    except Exception as e:
        flash('Cannot delete: subject has attendance records or assignments.', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin.manage_subjects'))


@admin.route('/assign_classes', methods=['GET', 'POST'])
def assign_classes():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        uTID = request.form.get('utid')
        subject_id = request.form.get('subject_id')
        section = request.form.get('section')
        
        cursor.execute("INSERT INTO Teacher_Assignments (uTID, subject_id, section) VALUES (%s, %s, %s) RETURNING assignment_id", (uTID, subject_id, section))
        assignment_id = cursor.fetchone()['assignment_id']
        
        # Audit Logging
        log_system_action(cursor, 'Teacher_Assignments', assignment_id, 'Create', session['user_id'], session['role'], f"Class assigned to teacher {uTID}: Subject ID {subject_id}, Section {section}")
        
        conn.commit()
        flash('Class successfully assigned to teacher.', 'success')
        return redirect(url_for('admin.assign_classes'))

    if request.args.get('clear'):
        session.pop('assignments_search', None)
        return redirect(url_for('admin.assign_classes'))

    # Persist search in session
    search_param = request.args.get('search')
    if search_param is not None:
        session['assignments_search'] = search_param.strip()
    search = session.get('assignments_search', '')
    

    cursor.execute("SELECT * FROM Teachers WHERE status = 'Active'")
    teachers = cursor.fetchall()
    
    cursor.execute("SELECT * FROM Subjects")
    subjects = cursor.fetchall()
    
    query = """
        SELECT ta.assignment_id, t.first_name, t.middle_name, t.last_name, s.subject_code, s.subject_name, ta.section
        FROM Teacher_Assignments ta
        JOIN Teachers t ON ta.uTID = t.uTID
        JOIN Subjects s ON ta.subject_id = s.subject_id
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (s.subject_code LIKE %s OR s.subject_name LIKE %s OR t.first_name LIKE %s OR t.last_name LIKE %s OR ta.section LIKE %s)"
        search_val = f"%{search}%"
        params.extend([search_val, search_val, search_val, search_val, search_val])
        
    cursor.execute(query, params)
    assignments = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin_assign_classes.html', teachers=teachers, subjects=subjects, assignments=assignments, search=search)

@admin.route('/enroll_student', methods=['POST'])
def enroll_student():
    uSID = request.form.get('usid')
    assignment_id = request.form.get('assignment_id') # Selected from Teacher_Assignments
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
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
            cursor.execute("INSERT INTO Enrollments (uSID, subject_id, section) VALUES (%s, %s, %s) RETURNING enrollment_id", 
                           (uSID, assignment['subject_id'], assignment['section']))
            enrollment_id = cursor.fetchone()['enrollment_id']
            
            # Audit Logging
            log_system_action(cursor, 'Enrollments', enrollment_id, 'Create', session['user_id'], session['role'], f"Student {uSID} enrolled in Subject {assignment['subject_id']}, Section {assignment['section']}")
            
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
    """
    Handles creating and viewing class schedules.
    Validates that the time falls within school hours (07:00 to 18:00).
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        assignment_id = request.form.get('assignment_id')
        day = request.form.get('day_of_week')
        start = request.form.get('start_time')
        end = request.form.get('end_time')
        room = request.form.get('room')
        
        # Time validation
        try:
            from datetime import datetime
            start_dt = datetime.strptime(start, '%H:%M').time()
            end_dt = datetime.strptime(end, '%H:%M').time()
            school_start = datetime.strptime('07:00', '%H:%M').time()
            school_end = datetime.strptime('18:00', '%H:%M').time()
            
            if start_dt < school_start or end_dt > school_end:
                flash('Schedule must be within school hours (07:00 to 18:00).', 'error')
                return redirect(url_for('admin.manage_schedules'))
                
            if start_dt >= end_dt:
                flash('End time must be after start time.', 'error')
                return redirect(url_for('admin.manage_schedules'))
        except ValueError:
            flash('Invalid time format.', 'error')
            return redirect(url_for('admin.manage_schedules'))
        
        # Get details from Teacher_Assignments
        cursor.execute("SELECT * FROM Teacher_Assignments WHERE assignment_id = %s", (assignment_id,))
        ta = cursor.fetchone()
        
        if ta:
            # Conflict Check: Does this teacher or room already have a class at this time?
            conflict_query = """
                SELECT sch.*, s.subject_code 
                FROM schedule sch
                JOIN Subjects s ON sch.subject_id = s.subject_id
                WHERE sch.day_of_week = %s 
                AND (%s < sch.end_time AND %s > sch.start_time)
                AND (sch.uTID = %s OR sch.room = %s)
            """
            cursor.execute(conflict_query, (day, start, end, ta['utid'], room))
            conflict = cursor.fetchone()
            
            if conflict:
                conflict_type = "Teacher" if conflict['utid'] == ta['utid'] else "Room"
                flash(f"Conflict Detected! {conflict_type} is already busy with {conflict['subject_code']} at this time.", "error")
            else:
                cursor.execute("""
                    INSERT INTO schedule (subject_id, uTID, section, day_of_week, start_time, end_time, room)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (ta['subject_id'], ta['utid'], ta['section'], day, start, end, room))
                schedule_id = cursor.lastrowid
                
                # Audit Logging
                log_system_action(cursor, 'schedule', schedule_id, 'Create', session['user_id'], session['role'], f"Schedule created for {ta['subject_id']} - {ta['section']} on {day} ({start}-{end})")
                
                conn.commit()
                flash('Schedule added successfully.', 'success')

    if request.args.get('clear'):
        session.pop('schedules_search', None)
        return redirect(url_for('admin.manage_schedules'))

    # Persist search in session
    search_param = request.args.get('search')
    if search_param is not None:
        session['schedules_search'] = search_param.strip()
    search = session.get('schedules_search', '')
    

    cursor.execute("""
        SELECT ta.assignment_id, t.first_name, t.middle_name, t.last_name, s.subject_code, s.subject_name, ta.section
        FROM Teacher_Assignments ta
        JOIN Teachers t ON ta.uTID = t.uTID
        JOIN Subjects s ON ta.subject_id = s.subject_id
    """)
    assignments = cursor.fetchall()
    
    query = """
        SELECT sch.*, s.subject_code, s.subject_name, t.first_name, t.middle_name, t.last_name
        FROM schedule sch
        JOIN Subjects s ON sch.subject_id = s.subject_id
        JOIN Teachers t ON sch.uTID = t.uTID
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (s.subject_code LIKE %s OR s.subject_name LIKE %s OR t.first_name LIKE %s OR t.last_name LIKE %s OR sch.room LIKE %s OR sch.section LIKE %s)"
        search_val = f"%{search}%"
        params.extend([search_val, search_val, search_val, search_val, search_val, search_val])
        
    cursor.execute(query, params)
    schedules = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin_manage_schedules.html', assignments=assignments, schedules=schedules, search=search)

@admin.route('/remove_schedule/<int:schedule_id>')
def remove_schedule(schedule_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("DELETE FROM schedule WHERE schedule_id = %s", (schedule_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Schedule removed successfully.', 'success')
    return redirect(url_for('admin.manage_schedules'))

@admin.route('/remove_enrollment/<int:enrollment_id>')
def remove_enrollment(enrollment_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("DELETE FROM Enrollments WHERE enrollment_id = %s", (enrollment_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Enrollment removed successfully.', 'success')
    return redirect(url_for('admin.manage_students'))

@admin.route('/archive_student/<uSID>')
def archive_student(uSID):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("UPDATE Students SET status = 'Archived' WHERE uSID = %s", (uSID,))
    
    # Audit Logging
    log_system_action(cursor, 'Students', uSID, 'Update', session['user_id'], session['role'], f"Student archived: {uSID}")
    
    conn.commit()
    cursor.close()
    conn.close()
    flash('Student archived successfully.', 'success')
    return redirect(url_for('admin.manage_students'))

@admin.route('/unarchive_student/<uSID>')
def unarchive_student(uSID):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("UPDATE Students SET status = 'Active' WHERE uSID = %s", (uSID,))
    
    # Audit Logging
    log_system_action(cursor, 'Students', uSID, 'Update', session['user_id'], session['role'], f"Student unarchived: {uSID}")
    
    conn.commit()
    cursor.close()
    conn.close()
    flash('Student unarchived successfully.', 'success')
    return redirect(url_for('admin.manage_students'))

@admin.route('/archive_teacher/<uTID>')
def archive_teacher(uTID):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("UPDATE Teachers SET status = 'Archived' WHERE uTID = %s", (uTID,))
    
    # Audit Logging
    log_system_action(cursor, 'Teachers', uTID, 'Update', session['user_id'], session['role'], f"Teacher archived: {uTID}")
    
    conn.commit()
    cursor.close()
    conn.close()
    flash('Teacher archived successfully.', 'success')
    return redirect(url_for('admin.manage_teachers'))

@admin.route('/unarchive_teacher/<uTID>')
def unarchive_teacher(uTID):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("UPDATE Teachers SET status = 'Active' WHERE uTID = %s", (uTID,))
    
    # Audit Logging
    log_system_action(cursor, 'Teachers', uTID, 'Update', session['user_id'], session['role'], f"Teacher unarchived: {uTID}")
    
    conn.commit()
    cursor.close()
    conn.close()
    flash('Teacher unarchived successfully.', 'success')
    return redirect(url_for('admin.manage_teachers'))

@admin.route('/remove_assignment/<int:assignment_id>')
def remove_assignment(assignment_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
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
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.args.get('clear'):
        session.pop('drops_search', None)
        return redirect(url_for('admin.drop_requests'))

    # Persist search in session
    search_param = request.args.get('search')
    if search_param is not None:
        session['drops_search'] = search_param.strip()
    search = session.get('drops_search', '')
    

    query = """
        SELECT dr.*, s.first_name as s_first, s.middle_name as s_middle, s.last_name as s_last, 
               sub.subject_code, sub.subject_name,
               t.first_name as t_first, t.middle_name as t_middle, t.last_name as t_last
        FROM Drop_Requests dr
        JOIN Students s ON dr.uSID = s.uSID
        JOIN Subjects sub ON dr.subject_id = sub.subject_id
        JOIN Teachers t ON dr.uTID = t.uTID
        WHERE dr.status = 'Pending'
    """
    params = []
    
    if search:
        query += " AND (s.first_name LIKE %s OR s.last_name LIKE %s OR s.uSID LIKE %s OR sub.subject_code LIKE %s OR sub.subject_name LIKE %s)"
        search_val = f"%{search}%"
        params.extend([search_val, search_val, search_val, search_val, search_val])
        
    query += " ORDER BY dr.created_at DESC"
    cursor.execute(query, params)
    requests = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin_drop_requests.html', requests=requests, search=search)

@admin.route('/approve_drop/<int:request_id>')
def approve_drop(request_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("SELECT * FROM Drop_Requests WHERE request_id = %s", (request_id,))
    req = cursor.fetchone()
    
    if req:
        # 1. Update drop request status
        cursor.execute("UPDATE Drop_Requests SET status = 'Approved' WHERE request_id = %s", (request_id,))
        
        # 2. Find the section if possible (or just remove by uSID and subject_id)
        # Assuming we want to remove them from the specific subject they dropped
        cursor.execute("DELETE FROM Enrollments WHERE uSID = %s AND subject_id = %s", (req['usid'], req['subject_id']))
        
        # 3. Optional: Global Archive (Keeping it as per previous logic, but usually a drop is per subject)
        # If the user wants the student to be 'Archived' globally, we keep this.
        cursor.execute("UPDATE Students SET status = 'Archived' WHERE uSID = %s", (req['usid'],))
        
        conn.commit()
        flash('Drop request approved. Student has been unenrolled from the subject and archived.', 'success')
    
    cursor.close()
    conn.close()
    return redirect(url_for('admin.drop_requests'))

@admin.route('/reject_drop/<int:request_id>')
def reject_drop(request_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
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
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
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
            enroll_data = [(s['usid'], assignment['subject_id'], assignment['section']) for s in students_to_enroll]
            
            cursor.executemany(enroll_query, enroll_data)
            conn.commit()
            flash(f'Successfully enrolled {len(students_to_enroll)} students into {assignment["section"]}.', 'success')
            
    except Exception as e:
        flash(f'Error in bulk enrollment: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin.manage_students'))

@admin.route('/audit_logs')
def audit_logs():
    """
    View system-wide audit logs with pagination, search, and filtering.
    """
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    if request.args.get('clear'):
        session.pop('audit_search', None)
        session.pop('audit_table', None)
        session.pop('audit_action', None)
        return redirect(url_for('admin.audit_logs'))

    # Persist search and filters in session
    search_param = request.args.get('search')
    if search_param is not None:
        session['audit_search'] = search_param.strip()
    search = session.get('audit_search', '')

    table_param = request.args.get('table_filter')
    if table_param is not None:
        session['audit_table'] = table_param.strip()
    table_filter = session.get('audit_table', '')

    action_param = request.args.get('action_filter')
    if action_param is not None:
        session['audit_action'] = action_param.strip()
    action_filter = session.get('audit_action', '')
    
    
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Base query
    query = "FROM System_Audit_Log WHERE 1=1"
    params = []
    
    if search:
        query += " AND (details LIKE %s OR performed_by_id LIKE %s OR entity_id LIKE %s)"
        search_val = f"%{search}%"
        params.extend([search_val, search_val, search_val])
        
    if table_filter:
        query += " AND table_name = %s"
        params.append(table_filter)
        
    if action_filter:
        if action_filter == 'Status':
            query += " AND (action = 'Update' AND details LIKE '%Status%')"
        else:
            query += " AND action = %s"
            params.append(action_filter)
        
    # Count total
    cursor.execute("SELECT COUNT(*) as total " + query, params)
    total_count = cursor.fetchone()['total']
    total_pages = (total_count + per_page - 1) // per_page
    
    # Select data
    select_query = "SELECT * " + query + " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
    select_params = params + [per_page, offset]
    
    cursor.execute(select_query, select_params)
    logs = cursor.fetchall()
    
    # Fetch unique tables for filter
    cursor.execute("SELECT DISTINCT table_name FROM System_Audit_Log ORDER BY table_name ASC")
    tables = [row['table_name'] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return render_template('admin_audit_logs.html', 
                           logs=logs, 
                           total_pages=total_pages, 
                           current_page=page,
                           search=search,
                           table_filter=table_filter,
                           action_filter=action_filter,
                           tables=tables)

@admin.route('/attendance_analytics')
def attendance_analytics():
    subject_id = request.args.get('subject_id', type=int)
    uTID = request.args.get('utid')
    section = request.args.get('section')
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Fetch all assigned classes for the selector
    cursor.execute("""
        SELECT s.subject_id, s.subject_code, s.subject_name, ta.section, ta.uTID,
               t.first_name, t.middle_name, t.last_name
        FROM Teacher_Assignments ta
        JOIN Subjects s ON ta.subject_id = s.subject_id
        JOIN Teachers t ON ta.uTID = t.uTID
        ORDER BY s.subject_code, ta.section
    """)
    all_classes = cursor.fetchall()
    
    weekly_trends = []
    monthly_trends = []
    selected_class = None
    
    if subject_id and uTID and section:
        # Find selected class details
        for c in all_classes:
            if c['subject_id'] == subject_id and c['utid'] == uTID and c['section'] == section:
                selected_class = c
                break
        
        if selected_class:
            # Weekly Trends
            cursor.execute("""
                SELECT CONCAT('Week ', CEIL(DAY(a.scan_time) / 7), ' - ', MONTHNAME(a.scan_time), ' ', YEAR(a.scan_time)) as period,
                       YEAR(a.scan_time) as yr,
                       MONTH(a.scan_time) as mo,
                       CEIL(DAY(a.scan_time) / 7) as wk,
                       MIN(DATE(a.scan_time)) as week_start,
                       MAX(DATE(a.scan_time)) as week_end,
                       COUNT(DISTINCT a.uSID, DATE(a.scan_time)) as total_students,
                       SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
                       SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
                       SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as late_count
                FROM Attendance a
                JOIN Sessions ses ON a.session_id = ses.session_id
                WHERE ses.subject_id = %s AND ses.uTID = %s AND ses.section = %s
                GROUP BY yr, mo, wk, period
                ORDER BY yr DESC, mo DESC, wk DESC
            """, (subject_id, uTID, section))
            weekly_trends = cursor.fetchall()
            
            # Monthly Trends
            cursor.execute("""
                SELECT CONCAT(MONTHNAME(a.scan_time), ' ', YEAR(a.scan_time)) as period,
                       YEAR(a.scan_time) as yr,
                       MONTH(a.scan_time) as mo,
                       COUNT(DISTINCT a.uSID, DATE(a.scan_time)) as total_students,
                       SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
                       SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
                       SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as late_count
                FROM Attendance a
                JOIN Sessions ses ON a.session_id = ses.session_id
                WHERE ses.subject_id = %s AND ses.uTID = %s AND ses.section = %s
                GROUP BY yr, mo, period
                ORDER BY yr DESC, mo DESC
            """, (subject_id, uTID, section))
            monthly_trends = cursor.fetchall()

    cursor.close()
    conn.close()
    
    return render_template('admin_attendance_analytics.html', 
                           all_classes=all_classes,
                           selected_class=selected_class,
                           weekly_trends=weekly_trends,
                           monthly_trends=monthly_trends)
