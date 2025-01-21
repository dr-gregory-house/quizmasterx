# review/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from utils import get_db_connection, get_review_questions_count, get_next_review_question
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
        return redirect(url_for('auth.login'))

    now = datetime.now()
    
    # Get count of questions due for review
    count = get_review_questions_count(user_id)
    if count == 0:
        flash('No questions are due for review at this time.', 'info')
        return redirect(url_for('main.index'))

    # Get the next question due for review
    question = get_next_review_question(user_id)
    if not question:
        flash('No questions available for review at this time.', 'info')
        return redirect(url_for('main.index'))

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
    interval_minutes = sm2_item['interval']
    repetitions = sm2_item['repetitions']
    if difficulty == 'easy':
        quality_response = 5
        interval_minutes = 15  # Show after 15 minutes
    elif difficulty == 'medium':
        quality_response = 4
        interval_minutes = 7   # Show after 7 minutes
    elif difficulty == 'hard':
        quality_response = 3
        interval_minutes = 1   # Show after 1 minute
    elif difficulty == 'wrong':
        quality_response = 0
        interval_minutes = 1   # Show after 1 minute
    else:
        quality_response = 0
        interval_minutes = 1   # Default to 1 minute

    # We'll keep track of repetitions but won't use them for intervals
    if quality_response >= 3:
        repetitions += 1
    else:
        repetitions = 0

    easiness_factor = easiness_factor + (0.1 - (5 - quality_response) * (0.08 + (5 - quality_response) * 0.02))
    if easiness_factor < 1.3:
        easiness_factor = 1.3
        
    next_practice_date = datetime.now() + timedelta(minutes=interval_minutes)  # Use minutes instead of days
    cursor.execute("""
        UPDATE sm2_data
        SET easiness_factor = ?, interval = ?, repetitions = ?, next_practice_date = ?
        WHERE user_id = ? AND question_id = ?
    """, (easiness_factor, interval_minutes, repetitions, next_practice_date, user_id, question_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})