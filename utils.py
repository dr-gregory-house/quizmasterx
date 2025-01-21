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