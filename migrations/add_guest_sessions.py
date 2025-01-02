from utils import get_db_connection

def migrate():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create guest_sessions table
    cursor.execute('''
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
    )
    ''')
    
    # Create index for faster lookups
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_guest_sessions_guest_id 
    ON guest_sessions(guest_id)
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_guest_sessions_activity 
    ON guest_sessions(last_activity)
    ''')
    
    conn.commit()
    conn.close()
    print("Guest sessions table created successfully!")

if __name__ == "__main__":
    migrate() 