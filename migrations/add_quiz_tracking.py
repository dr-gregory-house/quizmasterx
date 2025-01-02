from utils import get_db_connection

def migrate():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create quiz_attempts table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS quiz_attempts (
        attempt_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        quiz_mode TEXT NOT NULL,
        start_time DATETIME NOT NULL,
        end_time DATETIME,
        score INTEGER DEFAULT 0,
        total_questions INTEGER DEFAULT 0,
        settings TEXT,  -- JSON field for mode-specific settings
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create quiz_responses table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS quiz_responses (
        response_id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id TEXT NOT NULL,
        question_id INTEGER NOT NULL,
        selected_option TEXT,
        is_correct BOOLEAN,
        response_time DATETIME NOT NULL,
        time_taken INTEGER,  -- Time taken in seconds
        FOREIGN KEY (attempt_id) REFERENCES quiz_attempts(attempt_id),
        FOREIGN KEY (question_id) REFERENCES questions(question_id)
    )
    ''')
    
    # Create indexes for better performance
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user 
    ON quiz_attempts(user_id)
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_quiz_responses_attempt 
    ON quiz_responses(attempt_id)
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_quiz_responses_question 
    ON quiz_responses(question_id)
    ''')
    
    conn.commit()
    conn.close()
    print("Quiz tracking tables created successfully!")

if __name__ == "__main__":
    migrate() 