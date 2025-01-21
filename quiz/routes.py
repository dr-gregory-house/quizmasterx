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
    
    if not quiz_session_id:
        flash('Invalid quiz state.', 'error')
        return redirect(url_for('quiz.start_quiz'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get quiz session data
    cursor.execute('SELECT * FROM quiz_sessions WHERE session_id = ?', (quiz_session_id,))
    quiz_session = cursor.fetchone()
    
    if not quiz_session:
        flash('Quiz session not found.', 'error')
        conn.close()
        return redirect(url_for('quiz.start_quiz'))
    
    questions = json.loads(quiz_session['questions'])
    current_index = quiz_session['current_index']
    correct_answers = quiz_session['correct_answers']
    user_id = quiz_session['user_id']
    
    # Process the answer for the current question
    if selected_answer:
        cursor.execute('SELECT correct_answer FROM questions WHERE question_id = ?', (questions[current_index],))
        question = cursor.fetchone()
        correct_answer = question['correct_answer'].lower()
        is_correct = selected_answer.lower() == correct_answer

        if is_correct:
            correct_answers += 1
            cursor.execute('UPDATE quiz_sessions SET correct_answers = ? WHERE session_id = ?', 
                         (correct_answers, quiz_session_id))
        else:
            # Update SM2 data for incorrect answers
            now = datetime.now()
            next_practice = now + timedelta(minutes=1)
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
        
        # Update statistics
        try:
            cursor.execute("""
                INSERT INTO user_topic_stats (user_id, topic, total_questions, correct_answers, last_attempt_date)
                VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, topic) DO UPDATE SET
                    total_questions = total_questions + 1,
                    correct_answers = CASE WHEN ? THEN correct_answers + 1 ELSE correct_answers END,
                    last_attempt_date = CURRENT_TIMESTAMP
            """, (user_id, question['topic'], 1 if is_correct else 0, is_correct))

            # Update weakness score
            if not is_correct:
                cursor.execute("""
                    INSERT INTO user_weak_topics (user_id, topic, weakness_score, last_updated)
                    VALUES (?, ?, 0.8, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, topic) DO UPDATE SET
                        weakness_score = MIN(1.0, (user_weak_topics.weakness_score + 0.1)),
                        last_updated = CURRENT_TIMESTAMP
                """, (user_id, question['topic']))
            else:
                cursor.execute("""
                    INSERT INTO user_weak_topics (user_id, topic, weakness_score, last_updated)
                    VALUES (?, ?, 0.4, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, topic) DO UPDATE SET
                        weakness_score = MAX(0.0, (user_weak_topics.weakness_score - 0.05)),
                        last_updated = CURRENT_TIMESTAMP
                """, (user_id, question['topic']))

            # Update daily statistics
            today = datetime.now().date()
            cursor.execute("""
                INSERT INTO user_daily_stats (user_id, date, questions_attempted, questions_correct)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(user_id, date) DO UPDATE SET
                    questions_attempted = questions_attempted + 1,
                    questions_correct = CASE WHEN ? THEN questions_correct + 1 ELSE questions_correct END
            """, (user_id, today, 1 if is_correct else 0, is_correct))

            cursor.execute('UPDATE quiz_sessions SET current_index = ? WHERE session_id = ?', 
                          (current_index + 1, quiz_session_id))
        except Exception as e:
            flash('An error occurred while updating statistics.', 'error')

    # Move to next question
    current_index += 1
    
    # Update quiz session
    cursor.execute('UPDATE quiz_sessions SET current_index = ? WHERE session_id = ?', 
                  (current_index, quiz_session_id))
    
    # Check if quiz is complete
    if current_index >= len(questions):
        cursor.execute('DELETE FROM quiz_sessions WHERE session_id = ?', (quiz_session_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('quiz.quiz_results', score=correct_answers, total=len(questions)))

    # Get next question data
    cursor.execute('SELECT * FROM questions WHERE question_id = ?', (questions[current_index],))
    next_question_data = cursor.fetchone()
    conn.commit()
    conn.close()

    return render_template('quiz/quiz_question.html', 
                         question=next_question_data,
                         next_question_url=url_for('quiz.next_question'),
                         current_question=current_index + 1,
                         total_questions=len(questions))

@quiz_bp.route('/quiz_results')
@login_required
def quiz_results():
    score = request.args.get('score', 0, type=int)
    total = request.args.get('total', 0, type=int)
    topics = request.args.get('topics', '', type=str).split(',')
    time_taken = request.args.get('time_taken', 0, type=int)
    user_id = session.get('user_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Update quiz history
        for topic in topics:
            if topic.strip():  # Only process non-empty topics
                cursor.execute("""
                    INSERT INTO user_quiz_history 
                    (user_id, quiz_date, topic, score, total_questions, time_taken)
                    VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
                """, (user_id, topic, score, total, time_taken))

        # Update daily stats
        today = datetime.now().date()
        cursor.execute("""
            INSERT INTO user_daily_stats (user_id, date, questions_attempted, questions_correct)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                questions_attempted = questions_attempted + ?,
                questions_correct = questions_correct + ?
        """, (user_id, today, total, score, total, score))

        conn.commit()
    except Exception as e:
        print(f"Error updating statistics: {e}")
    finally:
        conn.close()

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
    
    if not question_id or not selected_answer or not user_id:
        return jsonify({'error': 'Invalid request'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get question details including topic
    cursor.execute('SELECT correct_answer, topic FROM questions WHERE question_id = ?', (question_id,))
    question = cursor.fetchone()
    
    if not question:
        conn.close()
        return jsonify({'error': 'Question not found'}), 404

    correct_answer = question['correct_answer'].lower()
    is_correct = selected_answer.lower() == correct_answer
    topic = question['topic']

    try:
        # Update topic statistics
        cursor.execute("""
            INSERT INTO user_topic_stats (user_id, topic, total_questions, correct_answers, last_attempt_date)
            VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, topic) DO UPDATE SET
                total_questions = total_questions + 1,
                correct_answers = CASE WHEN ? THEN correct_answers + 1 ELSE correct_answers END,
                last_attempt_date = CURRENT_TIMESTAMP
        """, (user_id, topic, 1 if is_correct else 0, is_correct))

        # Update weakness score
        if not is_correct:
            cursor.execute("""
                INSERT INTO user_weak_topics (user_id, topic, weakness_score, last_updated)
                VALUES (?, ?, 0.8, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, topic) DO UPDATE SET
                    weakness_score = MIN(1.0, (user_weak_topics.weakness_score + 0.1)),
                    last_updated = CURRENT_TIMESTAMP
            """, (user_id, topic))
        else:
            cursor.execute("""
                INSERT INTO user_weak_topics (user_id, topic, weakness_score, last_updated)
                VALUES (?, ?, 0.4, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, topic) DO UPDATE SET
                    weakness_score = MAX(0.0, (user_weak_topics.weakness_score - 0.05)),
                    last_updated = CURRENT_TIMESTAMP
            """, (user_id, topic))

        # Update daily statistics
        today = datetime.now().date()
        cursor.execute("""
            INSERT INTO user_daily_stats (user_id, date, questions_attempted, questions_correct)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                questions_attempted = questions_attempted + 1,
                questions_correct = CASE WHEN ? THEN questions_correct + 1 ELSE questions_correct END
        """, (user_id, today, 1 if is_correct else 0, is_correct))

        if not is_correct:
            # Update SM2 data for wrong answers
            next_practice = datetime.now() + timedelta(minutes=1)
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

        conn.commit()
    except Exception as e:
        print(f"Error updating statistics: {e}")
        conn.rollback()
    finally:
        conn.close()

    return jsonify({
        'is_correct': is_correct,
        'correct_answer': correct_answer
    })

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