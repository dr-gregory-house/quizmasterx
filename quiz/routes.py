# quiz/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from utils import get_db_connection
from datetime import datetime, timedelta

quiz_bp = Blueprint('quiz', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is None:
            flash('Login required.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@quiz_bp.route('/hardcore')
@login_required
def hardcore_mode_select():
    return render_template('quiz/hardcore_quiz.html')

@quiz_bp.route('/start_hardcore_quiz', methods=['POST'])
@login_required
def start_hardcore_quiz():
    num_questions = int(request.form['num_questions'])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM questions WHERE flagged != ? ORDER BY RANDOM() LIMIT ?', ('yes', num_questions))
    questions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    session['quiz_questions'] = [(
        q['question_id'],
        q['correct_answer'],
        q['question_text'],
        q['option_a'],
        q['option_b'],
        q['option_c'],
        q['option_d'],
        q.get('option_e')
    ) for q in questions]
    session['current_question_index'] = 0
    session['correct_answers'] = 0
    next_question_url = url_for('quiz.next_question')  # Generate the URL
        
    return render_template('quiz/quiz_question.html', question=questions[0], next_question_url=next_question_url)
    return "Not enough questions available."
@quiz_bp.route('/next_question', methods=['POST'])
@login_required
def next_question():
    selected_answer = request.form.get('selected_answer')
    current_index = session.get('current_question_index')
    quiz_data = session.get('quiz_questions')
    if not quiz_data or current_index is None or current_index >= len(quiz_data):
        flash("Error: Invalid quiz state.", "error")
        return redirect(url_for('main.hello'))
    correct_answer_db = quiz_data[current_index][1].lower()
    if selected_answer and selected_answer.lower() == correct_answer_db.lower():
        session['correct_answers'] += 1
    session['current_question_index'] += 1
    current_index = session['current_question_index']
    if current_index < len(quiz_data):
        next_question_id = quiz_data[current_index][0]
        conn = get_db_connection()
        cursor = conn.cursor()
        next_question_data = cursor.execute('SELECT * FROM questions WHERE question_id = ?', (next_question_id,)).fetchone()
        conn.close()
        return render_template('quiz/quiz_question.html', question=next_question_data)
    else:
        return redirect(url_for('quiz.quiz_results'))

@quiz_bp.route('/quiz_results')
@login_required
def quiz_results():
    return render_template('quiz/quiz_results.html', score=session.get('correct_answers', 0), total_questions=len(session.get('quiz_questions', [])))

@quiz_bp.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    return redirect(url_for('quiz.next_question'))

@quiz_bp.route('/marathon')
@login_required
def marathon_mode():
    if 'marathon_start_time' not in session:
        session['marathon_start_time'] = datetime.now().timestamp()
        session['current_marathon_question'] = None
        session.modified = True  # Ensure session is saved
    
    if session.get('current_marathon_question') is None:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM questions WHERE flagged != ? ORDER BY RANDOM() LIMIT 1', ('yes',))
        question = cursor.fetchone()
        conn.close()
        
        if question:
            # Convert SQLite row to dictionary and store in session
            question_dict = {
                'question_id': question['question_id'],
                'question_text': question['question_text'],
                'option_a': question['option_a'],
                'option_b': question['option_b'],
                'option_c': question['option_c'],
                'option_d': question['option_d'],
                'option_e': question['option_e'] if 'option_e' in question.keys() else None,
                'correct_answer': question['correct_answer']
            }
            session['current_marathon_question'] = question_dict
            session.modified = True  # Ensure session is saved
        else:
            return "No unflagged questions available."
    
    return render_template('quiz/marathon.html', question=session['current_marathon_question'])

@quiz_bp.route('/marathon_time_left')
@login_required
def marathon_time_left():
    start_time = session.get('marathon_start_time')
    if start_time:
        elapsed_time = datetime.now().timestamp() - float(start_time)
        time_left = max(0, 900 - elapsed_time)
        return jsonify({'time_left': time_left})
    return jsonify({'time_left': 900})

@quiz_bp.route('/marathon_next_question')
@login_required
def marathon_next_question():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM questions WHERE flagged != ? ORDER BY RANDOM() LIMIT 1', ('yes',))
    question = cursor.fetchone()
    conn.close()
    
    if question:
        # Convert SQLite row to dictionary and store in session
        question_dict = {
            'question_id': question['question_id'],
            'question_text': question['question_text'],
            'option_a': question['option_a'],
            'option_b': question['option_b'],
            'option_c': question['option_c'],
            'option_d': question['option_d'],
            'option_e': question['option_e'] if 'option_e' in question.keys() else None,
            'correct_answer': question['correct_answer']
        }
        session['current_marathon_question'] = question_dict
        session.modified = True  # Ensure session is saved
        
        question_html = render_template('quiz/_marathon_question.html', question=question_dict)
        return jsonify({'question_html': question_html, 'question_id': question_dict['question_id']})
    return jsonify({'question_html': None})

@quiz_bp.route('/check_answer', methods=['POST'])
@login_required
def check_answer():
    data = request.get_json()
    question_id = data.get('question_id')
    selected_answer = data.get('selected_answer')
    user_id = session.get('user_id')
    if not question_id or not selected_answer or not user_id:
        return jsonify({'error': 'Invalid request'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    question = cursor.execute('SELECT correct_answer FROM questions WHERE question_id = ?', (question_id,)).fetchone()
    if not question:
        conn.close()
        return jsonify({'error': 'Question not found'}), 404
    correct_answer = question['correct_answer'].lower()
    is_correct = selected_answer.lower() == correct_answer
    if not is_correct:
        now = datetime.now()
        cursor.execute("""
            INSERT INTO user_question_performance (user_id, question_id, incorrect_attempts, last_attempt_date)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(user_id, question_id) DO UPDATE SET
                incorrect_attempts = incorrect_attempts + 1,
                last_attempt_date = ?
        """, (user_id, question_id, now, now))
        cursor.execute("""
            INSERT OR IGNORE INTO sm2_data (user_id, question_id, next_practice_date)
            VALUES (?, ?, ?)
        """, (user_id, question_id, now))
    conn.commit()
    conn.close()
    return jsonify({'is_correct': is_correct, 'correct_answer': correct_answer})

@quiz_bp.route('/question/<int:question_id>')
@login_required
def display_question(question_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    question = cursor.execute('SELECT * FROM questions WHERE question_id = ? AND flagged != ?', (question_id, 'yes')).fetchone()
    conn.close()
    if question:
        return render_template('quiz/question.html', question=question)
    return "Question not found or is flagged"

@quiz_bp.route('/marathon_results')
@login_required
def marathon_results():
    score = request.args.get('score', 0)
    return render_template('quiz/marathon_results.html', score=score)