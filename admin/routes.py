from flask import Blueprint, render_template, session, redirect, url_for, request, flash, jsonify
from functools import wraps
from utils import get_db_connection
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='admin')

# admin decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
         if session.get('user_role') != 'admin':
            flash('Admin access required.', 'warning')
            return redirect(url_for('main.hello'))
         return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@admin_required
def admin_dashboard():
    """Admin dashboard, list of users and other information"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all users with formatted last_activity
    cursor.execute("""
        SELECT id, username, is_active, 
               strftime('%Y-%m-%d %H:%M', last_activity) as last_activity, 
               role 
        FROM users
    """)
    users = cursor.fetchall()

    # Get active users (users with any last_activity)
    cursor.execute("""
        SELECT id, username, 
               strftime('%Y-%m-%d %H:%M', last_activity) as last_activity 
        FROM users 
        WHERE last_activity IS NOT NULL 
        ORDER BY last_activity DESC
    """)
    active_users = cursor.fetchall()

    # Get online users (last activity within the last 5 minutes)
    now = datetime.now()
    five_minutes_ago = now - timedelta(minutes=5)
    cursor.execute("""
        SELECT id, username, 
               strftime('%Y-%m-%d %H:%M', last_activity) as last_activity 
        FROM users 
        WHERE last_activity >= ? 
        ORDER BY last_activity DESC
    """, (five_minutes_ago,))
    online_users = cursor.fetchall()

    # Get total user counts
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    # Get pending activation requests
    cursor.execute("SELECT id, username FROM users WHERE is_active = 0")
    pending_users = cursor.fetchall()

    conn.close()
    return render_template('admin/admin_dashboard.html', 
                         users=users, 
                         active_users=active_users, 
                         online_users=online_users, 
                         total_users=total_users, 
                         pending_users=pending_users)

@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user_activation(user_id):
    """Handles toggle user activation or deactivation from the admin panel."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_active FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if user:
        new_status = 1 if user['is_active'] == 0 else 0
        cursor.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
        conn.commit()
        conn.close()
        return jsonify({
            'success': True,
            'message': 'User activation status has been changed successfully'
        })
    else:
        conn.close()
        return jsonify({
            'success': False,
            'message': 'User not found'
        }), 404

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Handles delete user request."""
    if user_id == session.get('user_id'):
        return jsonify({
            'success': False,
            'message': 'You cannot delete your own account'
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # First check if user exists and is not an admin
        cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        if user['role'] == 'admin':
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Cannot delete admin users'
            }), 400

        # Delete user's data from related tables
        tables = ['user_topic_stats', 'user_quiz_history', 'user_weak_topics', 
                 'user_daily_stats', 'sm2_data', 'user_question_performance']
        for table in tables:
            cursor.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))

        # Finally delete the user
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return jsonify({
            'success': True,
            'message': 'User deleted successfully'
        })
    except Exception as e:
        conn.close()
        return jsonify({
            'success': False,
            'message': f'Error deleting user: {str(e)}'
        }), 500

@admin_bp.route('/users/<int:user_id>/make-admin', methods=['POST'])
@admin_required
def make_admin(user_id):
    """Makes a user an admin."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return jsonify({
            'success': True,
            'message': 'User has been made admin successfully'
        })
    except Exception as e:
        conn.close()
        return jsonify({
            'success': False,
            'message': f'Error making user admin: {str(e)}'
        }), 500

@admin_bp.route('/questions')
@admin_required
def manage_questions():
    """Displays a list of questions for management."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT question_id, question_text FROM questions")
    questions = cursor.fetchall()
    conn.close()
    return render_template('admin/manage_questions.html', questions=questions)

@admin_bp.route('/questions/<int:question_id>/edit')
@admin_required
def edit_question(question_id):
    """Displays the form to edit a specific question."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE question_id = ?", (question_id,))
    question = cursor.fetchone()
    conn.close()
    if question:
        return render_template('admin/edit_question.html', question=question)
    else:
        flash('Question not found.', 'error')
        return redirect(url_for('admin.manage_questions'))

@admin_bp.route('/questions/<int:question_id>/delete', methods=['POST'])
@admin_required
def delete_question(question_id):
    """Deletes a specific question."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM questions WHERE question_id = ?", (question_id,))
        conn.commit()
        conn.close()
        flash('Question deleted successfully.', 'success')
    except Exception as e:
        conn.close()
        flash(f'Error deleting question: {e}', 'error')
    return redirect(url_for('admin.manage_questions'))