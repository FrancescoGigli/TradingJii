"""
Database connection module
"""

import sqlite3
from pathlib import Path

# Import from parent config
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import DB_PATH

# Connection timeout in seconds (wait if database is locked)
DB_TIMEOUT = 30


def get_connection():
    """
    Get database connection with optimized settings for concurrent access.
    
    Features:
    - timeout=30: Wait up to 30 seconds if database is locked
    - WAL mode: Allow concurrent reads during writes
    - busy_timeout: SQLite-level timeout for locked operations
    """
    if not Path(DB_PATH).exists():
        return None
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=DB_TIMEOUT)
    
    # Enable WAL mode for better concurrency
    # WAL allows readers and writer to operate concurrently
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")  # 30 seconds in milliseconds
    conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe with WAL
    
    return conn
