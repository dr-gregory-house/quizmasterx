import sqlite3
import os

def create_tables():
    db_path = os.path.join('data', 'mcq_database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create user statistics tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_topic_stats (
        user_id INTEGER,
        topic TEXT,
        total_questions INTEGER DEFAULT 0,
        correct_answers INTEGER DEFAULT 0,
        last_attempt_date TIMESTAMP,
        PRIMARY KEY (user_id, topic),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_quiz_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        quiz_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        topic TEXT,
        score INTEGER,
        total_questions INTEGER,
        time_taken INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_weak_topics (
        user_id INTEGER,
        topic TEXT,
        weakness_score FLOAT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, topic),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_daily_stats (
        user_id INTEGER,
        date DATE,
        questions_attempted INTEGER DEFAULT 0,
        questions_correct INTEGER DEFAULT 0,
        study_time INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, date),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')

    conn.commit()
    conn.close()
    print("Tables created successfully!")

if __name__ == '__main__':
    create_tables() 