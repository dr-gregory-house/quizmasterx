-- Add guest sessions table
CREATE TABLE IF NOT EXISTS guest_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    last_activity DATETIME NOT NULL,
    session_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
); 