from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from utils import get_db_connection
from functools import wraps
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_role') == 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/admin')
@admin_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all guest sessions with their current status
    all_guests = cursor.execute('''
        SELECT 
            guest_id,
            display_name,
            ip_address,
            start_time,
            end_time,
            last_activity,
            CASE 
                WHEN end_time IS NULL 
                AND last_activity > datetime('now', '-30 minutes') THEN 'active'
                WHEN end_time IS NOT NULL THEN 'logged_out'
                ELSE 'inactive'
            END as status,
            CASE 
                WHEN end_time IS NOT NULL THEN 
                    ROUND((julianday(end_time) - julianday(start_time)) * 24 * 60, 1)
                ELSE 
                    ROUND((julianday(COALESCE(last_activity, start_time)) - julianday(start_time)) * 24 * 60, 1)
            END as duration_minutes,
            (
                SELECT COUNT(*) 
                FROM quiz_attempts 
                WHERE user_id = guest_sessions.guest_id
            ) as total_attempts,
            (
                SELECT COALESCE(SUM(score), 0)
                FROM quiz_attempts 
                WHERE user_id = guest_sessions.guest_id
            ) as total_score
        FROM guest_sessions 
        ORDER BY 
            CASE 
                WHEN end_time IS NULL AND last_activity > datetime('now', '-30 minutes') THEN 0
                WHEN end_time IS NULL THEN 1
                ELSE 2
            END,
            last_activity DESC
    ''').fetchall()
    
    # Calculate statistics
    stats = {
        'total_guests': len(all_guests),
        'active_guests': sum(1 for guest in all_guests if guest['status'] == 'active'),
        'avg_session_duration': cursor.execute('''
            SELECT ROUND(AVG(
                CASE 
                    WHEN end_time IS NOT NULL THEN 
                        (julianday(end_time) - julianday(start_time)) * 24 * 60
                    ELSE 
                        (julianday(last_activity) - julianday(start_time)) * 24 * 60
                END
            ), 1)
            FROM guest_sessions 
            WHERE end_time IS NOT NULL 
            OR last_activity < datetime('now', '-30 minutes')
        ''').fetchone()[0],
        'total_quiz_attempts': cursor.execute('SELECT COUNT(*) FROM quiz_attempts').fetchone()[0]
    }
    
    conn.close()
    
    return render_template('admin/dashboard.html', 
                         guests=all_guests,
                         stats=stats)

@admin_bp.route('/admin/guest/<guest_id>')
@admin_required
def guest_details(guest_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get guest session details
    guest_session = cursor.execute('''
        SELECT * FROM guest_sessions 
        WHERE guest_id = ?
        ORDER BY start_time DESC
        LIMIT 1
    ''', (guest_id,)).fetchone()
    
    if not guest_session:
        flash('Guest session not found.', 'error')
        return redirect(url_for('admin.dashboard'))
    
    # Get quiz attempts for this guest
    quiz_attempts = cursor.execute('''
        SELECT 
            qa.attempt_id,
            qa.quiz_mode,
            qa.start_time,
            qa.end_time,
            qa.score,
            qa.total_questions,
            COUNT(qr.question_id) as questions_answered,
            SUM(CASE WHEN qr.is_correct = 1 THEN 1 ELSE 0 END) as correct_answers
        FROM quiz_attempts qa
        LEFT JOIN quiz_responses qr ON qa.attempt_id = qr.attempt_id
        WHERE qa.user_id = ?
        GROUP BY qa.attempt_id
        ORDER BY qa.start_time DESC
    ''', (guest_id,)).fetchall()
    
    # Get detailed question responses for each attempt
    attempts_details = {}
    for attempt in quiz_attempts:
        questions = cursor.execute('''
            SELECT 
                q.question_text,
                qr.selected_option,
                qr.is_correct,
                q.correct_option,
                qr.response_time
            FROM quiz_responses qr
            JOIN questions q ON qr.question_id = q.question_id
            WHERE qr.attempt_id = ?
            ORDER BY qr.response_time
        ''', (attempt['attempt_id'],)).fetchall()
        attempts_details[attempt['attempt_id']] = questions
    
    conn.close()
    
    return render_template('admin/guest_details.html', 
                         guest=guest_session,
                         attempts=quiz_attempts,
                         attempts_details=attempts_details)