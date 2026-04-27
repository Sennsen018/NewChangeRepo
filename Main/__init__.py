from flask import Flask, redirect, url_for
import os
from datetime import timedelta

db_config = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "atendeez_db"),
    "port": int(os.getenv("DB_PORT", 3306))
}

def reg_app():
    app = Flask(__name__)

    app.secret_key = os.getenv('SECRET_KEY', os.urandom(32))

    # SESSION SETTINGS
    app.config['SESSION_COOKIE_SECURE'] = False  # 🔥 IMPORTANT (local dev)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    @app.route('/')
    def index():
        return redirect(url_for('auth.student_login'))

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