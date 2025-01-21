# utils.py

import sqlite3
from datetime import datetime
import os

def adapt_datetime_to_iso(dt):
    """Converts datetime object to ISO format string."""
    return dt.isoformat()

def convert_iso_to_datetime(s):
    """Converts ISO format string to datetime object."""
    if isinstance(s, str):
        return datetime.fromisoformat(s)
    return s  # Return the input if it's not a string

def get_db_connection(database_path=None):
    """Get database connection with relative path for deployment compatibility"""
    if database_path is None:
        # Use the default relative path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        database_path = os.path.join(current_dir, 'data', 'mcq_database.db')
    
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(database_path), exist_ok=True)
    
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_review_questions_count(user_id):
    """Get the count of questions due for review for a given user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM sm2_data
        WHERE user_id = ? AND next_practice_date <= ?
    """, (user_id, now))
    result = cursor.fetchone()
    conn.close()
    return result['count'] if result else 0

def get_next_review_question(user_id):
    """Get the next question due for review for a given user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()
    cursor.execute("""
        SELECT q.question_id, q.question_text, q.correct_answer, q.option_a, q.option_b, q.option_c, q.option_d, q.topic, sm.next_practice_date
        FROM questions q
        JOIN sm2_data sm ON q.question_id = sm.question_id
        WHERE sm.user_id = ? AND sm.next_practice_date <= ?
        ORDER BY sm.next_practice_date ASC
        LIMIT 1
    """, (user_id, now))
    question = cursor.fetchone()
    conn.close()
    return dict(question) if question else None