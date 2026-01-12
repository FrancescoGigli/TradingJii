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


def get_connection():
    """Get database connection"""
    if not Path(DB_PATH).exists():
        return None
    return sqlite3.connect(DB_PATH, check_same_thread=False)
