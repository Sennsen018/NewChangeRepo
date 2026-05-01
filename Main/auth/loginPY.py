from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash
from Main.db import get_db_connection
from datetime import datetime, timedelta
import secrets
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def generate_otp():
    return str(secrets.randbelow(9000) + 1000)

def send_otp_email(receiver_email, otp, unique_id=''):
    # Default configuration - should ideally be in .env
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not smtp_user or not smtp_password or "your-email" in smtp_user:
        print("CRITICAL: SMTP credentials not configured in .env file.")
        return False
    
    msg = MIMEMultipart()
    msg['From'] = f"Attendeez Support <{smtp_user}>"
    msg['To'] = receiver_email
    msg['Subject'] = f"{otp} is your Attendeez Reset Code"
    
    # Build unique ID section if available
    uid_section = ''
    if unique_id:
        uid_section = f"""
            <div style="text-align: center; margin: 20px 0; padding: 15px; background: #eef4ff; border-radius: 8px; border: 1px dashed #4A90E2;">
                <p style="margin: 0 0 6px 0; font-size: 13px; color: #555;">Your Unique System ID</p>
                <span style="font-size: 22px; font-weight: bold; letter-spacing: 3px; color: #4A90E2;">{unique_id}</span>
                <p style="margin: 6px 0 0 0; font-size: 12px; color: #888;">Use this ID to log in to the system.</p>
            </div>
        """
    
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
            <h2 style="color: #4A90E2; text-align: center;">Password Reset Request</h2>
            <p>Hello,</p>
            <p>You requested to reset your password. Use the following OTP code to proceed:</p>
            <div style="text-align: center; margin: 30px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; background: #f4f4f4; padding: 10px 20px; border-radius: 5px; border: 1px dashed #4A90E2;">{otp}</span>
            </div>
            {uid_section}
            <p>This code will expire in 10 minutes. If you did not request this, please ignore this email.</p>
            <hr style="border: none; border-top: 1px solid #eee;">
            <p style="font-size: 12px; color: #888; text-align: center;">&copy; 2024 Attendeez Attendance System</p>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(body, 'html'))
    
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False

# ---------------------------------------------------------------------------
# OTP Rate-Limit / Lockout Helpers
# ---------------------------------------------------------------------------
OTP_MAX_SENDS      = 5          # max total OTP sends (initial + resends)
OTP_COOLDOWN_SECS  = 120        # seconds between resends
OTP_MAX_WRONG      = 5          # max wrong verification attempts
OTP_LOCKOUT_HOURS  = 12         # hours to lock after limit hit

def _get_otp_lockout(cursor, email):
    """Return lockout_until datetime if email is locked, else None."""
    try:
        cursor.execute(
            "SELECT lockout_until FROM otp_lockouts WHERE email = %s",
            (email,)
        )
        row = cursor.fetchone()
        if row:
            lu = row['lockout_until']
            if isinstance(lu, datetime) and lu > datetime.now():
                return lu
            # expired — clean up
            cursor.execute("DELETE FROM otp_lockouts WHERE email = %s", (email,))
    except Exception:
        pass
    return None

def _set_otp_lockout(conn, cursor, email):
    """Lock the email for OTP_LOCKOUT_HOURS hours."""
    until = datetime.now() + timedelta(hours=OTP_LOCKOUT_HOURS)
    cursor.execute(
        """INSERT INTO otp_lockouts (email, lockout_until)
           VALUES (%s, %s)
           ON DUPLICATE KEY UPDATE lockout_until = %s""",
        (email, until, until)
    )
    conn.commit()
    # Clear OTP session so user can't keep trying
    for k in ('reset_otp', 'reset_email', 'reset_unique_id', 'reset_type',
              'otp_expiry', 'otp_send_count', 'otp_last_sent', 'otp_wrong_count'):
        session.pop(k, None)
    return until

def _clear_otp_session():
    for k in ('reset_otp', 'reset_email', 'reset_unique_id', 'reset_type',
              'otp_expiry', 'otp_verified', 'otp_send_count',
              'otp_last_sent', 'otp_wrong_count'):
        session.pop(k, None)

auth = Blueprint('auth', __name__, template_folder='templates')

@auth.route('/login')
def login_redirect():
    """Redirects generic login path to the correct dashboard if logged in, else student login."""
    if 'user_id' in session:
        role = session.get('role')
        if role == 'student': return redirect(url_for('user.dashboard'))
        if role == 'teacher': return redirect(url_for('teacher.dashboard'))
        if role == 'admin': return redirect(url_for('admin.dashboard'))
    return redirect(url_for('auth.student_login'))


@auth.route('/student/login', methods=['GET', 'POST'])
def student_login():
    """Handles student authentication, session creation, and brute-force lockout."""
    if 'user_id' in session and session.get('role') == 'student':
        return redirect(url_for('user.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed', 'error')
            return render_template('student_login.html')
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Students WHERE uSID = %s", (email,))
        student = cursor.fetchone()
        
        if student:
            if student['status'] == 'Archived':
                flash('Account is disabled. Please contact admin.', 'error')
            elif student['lockout_time'] and student['lockout_time'] > datetime.now():
                flash(f'Account locked. Try again after {student["lockout_time"]}', 'error')
            elif check_password_hash(student['password_hash'], password):
                # Reset attempts
                cursor.execute("UPDATE Students SET failed_attempts = 0, lockout_time = NULL WHERE uSID = %s", (student['uSID'],))
                conn.commit()
                session['user_id'] = student['uSID']
                session['role'] = 'student'
                session['name'] = f"{student['first_name']} {student['middle_name']} {student['last_name']}"
                return redirect(url_for('user.dashboard'))
            else:
                attempts = student['failed_attempts'] + 1
                lockout = None
                if attempts >= 3:
                    lockout = datetime.now() + timedelta(minutes=3)
                    flash('Account locked for 3 minutes due to multiple failed attempts.', 'error')
                else:
                    flash('Invalid credentials.', 'error')
                cursor.execute("UPDATE Students SET failed_attempts = %s, lockout_time = %s WHERE uSID = %s", (attempts, lockout, student['uSID']))
                conn.commit()
        else:
            flash('Student not found.', 'error')
            
        cursor.close()
        conn.close()
        
    return render_template('student_login.html')

@auth.route('/teacher/login', methods=['GET', 'POST'])
def teacher_login():
    """Handles teacher authentication and dashboard redirection."""
    if 'user_id' in session and session.get('role') == 'teacher':
        return redirect(url_for('teacher.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed', 'error')
            return render_template('teacher_login.html')
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Teachers WHERE uTID = %s", (email,))
        teacher = cursor.fetchone()
        
        if teacher:
            if teacher['status'] == 'Archived':
                flash('Account is disabled.', 'error')
            elif teacher['lockout_time'] and teacher['lockout_time'] > datetime.now():
                flash(f'Account locked. Try again after {teacher["lockout_time"]}', 'error')
            elif check_password_hash(teacher['password_hash'], password):
                cursor.execute("UPDATE Teachers SET failed_attempts = 0, lockout_time = NULL WHERE uTID = %s", (teacher['uTID'],))
                conn.commit()
                session['user_id'] = teacher['uTID']
                session['role'] = 'teacher'
                session['name'] = f"{teacher['first_name']} {teacher['middle_name']} {teacher['last_name']}"
                return redirect(url_for('teacher.dashboard'))
            else:
                attempts = teacher['failed_attempts'] + 1
                lockout = None
                if attempts >= 3:
                    lockout = datetime.now() + timedelta(minutes=3)
                    flash('Account locked for 3 minutes.', 'error')
                else:
                    flash('Invalid credentials.', 'error')
                cursor.execute("UPDATE Teachers SET failed_attempts = %s, lockout_time = %s WHERE uTID = %s", (attempts, lockout, teacher['uTID']))
                conn.commit()
        else:
            flash('Teacher not found.', 'error')
            
        cursor.close()
        conn.close()
        
    return render_template('teacher_login.html')

@auth.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Handles admin authentication and dashboard redirection."""
    if 'user_id' in session and session.get('role') == 'admin':
        return redirect(url_for('admin.dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Admins WHERE username = %s", (username,))
        admin = cursor.fetchone()
        
        if admin and check_password_hash(admin['password_hash'], password):
            session['user_id'] = admin['admin_id']
            session['role'] = 'admin'
            return redirect(url_for('admin.dashboard'))
        flash('Invalid credentials.', 'error')
        cursor.close()
        conn.close()
    return render_template('admin_login.html')

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Initiates the password reset process by generating and sending an OTP."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # --- Check lockout first ---
        lockout_until = _get_otp_lockout(cursor, email)
        if lockout_until:
            conn.commit()
            cursor.close()
            conn.close()
            remaining = lockout_until - datetime.now()
            hours, rem = divmod(int(remaining.total_seconds()), 3600)
            mins = rem // 60
            flash(
                f'This account is temporarily locked due to too many OTP attempts. '
                f'Please try again in {hours}h {mins}m.',
                'error'
            )
            return render_template('forgot_password.html')
        
        # Check in all three tables by email, also fetch unique ID
        user = None
        user_type = None
        unique_id = None
        
        # Check Students
        cursor.execute("SELECT uSID, email FROM Students WHERE email = %s", (email,))
        user = cursor.fetchone()
        if user:
            user_type = 'student'
            unique_id = user['uSID']
        
        if not user:
            # Check Teachers
            cursor.execute("SELECT uTID, email FROM Teachers WHERE email = %s", (email,))
            user = cursor.fetchone()
            if user:
                user_type = 'teacher'
                unique_id = user['uTID']
            
        if not user:
            # Check Admins
            cursor.execute("SELECT username, email FROM Admins WHERE email = %s", (email,))
            user = cursor.fetchone()
            if user:
                user_type = 'admin'
                unique_id = user['username']
            
        if user:
            otp = generate_otp()
            session['reset_otp']       = otp
            session['reset_email']     = email
            session['reset_unique_id'] = unique_id
            session['reset_type']      = user_type
            session['otp_expiry']      = (datetime.now() + timedelta(minutes=10)).timestamp()
            # Rate-limit tracking: first send counts as 1
            session['otp_send_count']  = 1
            session['otp_last_sent']   = datetime.now().timestamp()
            session['otp_wrong_count'] = 0
            
            # Send OTP email — includes the unique ID inside the email body
            if send_otp_email(email, otp, unique_id):
                flash('OTP sent to your email. Check your inbox for your code and Unique ID.', 'success')
            else:
                flash('Failed to send email. Please contact support.', 'error')
            
            cursor.close()
            conn.close()
            return redirect(url_for('auth.verify_otp'))
        else:
            flash('Email not found in our records.', 'error')
            
        cursor.close()
        conn.close()
        
    return render_template('forgot_password.html')

@auth.route('/resend-otp')
def resend_otp():
    email = session.get('reset_email')
    if not email:
        flash('Session expired. Please try again.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # --- Check DB lockout ---
    lockout_until = _get_otp_lockout(cursor, email)
    if lockout_until:
        conn.commit()
        cursor.close()
        conn.close()
        remaining = lockout_until - datetime.now()
        hours, rem = divmod(int(remaining.total_seconds()), 3600)
        mins = rem // 60
        _clear_otp_session()
        flash(
            f'Your account is locked for {hours}h {mins}m due to too many OTP requests. '
            f'Please try again later.',
            'error'
        )
        return redirect(url_for('auth.forgot_password'))
    
    # --- Check total send count ---
    send_count = session.get('otp_send_count', 0)
    if send_count >= OTP_MAX_SENDS:
        # Lock the account
        until = _set_otp_lockout(conn, cursor, email)
        cursor.close()
        conn.close()
        hours, rem = divmod(OTP_LOCKOUT_HOURS * 3600, 3600)
        flash(
            f'You have reached the maximum OTP request limit ({OTP_MAX_SENDS} times). '
            f'Your account is locked for {OTP_LOCKOUT_HOURS} hours.',
            'error'
        )
        return redirect(url_for('auth.forgot_password'))
    
    # --- Check 2-minute cooldown ---
    last_sent  = session.get('otp_last_sent', 0)
    elapsed    = datetime.now().timestamp() - last_sent
    if elapsed < OTP_COOLDOWN_SECS:
        wait = int(OTP_COOLDOWN_SECS - elapsed)
        cursor.close()
        conn.close()
        flash(f'Please wait {wait} second(s) before requesting another OTP.', 'error')
        return redirect(url_for('auth.verify_otp'))
    
    cursor.close()
    conn.close()
    
    # --- All clear — resend ---
    unique_id = session.get('reset_unique_id', '')
    otp = generate_otp()
    session['reset_otp']      = otp
    session['otp_expiry']     = (datetime.now() + timedelta(minutes=10)).timestamp()
    session['otp_send_count'] = send_count + 1
    session['otp_last_sent']  = datetime.now().timestamp()
    
    if send_otp_email(email, otp, unique_id):
        remaining_sends = OTP_MAX_SENDS - (send_count + 1)
        flash(
            f'A new OTP has been sent to your email. '
            f'You have {remaining_sends} resend(s) remaining.',
            'success'
        )
    else:
        flash('Failed to send email. Please try again.', 'error')
        
    return redirect(url_for('auth.verify_otp'))

@auth.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reset_otp' not in session:
        return redirect(url_for('auth.forgot_password'))
    
    email = session.get('reset_email', '')
    
    # Pass rate-limit info to template
    send_count  = session.get('otp_send_count', 1)
    wrong_count = session.get('otp_wrong_count', 0)
    last_sent   = session.get('otp_last_sent', 0)
    resends_left   = max(0, OTP_MAX_SENDS - send_count)
    cooldown_ends  = int(last_sent + OTP_COOLDOWN_SECS)  # epoch seconds
        
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        
        # --- Check DB lockout first ---
        if email:
            conn   = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            lockout_until = _get_otp_lockout(cursor, email)
            conn.commit()
            cursor.close()
            conn.close()
            if lockout_until:
                remaining = lockout_until - datetime.now()
                hours, rem = divmod(int(remaining.total_seconds()), 3600)
                mins = rem // 60
                _clear_otp_session()
                flash(
                    f'Your account is locked for {hours}h {mins}m. Try again later.',
                    'error'
                )
                return redirect(url_for('auth.forgot_password'))
        
        if datetime.now().timestamp() > session.get('otp_expiry', 0):
            flash('OTP has expired. Please request a new one.', 'error')
            return redirect(url_for('auth.forgot_password'))
            
        if entered_otp == session.get('reset_otp'):
            session['otp_verified']    = True
            session['otp_wrong_count'] = 0
            return redirect(url_for('auth.reset_password'))
        else:
            wrong_count += 1
            session['otp_wrong_count'] = wrong_count
            attempts_left = OTP_MAX_WRONG - wrong_count
            
            if wrong_count >= OTP_MAX_WRONG:
                # Lock account for 12 hours
                if email:
                    conn   = get_db_connection()
                    cursor = conn.cursor(dictionary=True)
                    _set_otp_lockout(conn, cursor, email)
                    cursor.close()
                    conn.close()
                flash(
                    f'Too many incorrect attempts. Your account has been locked '
                    f'for {OTP_LOCKOUT_HOURS} hours.',
                    'error'
                )
                return redirect(url_for('auth.forgot_password'))
            else:
                flash(
                    f'Invalid OTP code. You have {attempts_left} attempt(s) remaining.',
                    'error'
                )
            
    return render_template(
        'verify_otp.html',
        resends_left=resends_left,
        cooldown_ends=cooldown_ends,
        wrong_count=session.get('otp_wrong_count', 0),
        max_wrong=OTP_MAX_WRONG
    )

@auth.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified'):
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html')
            
        email = session.get('reset_email')
        user_type = session.get('reset_type')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        hashed_pw = generate_password_hash(new_password)
        
        if user_type == 'student':
            cursor.execute("UPDATE Students SET password_hash = %s WHERE email = %s", (hashed_pw, email))
        elif user_type == 'teacher':
            cursor.execute("UPDATE Teachers SET password_hash = %s WHERE email = %s", (hashed_pw, email))
        elif user_type == 'admin':
            cursor.execute("UPDATE Admins SET password_hash = %s WHERE email = %s", (hashed_pw, email))
            
        conn.commit()
        cursor.close()
        conn.close()
        
        # Clear session (including rate-limit keys)
        _clear_otp_session()
        session.pop('reset_unique_id', None)
        
        flash('Password reset successful! You can now login.', 'success')
        if user_type == 'admin':
            return redirect(url_for('auth.admin_login'))
        elif user_type == 'teacher':
            return redirect(url_for('auth.teacher_login'))
        else:
            return redirect(url_for('auth.student_login'))
            
    return render_template('reset_password.html')

@auth.route('/logout')
def logout():
    role = session.get('role')
    session.clear()
    if role == 'admin':
        return redirect(url_for('auth.admin_login'))
    return redirect(url_for('auth.student_login'))

@auth.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('auth.login_redirect'))
        
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('change_password.html')
            
        role = session.get('role')
        uID = session.get('user_id')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        table = 'Students' if role == 'student' else 'Teachers' if role == 'teacher' else 'Admins'
        id_col = 'uSID' if role == 'student' else 'uTID' if role == 'teacher' else 'admin_id'
        
        cursor.execute(f"SELECT * FROM {table} WHERE {id_col} = %s", (uID,))
        user = cursor.fetchone()
        
        from werkzeug.security import check_password_hash, generate_password_hash
        if user and check_password_hash(user['password_hash'], current_password):
            new_hash = generate_password_hash(new_password)
            cursor.execute(f"UPDATE {table} SET password_hash = %s WHERE {id_col} = %s", (new_hash, uID))
            conn.commit()
            flash('Password updated successfully.', 'success')
            dest = 'user.dashboard' if role == 'student' else 'teacher.dashboard' if role == 'teacher' else 'admin.dashboard'
            return redirect(url_for(dest))
        else:
            flash('Incorrect current password.', 'error')
            
        cursor.close()
        conn.close()
        
    return render_template('change_password.html')