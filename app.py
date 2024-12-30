import os
import secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
from auth.routes import auth_bp
from quiz.routes import quiz_bp
from review.routes import review_bp
from main.routes import main_bp
from admin.routes import admin_bp
from utils import get_db_connection

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(32)
# REMOVE THE HARD CODED PATH
# app.config['DATABASE'] = r"C:\Users\anubh\Desktop\Project PSM\mcq_app\data\mcq_database.db"


app.register_blueprint(auth_bp)
app.register_blueprint(quiz_bp, url_prefix='/quiz')
app.register_blueprint(review_bp, url_prefix='/review')
app.register_blueprint(main_bp)
app.register_blueprint(admin_bp)


def with_db_connection(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        conn = get_db_connection()  # Use the updated get_db_connection
        try:
            result = f(conn, *args, **kwargs)
            conn.commit()
            return result
        except sqlite3.Error as e:
            app.logger.error(f"Database error: {e}")
            conn.rollback()
            flash('A database error occurred.', 'error')
            return redirect(url_for('main.hello'))
        finally:
            conn.close()
    return decorated_function


@app.before_request
def before_request():
    if session.get('user_id'):
        update_last_activity()
        set_user_role()


@with_db_connection
def update_last_activity(conn=None):
    user_id = session.get('user_id')
    if user_id:
        now = datetime.now()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_activity = ? WHERE id = ?", (now, user_id))


@with_db_connection
def set_user_role(conn=None):
    user_id = session.get('user_id')
    if user_id:
        cursor = conn.cursor()
        cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        session['user_role'] = user['role'] if user else None


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)