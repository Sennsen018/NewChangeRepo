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

def send_otp_email(receiver_email, otp):
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

auth = Blueprint('auth', __name__, template_folder='templates')

@auth.route('/login')
def login_redirect():
    # Redirect base /login to student login
    return redirect(url_for('auth.student_login'))


@auth.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed', 'error')
            return render_template('student_login.html')
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Students WHERE email = %s OR uSID = %s", (email, email))
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
                session['name'] = f"{student['first_name']} {student['last_name']}"
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
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed', 'error')
            return render_template('teacher_login.html')
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Teachers WHERE email = %s OR uTID = %s", (email, email))
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
                session['name'] = f"{teacher['first_name']} {teacher['last_name']}"
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
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Admins WHERE username = %s OR email = %s", (username, username))
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
    if request.method == 'POST':
        email = request.form.get('email')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check in all three tables
        user = None
        user_type = None
        
        # Check Students
        cursor.execute("SELECT email FROM Students WHERE email = %s", (email,))
        user = cursor.fetchone()
        if user: user_type = 'student'
        
        if not user:
            # Check Teachers
            cursor.execute("SELECT email FROM Teachers WHERE email = %s", (email,))
            user = cursor.fetchone()
            if user: user_type = 'teacher'
            
        if not user:
            # Check Admins
            cursor.execute("SELECT email FROM Admins WHERE email = %s", (email,))
            user = cursor.fetchone()
            if user: user_type = 'admin'
            
        if user:
            otp = generate_otp()
            session['reset_otp'] = otp
            session['reset_email'] = email
            session['reset_type'] = user_type
            session['otp_expiry'] = (datetime.now() + timedelta(minutes=10)).timestamp()
            
            # For demonstration, we'll flash the OTP if email sending fails or is not configured
            if send_otp_email(email, otp):
                flash('OTP sent to your email.', 'success')
            else:
                flash('Failed to send email. Please contact support.', 'error')
            
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
        
    otp = generate_otp()
    session['reset_otp'] = otp
    session['otp_expiry'] = (datetime.now() + timedelta(minutes=10)).timestamp()
    
    if send_otp_email(email, otp):
        flash('A new OTP has been sent to your email.', 'success')
    else:
        flash('Failed to send email. Please try again.', 'error')
        
    return redirect(url_for('auth.verify_otp'))

@auth.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reset_otp' not in session:
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        
        if datetime.now().timestamp() > session.get('otp_expiry', 0):
            flash('OTP has expired. Please request a new one.', 'error')
            return redirect(url_for('auth.forgot_password'))
            
        if entered_otp == session.get('reset_otp'):
            session['otp_verified'] = True
            return redirect(url_for('auth.reset_password'))
        else:
            flash('Invalid OTP code.', 'error')
            
    return render_template('verify_otp.html')

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
        
        # Clear session
        session.pop('reset_otp', None)
        session.pop('reset_email', None)
        session.pop('reset_type', None)
        session.pop('otp_expiry', None)
        session.pop('otp_verified', None)
        
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