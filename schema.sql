-- User Statistics Tables
CREATE TABLE IF NOT EXISTS user_topic_stats (
    user_id INTEGER,
    topic TEXT,
    total_questions INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    last_attempt_date TIMESTAMP,
    PRIMARY KEY (user_id, topic),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS user_quiz_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    quiz_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    topic TEXT,
    score INTEGER,
    total_questions INTEGER,
    time_taken INTEGER,  -- in seconds
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS user_weak_topics (
    user_id INTEGER,
    topic TEXT,
    weakness_score FLOAT,  -- lower score means weaker topic
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, topic),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS user_daily_stats (
    user_id INTEGER,
    date DATE,
    questions_attempted INTEGER DEFAULT 0,
    questions_correct INTEGER DEFAULT 0,
    study_time INTEGER DEFAULT 0,  -- in minutes
    PRIMARY KEY (user_id, date),
    FOREIGN KEY (user_id) REFERENCES users(id)
); 