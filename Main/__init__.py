from flask import Flask, redirect, url_for, session
import os
from datetime import timedelta


def reg_app():
    app = Flask(__name__)

    app.secret_key = os.getenv('SECRET_KEY', os.urandom(32))

    # SESSION SETTINGS
    app.config['SESSION_COOKIE_SECURE'] = False  # 🔥 IMPORTANT (local dev)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=6)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    from flask_wtf.csrf import CSRFProtect
    csrf = CSRFProtect()
    csrf.init_app(app)

    @app.route('/')
    def index():
        if 'user_id' in session:
            role = session.get('role')
            if role == 'student': return redirect(url_for('user.dashboard'))
            if role == 'teacher': return redirect(url_for('teacher.dashboard'))
            if role == 'admin': return redirect(url_for('admin.dashboard'))
        return redirect(url_for('auth.student_login'))

    @app.route('/.well-known/appspecific/com.chrome.devtools.json')
    def chrome_devtools():
        return "{}", 200, {'Content-Type': 'application/json'}

    # IMPORT BLUEPRINTS
    from Main.admin.crudPY import crud
    from Main.admin.adminPY import admin
    from Main.auth.loginPY import auth
    from Main.student.studentPY import user
    from Main.teacher.teacherPY import teacher
    

    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(crud)
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(user, url_prefix='/user')
    app.register_blueprint(teacher, url_prefix='/teacher')

    return app
