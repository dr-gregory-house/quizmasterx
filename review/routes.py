# review/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from utils import get_db_connection
from datetime import datetime, timedelta
from functools import wraps

review_bp = Blueprint('review', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is None:
            flash('Login required.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@review_bp.route('/')
@login_required
def review_mode():
    user_id = session.get('user_id')
    if not user_id:
        flash('User not logged in.', 'error')
        return redirect(url_for('auth.login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()
    cursor.execute("""
        SELECT q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, q.option_e, q.correct_answer, q.question_id
        FROM questions q
        JOIN sm2_data sm ON q.question_id = sm.question_id
        WHERE sm.user_id = ? AND sm.next_practice_date <= ?
        ORDER BY sm.next_practice_date
        LIMIT 1
    """, (user_id, now))
    question = cursor.fetchone()
    conn.close()
    return render_template('review/review.html', question=question)

@review_bp.route('/submit_review', methods=['POST'])
@login_required
def submit_review():
    user_id = session.get('user_id')
    data = request.get_json()
    question_id = data.get('question_id')
    difficulty = data.get('difficulty')
    if not user_id or not question_id or not difficulty:
        return jsonify({'error': 'Invalid request'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sm2_data WHERE user_id = ? AND question_id = ?', (user_id, question_id))
    sm2_item = cursor.fetchone()
    if not sm2_item:
        conn.close()
        return jsonify({'error': 'SM-2 data not found'}), 404
    easiness_factor = sm2_item['easiness_factor']
    interval = sm2_item['interval']
    repetitions = sm2_item['repetitions']
    if difficulty == 'easy':
        quality_response = 5
    elif difficulty == 'medium':
        quality_response = 4
    elif difficulty == 'hard':
        quality_response = 3
    elif difficulty == 'wrong':
        quality_response = 0
    else:
        quality_response = 0
    if quality_response >= 3:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = round(interval * easiness_factor)
        repetitions += 1
    else:
        repetitions = 0
        interval = 1
    easiness_factor = easiness_factor + (0.1 - (5 - quality_response) * (0.08 + (5 - quality_response) * 0.02))
    if easiness_factor < 1.3:
        easiness_factor = 1.3
    next_practice_date = datetime.now() + timedelta(days=interval)
    cursor.execute("""
        UPDATE sm2_data
        SET easiness_factor = ?, interval = ?, repetitions = ?, next_practice_date = ?
        WHERE user_id = ? AND question_id = ?
    """, (easiness_factor, interval, repetitions, next_practice_date, user_id, question_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})