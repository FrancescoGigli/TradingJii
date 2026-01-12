"""
OHLCV data access functions
"""

import streamlit as st
import pandas as pd
from .connection import get_connection

# Import from parent config
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import CANDLES_LIMIT


@st.cache_data(ttl=300, show_spinner=False)
def get_top_symbols():
    """Get list of top symbols with volume (cached 5min)"""
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


@st.cache_data(ttl=300, show_spinner=False)
def get_symbols():
    """Get list of distinct symbols ordered by volume (cached 5min)"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        # First try to get from top_symbols (ordered by rank = volume)
        cur.execute('''
            SELECT ts.symbol 
            FROM top_symbols ts
            INNER JOIN (SELECT DISTINCT symbol FROM ohlcv_data) od ON ts.symbol = od.symbol
            ORDER BY ts.rank ASC
        ''')
        symbols = [r[0] for r in cur.fetchall()]
        
        # Fallback to alphabetical if no top_symbols
        if not symbols:
            cur.execute('SELECT DISTINCT symbol FROM ohlcv_data ORDER BY symbol')
            symbols = [r[0] for r in cur.fetchall()]
        
        return symbols
    except Exception:
        return []
    finally:
        conn.close()


@st.cache_data(ttl=300, show_spinner=False)
def get_timeframes(symbol):
    """Get available timeframes for a symbol (cached 5min)"""
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


def get_ohlcv(symbol, timeframe, limit=CANDLES_LIMIT):
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


@st.cache_data(ttl=30, show_spinner=False)
def get_stats():
    """Get database statistics (cached 30s)"""
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


@st.cache_data(ttl=10, show_spinner=False)
def get_update_status():
    """Get current update status from data-fetcher (cached 10s)"""
    conn = get_connection()
    if not conn:
        return {
            'status': 'OFFLINE',
            'last_update': None,
            'duration_sec': 0,
            'symbols_updated': 0,
            'candles_updated': 0
        }
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT status, last_update, last_update_duration_sec, 
                   symbols_updated, candles_updated
            FROM update_status WHERE id = 1
        ''')
        row = cur.fetchone()
        
        if row:
            return {
                'status': row[0] or 'IDLE',
                'last_update': row[1],
                'duration_sec': row[2] or 0,
                'symbols_updated': row[3] or 0,
                'candles_updated': row[4] or 0
            }
        return {
            'status': 'IDLE',
            'last_update': None,
            'duration_sec': 0,
            'symbols_updated': 0,
            'candles_updated': 0
        }
    except Exception:
        # Table might not exist yet
        return {
            'status': 'OFFLINE',
            'last_update': None,
            'duration_sec': 0,
            'symbols_updated': 0,
            'candles_updated': 0
        }
    finally:
        conn.close()
