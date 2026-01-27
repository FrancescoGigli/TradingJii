"""
🗄️ ML Inference Agent - Database Operations
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd

from config import DATABASE_PATH

logger = logging.getLogger(__name__)


OHLCV_TABLE = "realtime_ohlcv"


def _to_db_timestamp(value) -> str:
    """Convert a Timestamp-like value into a SQLite-friendly ISO string.

    sqlite3 does not accept pandas.Timestamp directly as a bound parameter.
    We store timestamps as ISO-8601 strings for consistency across agents.
    """

    if value is None:
        return ""

    try:
        # pandas.Timestamp supports isoformat()
        return value.isoformat()
    except Exception:
        return str(value)


def get_connection():
    """
    Get database connection with optimized settings for concurrent access.
    
    Features:
    - timeout=30: Wait up to 30 seconds if database is locked
    - WAL mode: Allow concurrent reads during writes
    - busy_timeout: SQLite-level timeout for locked operations
    """
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")  # 30 seconds in milliseconds
    conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe with WAL
    
    return conn


def init_ml_signals_table():
    """Create ml_signals table if not exists"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create table if not exists (safe for concurrent access)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ml_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            score_long REAL,
            score_short REAL,
            confidence_long REAL,
            confidence_short REAL,
            signal_long TEXT,
            signal_short TEXT,
            model_version TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timeframe, timestamp)
        )
    """)
    
    # Index for fast queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ml_signals_symbol_timeframe 
        ON ml_signals(symbol, timeframe, timestamp DESC)
    """)
    
    conn.commit()
    conn.close()
    logger.info("✅ ml_signals table initialized")


def get_available_symbols(timeframe: str = '15m') -> List[str]:
    """Get list of symbols with data in the database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT symbol 
        FROM realtime_ohlcv 
        WHERE timeframe = ?
        ORDER BY symbol
    """, (timeframe,))
    
    symbols = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return symbols


def get_ohlcv_data(symbol: str, timeframe: str, limit: int = 200) -> Optional[pd.DataFrame]:
    """Get OHLCV data for a symbol"""
    conn = get_connection()
    
    query = """
        SELECT timestamp, open, high, low, close, volume
        FROM realtime_ohlcv
        WHERE symbol = ? AND timeframe = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """
    
    df = pd.read_sql_query(query, conn, params=(symbol, timeframe, limit))
    conn.close()
    
    if df.empty:
        return None
    
    # Convert timestamp to datetime and sort ascending
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    return df


def save_ml_signal(signal: Dict):
    """Save ML signal to database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO ml_signals 
        (symbol, timeframe, timestamp, score_long, score_short, 
         confidence_long, confidence_short, signal_long, signal_short, model_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        signal['symbol'],
        signal['timeframe'],
        _to_db_timestamp(signal.get('timestamp')),
        signal['score_long'],
        signal['score_short'],
        signal['confidence_long'],
        signal['confidence_short'],
        signal['signal_long'],
        signal['signal_short'],
        signal['model_version']
    ))
    
    conn.commit()
    conn.close()


def save_ml_signals_batch(signals: List[Dict]):
    """Save multiple ML signals in batch"""
    if not signals:
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.executemany("""
        INSERT OR REPLACE INTO ml_signals 
        (symbol, timeframe, timestamp, score_long, score_short, 
         confidence_long, confidence_short, signal_long, signal_short, model_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (s['symbol'], s['timeframe'], _to_db_timestamp(s.get('timestamp')), s['score_long'], s['score_short'],
         s['confidence_long'], s['confidence_short'], s['signal_long'], s['signal_short'], s['model_version'])
        for s in signals
    ])
    
    conn.commit()
    conn.close()
    logger.info(f"✅ Saved {len(signals)} ML signals to database")


def get_latest_signals(timeframe: str = '15m', limit: int = 100) -> pd.DataFrame:
    """Get latest ML signals for all symbols"""
    conn = get_connection()
    
    query = """
        SELECT * FROM ml_signals
        WHERE timeframe = ?
        AND timestamp = (
            SELECT MAX(timestamp) FROM ml_signals s2 
            WHERE s2.symbol = ml_signals.symbol AND s2.timeframe = ml_signals.timeframe
        )
        ORDER BY confidence_long DESC
        LIMIT ?
    """
    
    df = pd.read_sql_query(query, conn, params=(timeframe, limit))
    conn.close()
    
    return df


def cleanup_old_signals(days: int = 7):
    """Remove signals older than N days"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        DELETE FROM ml_signals 
        WHERE created_at < datetime('now', ?)
    """, (f'-{days} days',))
    
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted > 0:
        logger.info(f"🗑️ Cleaned up {deleted} old ML signals")
