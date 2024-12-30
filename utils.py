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
    if database_path is None:
        database_path = os.path.join(os.path.dirname(__file__), "data", "mcq_database.db")
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    return conn