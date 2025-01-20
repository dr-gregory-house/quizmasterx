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
    print(f"\n=== REVIEW MODE DEBUG ===")
    print(f"User ID: {user_id}")
    
    if not user_id:
        print("No user_id found in session")
        flash('User not logged in.', 'error')
        return redirect(url_for('auth.login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()
    print(f"Current time: {now}")
    
    # First check if there are any questions to review
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM sm2_data sm
        WHERE sm.user_id = ? AND sm.next_practice_date <= ?
    """, (user_id, now))
    count = cursor.fetchone()['count']
    print(f"Number of questions due for review: {count}")
    
    if count == 0:
        print("No questions found for review")
        conn.close()
        return render_template('review/review.html', message="No questions to review at this time. Questions will appear here after you answer them in Quiz mode.")
    
    # Debug: Let's see what's in sm2_data for this user
    cursor.execute("""
        SELECT question_id, next_practice_date, interval
        FROM sm2_data
        WHERE user_id = ?
    """, (user_id,))
    sm2_entries = cursor.fetchall()
    print("\nAll SM2 entries for user:")
    for entry in sm2_entries:
        print(f"Question ID: {entry['question_id']}, Next Practice: {entry['next_practice_date']}, Interval: {entry['interval']}")
        
    cursor.execute("""
        SELECT q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, q.option_e, q.correct_answer, q.question_id,
               sm.next_practice_date
        FROM questions q
        JOIN sm2_data sm ON q.question_id = sm.question_id
        WHERE sm.user_id = ? AND sm.next_practice_date <= ?
        ORDER BY sm.next_practice_date
        LIMIT 1
    """, (user_id, now))
    question = cursor.fetchone()
    print("\nRetrieved question:")
    if question:
        print(f"Question ID: {question['question_id']}")
        print(f"Question Text: {question['question_text']}")
        print(f"Next Practice Date: {question['next_practice_date']}")
    else:
        print("No question retrieved")
    
    conn.close()
    print("=== END REVIEW MODE DEBUG ===\n")
    
    if not question:
        return render_template('review/review.html', message="No questions available for review at this moment.")
        
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