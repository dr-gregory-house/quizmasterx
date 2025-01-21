from flask import Blueprint, render_template, session, jsonify, request, flash, redirect, url_for
from functools import wraps
from utils import get_db_connection
from datetime import datetime, timedelta
import json

stats_bp = Blueprint('stats', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is None:
            flash('Login required.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_role') != 'admin':
            flash('Admin access required.', 'warning')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def calculate_average(values):
    if not values:
        return 0
    return sum(values) / len(values)

@stats_bp.route('/my_statistics')
@login_required
def my_statistics():
    user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get user's topic statistics
    cursor.execute('''
        SELECT 
            topic,
            COUNT(*) as total_questions,
            SUM(CASE WHEN score = total_questions THEN 1 ELSE 0 END) as correct_answers,
            AVG(CAST(score AS FLOAT) / total_questions * 100) as accuracy
        FROM user_quiz_history
        WHERE user_id = ?
        GROUP BY topic
    ''', (user_id,))
    topic_stats = cursor.fetchall()

    # Calculate average accuracy
    total_correct = sum(stat['correct_answers'] for stat in topic_stats)
    total_questions = sum(stat['total_questions'] for stat in topic_stats)
    avg_accuracy = round((total_correct / total_questions * 100) if total_questions > 0 else 0, 1)

    # Get user's weak topics
    cursor.execute('''
        SELECT topic, weakness_score
        FROM user_weak_topics
        WHERE user_id = ?
        ORDER BY weakness_score DESC
        LIMIT 5
    ''', (user_id,))
    weak_topics = cursor.fetchall()

    # Get recent quiz history
    cursor.execute('''
        SELECT 
            quiz_date,
            topic,
            score,
            total_questions,
            time_taken,
            CAST(score AS FLOAT) / total_questions * 100 as score_percentage
        FROM user_quiz_history
        WHERE user_id = ?
        ORDER BY quiz_date DESC
        LIMIT 20
    ''', (user_id,))
    recent_quizzes = cursor.fetchall()

    # Get daily statistics
    cursor.execute('''
        SELECT 
            date,
            questions_attempted,
            questions_correct
        FROM user_daily_stats
        WHERE user_id = ?
        AND date >= date('now', '-30 days')
        ORDER BY date
    ''', (user_id,))
    daily_stats = cursor.fetchall()

    conn.close()

    return render_template('stats/my_statistics.html',
                         topic_stats=topic_stats,
                         avg_accuracy=avg_accuracy,
                         weak_topics=weak_topics,
                         recent_quizzes=recent_quizzes,
                         daily_stats=daily_stats)

@stats_bp.route('/admin/user_statistics/<int:target_user_id>')
@login_required
def admin_user_statistics(target_user_id):
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get user info
    cursor.execute("SELECT username FROM users WHERE id = ?", (target_user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    # Get comprehensive user statistics
    cursor.execute("""
        SELECT topic, total_questions, correct_answers,
               CASE 
                   WHEN total_questions > 0 
                   THEN ROUND(CAST(correct_answers AS FLOAT) / total_questions * 100, 2)
                   ELSE 0 
               END as accuracy
        FROM user_topic_stats
        WHERE user_id = ?
        ORDER BY accuracy DESC
    """, (target_user_id,))
    topic_stats = cursor.fetchall()
    
    # Calculate average accuracy
    accuracies = [stat['accuracy'] for stat in topic_stats]
    avg_accuracy = round(calculate_average(accuracies), 1) if accuracies else 0

    # Get weak topics
    cursor.execute("""
        SELECT topic, weakness_score
        FROM user_weak_topics
        WHERE user_id = ?
        ORDER BY weakness_score ASC
    """, (target_user_id,))
    weak_topics = cursor.fetchall()

    # Get all quiz history with proper date formatting
    cursor.execute("""
        SELECT strftime('%Y-%m-%d %H:%M', quiz_date) as quiz_date,
               topic, score, total_questions, time_taken
        FROM user_quiz_history
        WHERE user_id = ?
        ORDER BY quiz_date DESC
    """, (target_user_id,))
    quiz_history = cursor.fetchall()

    # Get daily activity for the last 30 days with proper date formatting
    thirty_days_ago = datetime.now() - timedelta(days=30)
    cursor.execute("""
        SELECT strftime('%Y-%m-%d', date) as date,
               questions_attempted, questions_correct, study_time
        FROM user_daily_stats
        WHERE user_id = ? AND date >= ?
        ORDER BY date DESC
    """, (target_user_id, thirty_days_ago.date()))
    daily_stats = cursor.fetchall()

    conn.close()

    return render_template('stats/admin_user_statistics.html',
                         user=user,
                         topic_stats=topic_stats,
                         weak_topics=weak_topics,
                         quiz_history=quiz_history,
                         daily_stats=daily_stats,
                         avg_accuracy=avg_accuracy)

@stats_bp.route('/admin_statistics')
@login_required
@admin_required
def admin_statistics():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get total users and active users
    cursor.execute('SELECT COUNT(*) as total FROM users')
    total_users = cursor.fetchone()['total']
    
    cursor.execute('SELECT COUNT(*) as active FROM users WHERE is_active = 1')
    active_users = cursor.fetchone()['active']
    
    # Get users active today
    today = datetime.now().date()
    cursor.execute('''
        SELECT COUNT(DISTINCT user_id) as active_today 
        FROM user_daily_stats 
        WHERE date = ?
    ''', (today,))
    active_today = cursor.fetchone()['active_today']

    # Get total quizzes and average score
    cursor.execute('''
        SELECT COUNT(*) as total_quizzes,
               AVG(CAST(score AS FLOAT) / total_questions * 100) as avg_score
        FROM user_quiz_history
    ''')
    quiz_stats = cursor.fetchone()
    total_quizzes = quiz_stats['total_quizzes']
    avg_score = quiz_stats['avg_score'] or 0

    # Get score distribution
    cursor.execute('''
        SELECT 
            SUM(CASE WHEN (CAST(score AS FLOAT) / total_questions * 100) BETWEEN 0 AND 20 THEN 1 ELSE 0 END) as range_0_20,
            SUM(CASE WHEN (CAST(score AS FLOAT) / total_questions * 100) BETWEEN 21 AND 40 THEN 1 ELSE 0 END) as range_21_40,
            SUM(CASE WHEN (CAST(score AS FLOAT) / total_questions * 100) BETWEEN 41 AND 60 THEN 1 ELSE 0 END) as range_41_60,
            SUM(CASE WHEN (CAST(score AS FLOAT) / total_questions * 100) BETWEEN 61 AND 80 THEN 1 ELSE 0 END) as range_61_80,
            SUM(CASE WHEN (CAST(score AS FLOAT) / total_questions * 100) BETWEEN 81 AND 100 THEN 1 ELSE 0 END) as range_81_100
        FROM user_quiz_history
    ''')
    score_dist = cursor.fetchone()
    score_distribution = [
        score_dist['range_0_20'] or 0,
        score_dist['range_21_40'] or 0,
        score_dist['range_41_60'] or 0,
        score_dist['range_61_80'] or 0,
        score_dist['range_81_100'] or 0
    ]

    # Get daily statistics for the past 30 days
    cursor.execute('''
        SELECT 
            date,
            SUM(questions_attempted) as questions_attempted,
            SUM(questions_correct) as questions_correct,
            COUNT(DISTINCT user_id) as active_users,
            COUNT(*) as quiz_count
        FROM user_daily_stats
        WHERE date >= date('now', '-30 days')
        GROUP BY date
        ORDER BY date
    ''')
    daily_stats = cursor.fetchall()

    # Get topic statistics
    cursor.execute('''
        SELECT 
            topic,
            COUNT(*) as quiz_count,
            AVG(CAST(score AS FLOAT) / total_questions * 100) as avg_score
        FROM user_quiz_history
        GROUP BY topic
        ORDER BY quiz_count DESC
    ''')
    topic_stats = cursor.fetchall()

    # Get recent quiz history
    cursor.execute('''
        SELECT 
            h.quiz_date,
            u.username,
            h.topic,
            h.score,
            h.total_questions,
            h.time_taken,
            CAST(h.score AS FLOAT) / h.total_questions * 100 as score_percentage
        FROM user_quiz_history h
        JOIN users u ON h.user_id = u.user_id
        ORDER BY h.quiz_date DESC
        LIMIT 50
    ''')
    quiz_history = cursor.fetchall()

    # Get user performance overview
    cursor.execute('''
        SELECT 
            u.username,
            COUNT(*) as total_quizzes,
            AVG(CAST(h.score AS FLOAT) / h.total_questions * 100) as avg_score
        FROM users u
        JOIN user_quiz_history h ON u.user_id = h.user_id
        GROUP BY u.user_id, u.username
        ORDER BY avg_score DESC
        LIMIT 20
    ''')
    user_performance = cursor.fetchall()

    conn.close()

    return render_template('stats/admin_statistics.html',
                         total_users=total_users,
                         active_users=active_users,
                         active_today=active_today,
                         total_quizzes=total_quizzes,
                         avg_score=avg_score,
                         score_distribution=score_distribution,
                         daily_stats=daily_stats,
                         topic_stats=topic_stats,
                         quiz_history=quiz_history,
                         user_performance=user_performance) 