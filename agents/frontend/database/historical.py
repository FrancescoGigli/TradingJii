"""
Training data functions (ML Training data)

Reads from training_data table:
- OHLCV + 16 technical indicators
- No NULL values (warmup discarded)
- Date aligned between 15m and 1h
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import os
import json
from .connection import get_connection

# Import from parent config
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import DB_PATH


# =========================================
# TRAINING DATA STATS
# =========================================

@st.cache_data(ttl=60, show_spinner=False)
def get_historical_stats():
    """Get statistics for training data (cached 60s)"""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_data'")
        if not cur.fetchone():
            return {'exists': False}
        
        cur.execute('''
            SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT timeframe), 
                   COUNT(*), MIN(timestamp), MAX(timestamp)
            FROM training_data
        ''')
        r = cur.fetchone()
        
        # Database file size
        db_size = Path(DB_PATH).stat().st_size if Path(DB_PATH).exists() else 0
        
        return {
            'exists': True,
            'symbols': r[0] or 0,
            'timeframes': r[1] or 0,
            'total_candles': r[2] or 0,
            'min_date': r[3],
            'max_date': r[4],
            'db_size_mb': db_size / (1024 * 1024)
        }
    except Exception as e:
        return {'exists': False, 'error': str(e)}
    finally:
        conn.close()


# =========================================
# TRAINING DATA ACCESS
# =========================================

def get_historical_ohlcv(symbol, timeframe, limit=1000, include_indicators=True):
    """
    Get training data with pre-computed indicators from database.
    All data is guaranteed to have no NULL values.
    
    Args:
        symbol: Trading pair symbol
        timeframe: Candle timeframe
        limit: Max number of candles to return
        include_indicators: Include pre-computed indicators (default True)
    
    Returns:
        DataFrame with OHLCV and 16 indicators
    """
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    try:
        # Check if table exists
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_data'")
        if not cur.fetchone():
            return pd.DataFrame()
        
        if include_indicators:
            columns = '''timestamp, open, high, low, close, volume,
                        sma_20, sma_50, ema_12, ema_26,
                        bb_upper, bb_mid, bb_lower,
                        macd, macd_signal, macd_hist,
                        rsi, stoch_k, stoch_d, atr,
                        volume_sma, obv'''
        else:
            columns = 'timestamp, open, high, low, close, volume'
        
        query = f'''
            SELECT {columns}
            FROM training_data 
            WHERE symbol=? AND timeframe=?
            ORDER BY timestamp DESC LIMIT ?
        '''
        df = pd.read_sql_query(query, conn, params=(symbol, timeframe, limit))
        
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            df.set_index('timestamp', inplace=True)
            
            # Rename indicator columns to match frontend expected names (uppercase for charts)
            if include_indicators:
                rename_map = {
                    'sma_20': 'SMA_20', 'sma_50': 'SMA_50',
                    'ema_12': 'EMA_12', 'ema_26': 'EMA_26',
                    'bb_upper': 'BB_upper', 'bb_mid': 'BB_mid', 'bb_lower': 'BB_lower',
                    'macd': 'MACD', 'macd_signal': 'MACD_signal', 'macd_hist': 'MACD_hist',
                    'rsi': 'RSI',
                    'stoch_k': 'Stoch_K', 'stoch_d': 'Stoch_D',
                    'atr': 'ATR',
                    'volume_sma': 'Volume_SMA', 'obv': 'OBV'
                }
                df.rename(columns=rename_map, inplace=True)
        return df
    except Exception as e:
        print(f"Error in get_historical_ohlcv: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=60, show_spinner=False)
def get_historical_symbols():
    """Get list of symbols with training data (cached 60s)"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_data'")
        if not cur.fetchone():
            return []
        
        cur.execute('SELECT DISTINCT symbol FROM training_data ORDER BY symbol')
        return [r[0] for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


@st.cache_data(ttl=60, show_spinner=False)
def get_historical_symbols_by_volume():
    """Get list of symbols with training data, ordered by volume rank (cached 60s)"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_data'")
        if not cur.fetchone():
            return []
        
        # Get symbols ordered by volume rank
        query = '''
            SELECT DISTINCT t.symbol
            FROM training_data t
            LEFT JOIN top_symbols ts ON t.symbol = ts.symbol
            ORDER BY COALESCE(ts.rank, 999) ASC
        '''
        cur.execute(query)
        return [r[0] for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def get_historical_date_range(symbol, timeframe):
    """Get date range for training data of a symbol/timeframe"""
    conn = get_connection()
    if not conn:
        return None, None
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT MIN(timestamp), MAX(timestamp)
            FROM training_data
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        row = cur.fetchone()
        return row[0], row[1] if row else (None, None)
    except Exception:
        return None, None
    finally:
        conn.close()


# =========================================
# TRAINING DATA INVENTORY
# =========================================

@st.cache_data(ttl=60, show_spinner=False)
def get_historical_inventory():
    """
    Get per-symbol inventory with date ranges, ordered by volume rank.
    Returns detailed info for each coin including both timeframes. (cached 60s)
    """
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_data'")
        if not cur.fetchone():
            return []
        
        # Get all symbols with their data ranges, joined with top_symbols for ranking
        query = '''
            WITH symbol_stats AS (
                SELECT 
                    symbol,
                    timeframe,
                    MIN(timestamp) as from_date,
                    MAX(timestamp) as to_date,
                    COUNT(*) as candles
                FROM training_data
                GROUP BY symbol, timeframe
            ),
            symbol_summary AS (
                SELECT 
                    s.symbol,
                    MAX(CASE WHEN s.timeframe = '15m' THEN s.from_date END) as from_date_15m,
                    MAX(CASE WHEN s.timeframe = '15m' THEN s.to_date END) as to_date_15m,
                    MAX(CASE WHEN s.timeframe = '15m' THEN s.candles ELSE 0 END) as candles_15m,
                    MAX(CASE WHEN s.timeframe = '1h' THEN s.from_date END) as from_date_1h,
                    MAX(CASE WHEN s.timeframe = '1h' THEN s.to_date END) as to_date_1h,
                    MAX(CASE WHEN s.timeframe = '1h' THEN s.candles ELSE 0 END) as candles_1h
                FROM symbol_stats s
                GROUP BY s.symbol
            )
            SELECT 
                COALESCE(ts.rank, 999) as rank,
                ss.symbol,
                ss.from_date_15m,
                ss.to_date_15m,
                ss.candles_15m,
                ss.from_date_1h,
                ss.to_date_1h,
                ss.candles_1h,
                COALESCE(ts.volume_24h, 0) as volume_24h
            FROM symbol_summary ss
            LEFT JOIN top_symbols ts ON ss.symbol = ts.symbol
            ORDER BY COALESCE(ts.rank, 999) ASC
        '''
        
        cur.execute(query)
        
        results = []
        for row in cur.fetchall():
            results.append({
                'rank': row[0],
                'symbol': row[1],
                'from_date_15m': row[2],
                'to_date_15m': row[3],
                'candles_15m': row[4] or 0,
                'from_date_1h': row[5],
                'to_date_1h': row[6],
                'candles_1h': row[7] or 0,
                'volume_24h': row[8] or 0
            })
        return results
    except Exception as e:
        print(f"Error in get_historical_inventory: {e}")
        return []
    finally:
        conn.close()


def get_symbol_data_quality(symbol: str, timeframe: str):
    """Get data quality metrics for a specific symbol/timeframe"""
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        
        # Get stats from training_data
        cur.execute('''
            SELECT 
                MIN(timestamp) as from_date,
                MAX(timestamp) as to_date,
                COUNT(*) as total_candles,
                AVG(volume) as avg_volume,
                MIN(close) as min_price,
                MAX(close) as max_price
            FROM training_data
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        
        row = cur.fetchone()
        if not row or not row[0]:
            return None
        
        return {
            'from_date': row[0],
            'to_date': row[1],
            'total_candles': row[2],
            'avg_volume': row[3] or 0,
            'min_price': row[4] or 0,
            'max_price': row[5] or 0,
            'completeness_pct': 100.0,  # No NULL values in training_data
            'gap_count': 0,
            'status': 'COMPLETE'
        }
    except Exception:
        return None
    finally:
        conn.close()


# =========================================
# TRIGGER DOWNLOAD
# =========================================

def trigger_backfill_with_dates(start_date, end_date):
    """
    Create trigger file with date range to start training data download.
    
    Args:
        start_date: Start date for data download
        end_date: End date for data download
    
    Returns:
        bool: True if trigger file was created successfully
    """
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    trigger_file = Path(shared_path) / 'start_backfill.txt'
    
    try:
        trigger_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write trigger with date range info
        trigger_data = {
            'triggered_at': str(pd.Timestamp.now()),
            'start_date': str(start_date),
            'end_date': str(end_date)
        }
        trigger_file.write_text(json.dumps(trigger_data))
        return True
    except Exception as e:
        print(f"Error creating trigger file: {e}")
        return False


def trigger_backfill():
    """Alias for backward compatibility - requires dates now"""
    return False  # Dates are required


def check_backfill_running():
    """Check if download is currently running (check for trigger file)"""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    trigger_file = Path(shared_path) / 'start_backfill.txt'
    return trigger_file.exists()


# =========================================
# CLEAR DATA
# =========================================

def clear_historical_data():
    """Clear all training data and backfill status to start fresh"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        
        # Clear training data table
        cur.execute("DELETE FROM training_data")
        
        # Clear backfill status table (reset progress)
        cur.execute("DELETE FROM backfill_status")
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error clearing training data: {e}")
        return False
    finally:
        conn.close()


# =========================================
# BACKFILL STATUS (for progress tracking)
# =========================================

def get_backfill_status_all():
    """Get all backfill status records for progress display"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backfill_status'")
        if not cur.fetchone():
            return []
        
        cur.execute('''
            SELECT symbol, timeframe, status, oldest_timestamp, newest_timestamp,
                   total_candles, warmup_candles, training_candles,
                   completeness_pct, gap_count, last_update, error_message
            FROM backfill_status
            ORDER BY symbol, timeframe
        ''')
        
        results = []
        for row in cur.fetchall():
            results.append({
                'symbol': row[0],
                'timeframe': row[1],
                'status': row[2],
                'oldest_timestamp': row[3],
                'newest_timestamp': row[4],
                'total_candles': row[5] or 0,
                'warmup_candles': row[6] or 0,
                'training_candles': row[7] or 0,
                'completeness_pct': row[8] or 0.0,
                'gap_count': row[9] or 0,
                'last_update': row[10],
                'error_message': row[11]
            })
        return results
    except Exception as e:
        print(f"Error in get_backfill_status_all: {e}")
        return []
    finally:
        conn.close()


def get_backfill_summary():
    """Get summary of backfill status by timeframe"""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backfill_status'")
        if not cur.fetchone():
            return {}
        
        cur.execute('''
            SELECT timeframe, status, COUNT(*) as count, SUM(total_candles) as candles
            FROM backfill_status
            GROUP BY timeframe, status
        ''')
        
        results = {}
        for row in cur.fetchall():
            tf = row[0]
            if tf not in results:
                results[tf] = {'COMPLETE': 0, 'IN_PROGRESS': 0, 'PENDING': 0, 'ERROR': 0, 'total_candles': 0}
            results[tf][row[1]] = row[2]
            results[tf]['total_candles'] += row[3] or 0
        
        return results
    except Exception:
        return {}
    finally:
        conn.close()


def get_backfill_errors():
    """Get list of backfill errors"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backfill_status'")
        if not cur.fetchone():
            return []
        
        cur.execute('''
            SELECT symbol, timeframe, error_message, last_update
            FROM backfill_status
            WHERE status = 'ERROR'
            ORDER BY last_update DESC
        ''')
        
        return [{'symbol': r[0], 'timeframe': r[1], 'error_message': r[2], 'last_update': r[3]} 
                for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def retry_failed_downloads():
    """Reset ERROR status to PENDING for retry"""
    conn = get_connection()
    if not conn:
        return 0
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backfill_status'")
        if not cur.fetchone():
            return 0
        
        cur.execute('''
            UPDATE backfill_status 
            SET status = 'PENDING', error_message = NULL
            WHERE status = 'ERROR'
        ''')
        count = cur.rowcount
        conn.commit()
        return count
    except Exception:
        return 0
    finally:
        conn.close()
