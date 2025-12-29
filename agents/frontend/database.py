"""
Database access functions for the Crypto Dashboard
"""

import sqlite3
from pathlib import Path
import pandas as pd
from config import DB_PATH


def get_connection():
    """Get database connection"""
    if not Path(DB_PATH).exists():
        return None
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def get_top_symbols():
    """Get list of top symbols with volume"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT symbol, rank, volume_24h, fetched_at 
            FROM top_symbols 
            ORDER BY rank ASC
        ''')
        results = []
        for row in cur.fetchall():
            results.append({
                'symbol': row[0],
                'rank': row[1],
                'volume_24h': row[2],
                'fetched_at': row[3]
            })
        return results
    except Exception:
        return []
    finally:
        conn.close()


def get_symbols():
    """Get list of distinct symbols"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute('SELECT DISTINCT symbol FROM ohlcv_data ORDER BY symbol')
        return [r[0] for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def get_timeframes(symbol):
    """Get available timeframes for a symbol"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT DISTINCT timeframe FROM ohlcv_data WHERE symbol=? ORDER BY timeframe',
            (symbol,)
        )
        return [r[0] for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def get_ohlcv(symbol, timeframe, limit=200):
    """Get OHLCV data for a symbol and timeframe"""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    try:
        query = '''
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv_data WHERE symbol=? AND timeframe=?
            ORDER BY timestamp DESC LIMIT ?
        '''
        df = pd.read_sql_query(query, conn, params=(symbol, timeframe, limit))
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            df.set_index('timestamp', inplace=True)
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def get_stats():
    """Get database statistics"""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT timeframe), 
                   COUNT(*), MAX(timestamp)
            FROM ohlcv_data
        ''')
        r = cur.fetchone()
        
        # Top symbols info
        cur.execute('SELECT COUNT(*), MIN(fetched_at) FROM top_symbols')
        top_info = cur.fetchone()
        
        return {
            'symbols': r[0] or 0,
            'timeframes': r[1] or 0,
            'candles': r[2] or 0,
            'updated': r[3],
            'top_count': top_info[0] or 0,
            'top_fetched_at': top_info[1]
        }
    except Exception:
        return {}
    finally:
        conn.close()
