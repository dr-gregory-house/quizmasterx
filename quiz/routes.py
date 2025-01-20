# quiz/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from utils import get_db_connection
from datetime import datetime, timedelta
import json

quiz_bp = Blueprint('quiz', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is None:
            flash('Login required.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@quiz_bp.route('/topic_select')
@login_required
def topic_select():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT topic FROM questions WHERE topic IS NOT NULL AND topic != ''")
    topics = [row['topic'] for row in cursor.fetchall()]
    conn.close()
    return render_template('quiz/topic_select.html', topics=topics)

@quiz_bp.route('/start_topic_quiz', methods=['POST'])
@login_required
def start_topic_quiz():
    selected_topics = request.form.getlist('topics')
    question_option = request.form.get('question_option', 'custom')
    num_questions = None if question_option == 'all' else int(request.form.get('num_questions', 10))

    if not selected_topics:
        flash('Please select at least one topic', 'warning')
        return redirect(url_for('quiz.topic_select'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Create temporary quiz session table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_sessions (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER,
            questions TEXT,
            current_index INTEGER,
            correct_answers INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # First, get the total number of available questions for the selected topics
    if 'all' in selected_topics:
        cursor.execute('SELECT COUNT(*) as count FROM questions WHERE flagged != ?', ('yes',))
    else:
        placeholders = ','.join('?' * len(selected_topics))
        cursor.execute(f'SELECT COUNT(*) as count FROM questions WHERE topic IN ({placeholders}) AND flagged != ?', 
                      (*selected_topics, 'yes'))
    
    total_available = cursor.fetchone()['count']

    # If all questions are requested or if num_questions is greater than available, use all available questions
    if question_option == 'all' or (num_questions and num_questions > total_available):
        num_questions = total_available

    # Now get the actual questions
    if 'all' in selected_topics:
        cursor.execute('SELECT question_id, correct_answer FROM questions WHERE flagged != ? ORDER BY RANDOM() LIMIT ?', 
                      ('yes', num_questions))
    else:
        placeholders = ','.join('?' * len(selected_topics))
        query = f'SELECT question_id, correct_answer FROM questions WHERE topic IN ({placeholders}) AND flagged != ? ORDER BY RANDOM() LIMIT ?'
        cursor.execute(query, (*selected_topics, 'yes', num_questions))

    questions = [dict(row) for row in cursor.fetchall()]
    
    if not questions:
        conn.close()
        flash(f"No questions found for the selected topics", 'info')
        return redirect(url_for('quiz.topic_select'))

    # Generate a unique session ID for this quiz
    quiz_session_id = f"quiz_{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Store quiz data in the temporary table
    cursor.execute("""
        INSERT INTO quiz_sessions (session_id, user_id, questions, current_index, correct_answers)
        VALUES (?, ?, ?, ?, ?)
    """, (quiz_session_id, session['user_id'], json.dumps([q['question_id'] for q in questions]), 0, 0))
    
    # Store only the session ID in the user session
    session['quiz_session_id'] = quiz_session_id
    
    # Get the first question's full data
    first_question_id = questions[0]['question_id']
    cursor.execute('SELECT * FROM questions WHERE question_id = ?', (first_question_id,))
    first_question = cursor.execute('SELECT * FROM questions WHERE question_id = ?', (first_question_id,)).fetchone()
    
    conn.commit()
    conn.close()

    return render_template('quiz/quiz_question.html', 
                         question=first_question,
                         next_question_url=url_for('quiz.next_question'),
                         current_question=1,
                         total_questions=len(questions))

@quiz_bp.route('/next_question', methods=['POST'])
@login_required
def next_question():
    selected_answer = request.form.get('selected_answer')
    quiz_session_id = session.get('quiz_session_id')
    
    print(f"\n=== NEXT QUESTION DEBUG ===")
    print(f"Selected Answer: {selected_answer}")
    print(f"Quiz Session ID: {quiz_session_id}")
    
    if not quiz_session_id:
        print("Error: Invalid quiz state.")
        flash("Error: Invalid quiz state.", "error")
        return redirect(url_for('main.hello'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get quiz session data
    cursor.execute('SELECT * FROM quiz_sessions WHERE session_id = ?', (quiz_session_id,))
    quiz_session = cursor.fetchone()
    
    if not quiz_session:
        print("Error: Quiz session not found.")
        conn.close()
        flash("Error: Quiz session not found.", "error")
        return redirect(url_for('main.hello'))
    
    questions = json.loads(quiz_session['questions'])
    current_index = quiz_session['current_index']
    correct_answers = quiz_session['correct_answers']
    user_id = quiz_session['user_id']
    
    # Check current answer if provided
    if selected_answer:
        cursor.execute('SELECT correct_answer FROM questions WHERE question_id = ?', (questions[current_index],))
        question = cursor.fetchone()
        is_correct = False
        if question and selected_answer.lower() == question['correct_answer'].lower():
            correct_answers += 1
            is_correct = True
            cursor.execute('UPDATE quiz_sessions SET correct_answers = ? WHERE session_id = ?', 
                         (correct_answers, quiz_session_id))
        
        if not is_correct:
            print(f"\nIncorrect answer for question {questions[current_index]} - updating SM2 data")
            now = datetime.now()
            next_practice = now + timedelta(minutes=1)
            print(f"Setting next practice date to: {next_practice}")
            
            # Update SM2 data for wrong answers
            cursor.execute("""
                INSERT INTO sm2_data 
                (user_id, question_id, easiness_factor, repetitions, interval, next_practice_date) 
                VALUES (?, ?, 2.5, 0, 1, ?)
                ON CONFLICT(user_id, question_id) DO UPDATE SET
                    easiness_factor = 2.5,
                    repetitions = 0,
                    interval = 1,
                    next_practice_date = ?
            """, (user_id, questions[current_index], next_practice, next_practice))
            
            # Verify SM2 data
            cursor.execute("SELECT * FROM sm2_data WHERE user_id = ? AND question_id = ?", 
                         (user_id, questions[current_index]))
            sm2_data = cursor.fetchone()
            if sm2_data:
                print("\nSM2 data after update:")
                print(f"Next Practice Date: {sm2_data['next_practice_date']}")
                print(f"Interval: {sm2_data['interval']}")
                print(f"Repetitions: {sm2_data['repetitions']}")
            else:
                print("Warning: SM2 data not found after insert/update")
    
    # Move to next question
    current_index += 1
    cursor.execute('UPDATE quiz_sessions SET current_index = ? WHERE session_id = ?', 
                  (current_index, quiz_session_id))
    
    if current_index < len(questions):
        # Get next question data
        cursor.execute('SELECT * FROM questions WHERE question_id = ?', (questions[current_index],))
        next_question_data = cursor.fetchone()
        conn.commit()
        conn.close()
        print("=== END NEXT QUESTION DEBUG ===\n")
        return render_template('quiz/quiz_question.html', 
                             question=next_question_data,
                             next_question_url=url_for('quiz.next_question'),
                             current_question=current_index + 1,
                             total_questions=len(questions))
    else:
        # Quiz completed, clean up
        cursor.execute('DELETE FROM quiz_sessions WHERE session_id = ?', (quiz_session_id,))
        conn.commit()
        conn.close()
        print("=== END NEXT QUESTION DEBUG ===\n")
        return redirect(url_for('quiz.quiz_results', score=correct_answers, total=len(questions)))

@quiz_bp.route('/quiz_results')
@login_required
def quiz_results():
    score = request.args.get('score', 0, type=int)
    total = request.args.get('total', 0, type=int)
    return render_template('quiz/quiz_results.html', score=score, total=total)

@quiz_bp.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    return redirect(url_for('quiz.next_question'))

@quiz_bp.route('/check_answer', methods=['POST'])
@login_required
def check_answer():
    data = request.get_json()
    question_id = data.get('question_id')
    selected_answer = data.get('selected_answer')
    user_id = session.get('user_id')
    
    print(f"\n=== CHECK ANSWER DEBUG ===")
    print(f"User ID: {user_id}")
    print(f"Question ID: {question_id}")
    print(f"Selected Answer: {selected_answer}")
    
    if not question_id or not selected_answer or not user_id:
        print("Invalid request - missing data")
        return jsonify({'error': 'Invalid request'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    question = cursor.execute('SELECT correct_answer FROM questions WHERE question_id = ?', (question_id,)).fetchone()
    
    if not question:
        print("Question not found in database")
        conn.close()
        return jsonify({'error': 'Question not found'}), 404

    correct_answer = question['correct_answer'].lower()
    is_correct = selected_answer.lower() == correct_answer
    print(f"Correct Answer: {correct_answer}")
    print(f"Is Answer Correct: {is_correct}")

    if not is_correct:
        now = datetime.now()
        print("\nAnswer is incorrect - updating SM2 data")
        
        # Update performance tracking
        cursor.execute("""
            INSERT INTO user_question_performance (user_id, question_id, incorrect_attempts, last_attempt_date)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(user_id, question_id) DO UPDATE SET
                incorrect_attempts = incorrect_attempts + 1,
                last_attempt_date = ?
        """, (user_id, question_id, now, now))

        # Initialize or update SM-2 parameters
        next_practice = now + timedelta(minutes=1)  # Start with 1-minute interval for wrong answers
        print(f"Setting next practice date to: {next_practice}")
        
        cursor.execute("""
            INSERT INTO sm2_data 
            (user_id, question_id, easiness_factor, repetitions, interval, next_practice_date) 
            VALUES (?, ?, 2.5, 0, 1, ?)
            ON CONFLICT(user_id, question_id) DO UPDATE SET
                easiness_factor = 2.5,
                repetitions = 0,
                interval = 1,
                next_practice_date = ?
        """, (user_id, question_id, next_practice, next_practice))
        
        # Verify the data was inserted/updated
        cursor.execute("SELECT * FROM sm2_data WHERE user_id = ? AND question_id = ?", (user_id, question_id))
        sm2_data = cursor.fetchone()
        if sm2_data:
            print("\nSM2 data after update:")
            print(f"Next Practice Date: {sm2_data['next_practice_date']}")
            print(f"Interval: {sm2_data['interval']}")
            print(f"Repetitions: {sm2_data['repetitions']}")
        else:
            print("Warning: SM2 data not found after insert/update")

    conn.commit()
    conn.close()
    print("=== END CHECK ANSWER DEBUG ===\n")
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