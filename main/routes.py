# main/routes.py
from flask import Blueprint, render_template, url_for, redirect, session
from utils import get_db_connection

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def hello():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    review_url = url_for('review.review_mode')
    study_url = url_for('main.study_mode')
    return render_template('index.html', review_url=review_url, study_url=study_url)

@main_bp.route('/study')
def study_mode():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT topic FROM questions WHERE topic IS NOT NULL AND topic != ''")
    topics = [row['topic'] for row in cursor.fetchall()]
    conn.close()
    return render_template('study_mode.html', topics=topics)