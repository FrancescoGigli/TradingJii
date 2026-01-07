"""
Database access functions for the Crypto Dashboard
"""

import sqlite3
from pathlib import Path
import pandas as pd
from config import DB_PATH, CANDLES_LIMIT


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
    """Get list of distinct symbols ordered by volume (from top_symbols table)"""
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


def get_update_status():
    """Get current update status from data-fetcher"""
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


# =========================================
# HISTORICAL DATA FUNCTIONS (ML Training)
# =========================================

def get_historical_stats():
    """Get statistics for historical data (ML training data)"""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='historical_ohlcv'")
        if not cur.fetchone():
            return {'exists': False}
        
        cur.execute('''
            SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT timeframe), 
                   COUNT(*), MIN(timestamp), MAX(timestamp),
                   SUM(CASE WHEN interpolated = 1 THEN 1 ELSE 0 END)
            FROM historical_ohlcv
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
            'interpolated_count': r[5] or 0,
            'db_size_mb': db_size / (1024 * 1024)
        }
    except Exception as e:
        return {'exists': False, 'error': str(e)}
    finally:
        conn.close()


def get_backfill_status_all():
    """Get backfill status for all symbols/timeframes"""
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
                'completeness_pct': row[8] or 0,
                'gap_count': row[9] or 0,
                'last_update': row[10],
                'error_message': row[11]
            })
        return results
    except Exception:
        return []
    finally:
        conn.close()


def get_historical_ohlcv(symbol, timeframe, limit=1000):
    """Get historical OHLCV data for visualization"""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    try:
        # Check if table exists
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='historical_ohlcv'")
        if not cur.fetchone():
            return pd.DataFrame()
        
        query = '''
            SELECT timestamp, open, high, low, close, volume, interpolated
            FROM historical_ohlcv 
            WHERE symbol=? AND timeframe=?
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


def get_historical_symbols():
    """Get list of symbols with historical data"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='historical_ohlcv'")
        if not cur.fetchone():
            return []
        
        cur.execute('SELECT DISTINCT symbol FROM historical_ohlcv ORDER BY symbol')
        return [r[0] for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def get_historical_date_range(symbol, timeframe):
    """Get date range for historical data of a symbol/timeframe"""
    conn = get_connection()
    if not conn:
        return None, None
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT MIN(timestamp), MAX(timestamp)
            FROM historical_ohlcv
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        row = cur.fetchone()
        return row[0], row[1] if row else (None, None)
    except Exception:
        return None, None
    finally:
        conn.close()


def get_backfill_summary():
    """Get summary of backfill status grouped by status"""
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
            SELECT status, COUNT(*) as count,
                   SUM(total_candles) as total_candles,
                   AVG(completeness_pct) as avg_completeness
            FROM backfill_status
            GROUP BY status
        ''')
        
        result = {}
        for row in cur.fetchall():
            result[row[0]] = {
                'count': row[1],
                'total_candles': row[2] or 0,
                'avg_completeness': round(row[3] or 0, 2)
            }
        return result
    except Exception:
        return {}
    finally:
        conn.close()


def get_historical_inventory():
    """
    Get per-symbol inventory with date ranges, ordered by volume rank.
    Returns detailed info for each coin including both timeframes.
    """
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        # Check if tables exist
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='historical_ohlcv'")
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
                    COUNT(*) as candles,
                    SUM(CASE WHEN interpolated = 1 THEN 1 ELSE 0 END) as interpolated
                FROM historical_ohlcv
                GROUP BY symbol, timeframe
            ),
            symbol_summary AS (
                SELECT 
                    s.symbol,
                    MAX(CASE WHEN s.timeframe = '15m' THEN s.from_date END) as from_date_15m,
                    MAX(CASE WHEN s.timeframe = '15m' THEN s.to_date END) as to_date_15m,
                    MAX(CASE WHEN s.timeframe = '15m' THEN s.candles ELSE 0 END) as candles_15m,
                    MAX(CASE WHEN s.timeframe = '15m' THEN s.interpolated ELSE 0 END) as interp_15m,
                    MAX(CASE WHEN s.timeframe = '1h' THEN s.from_date END) as from_date_1h,
                    MAX(CASE WHEN s.timeframe = '1h' THEN s.to_date END) as to_date_1h,
                    MAX(CASE WHEN s.timeframe = '1h' THEN s.candles ELSE 0 END) as candles_1h,
                    MAX(CASE WHEN s.timeframe = '1h' THEN s.interpolated ELSE 0 END) as interp_1h
                FROM symbol_stats s
                GROUP BY s.symbol
            )
            SELECT 
                COALESCE(ts.rank, 999) as rank,
                ss.symbol,
                ss.from_date_15m,
                ss.to_date_15m,
                ss.candles_15m,
                ss.interp_15m,
                ss.from_date_1h,
                ss.to_date_1h,
                ss.candles_1h,
                ss.interp_1h,
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
                'interp_15m': row[5] or 0,
                'from_date_1h': row[6],
                'to_date_1h': row[7],
                'candles_1h': row[8] or 0,
                'interp_1h': row[9] or 0,
                'volume_24h': row[10] or 0
            })
        return results
    except Exception as e:
        print(f"Error in get_historical_inventory: {e}")
        return []
    finally:
        conn.close()


def get_historical_symbols_by_volume():
    """Get list of symbols with historical data, ordered by volume rank"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='historical_ohlcv'")
        if not cur.fetchone():
            return []
        
        # Get symbols ordered by volume rank
        query = '''
            SELECT DISTINCT h.symbol
            FROM historical_ohlcv h
            LEFT JOIN top_symbols ts ON h.symbol = ts.symbol
            ORDER BY COALESCE(ts.rank, 999) ASC
        '''
        cur.execute(query)
        return [r[0] for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def get_symbol_data_quality(symbol: str, timeframe: str):
    """Get detailed data quality metrics for a specific symbol/timeframe"""
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        
        # Get basic stats
        cur.execute('''
            SELECT 
                MIN(timestamp) as from_date,
                MAX(timestamp) as to_date,
                COUNT(*) as total_candles,
                SUM(CASE WHEN interpolated = 1 THEN 1 ELSE 0 END) as interpolated,
                AVG(volume) as avg_volume,
                MIN(close) as min_price,
                MAX(close) as max_price
            FROM historical_ohlcv
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        
        row = cur.fetchone()
        if not row or not row[0]:
            return None
        
        # Get backfill status
        cur.execute('''
            SELECT completeness_pct, gap_count, status
            FROM backfill_status
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        
        bf_row = cur.fetchone()
        
        return {
            'from_date': row[0],
            'to_date': row[1],
            'total_candles': row[2],
            'interpolated': row[3] or 0,
            'avg_volume': row[4] or 0,
            'min_price': row[5] or 0,
            'max_price': row[6] or 0,
            'completeness_pct': bf_row[0] if bf_row else 0,
            'gap_count': bf_row[1] if bf_row else 0,
            'status': bf_row[2] if bf_row else 'UNKNOWN'
        }
    except Exception:
        return None
    finally:
        conn.close()


def trigger_backfill():
    """Create trigger file to start backfill process"""
    from pathlib import Path
    import os
    
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    trigger_file = Path(shared_path) / 'start_backfill.txt'
    
    try:
        trigger_file.parent.mkdir(parents=True, exist_ok=True)
        trigger_file.write_text(f'Triggered at {pd.Timestamp.now()}')
        return True
    except Exception:
        return False


def check_backfill_running():
    """Check if backfill is currently running"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backfill_status'")
        if not cur.fetchone():
            return False
        
        cur.execute("SELECT COUNT(*) FROM backfill_status WHERE status = 'IN_PROGRESS'")
        return cur.fetchone()[0] > 0
    except Exception:
        return False
    finally:
        conn.close()


def get_backfill_errors():
    """Get list of symbols with errors and their error messages"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backfill_status'")
        if not cur.fetchone():
            return []
        
        cur.execute('''
            SELECT symbol, timeframe, error_message, last_update
            FROM backfill_status
            WHERE status = 'ERROR'
            ORDER BY last_update DESC
        ''')
        
        results = []
        for row in cur.fetchall():
            results.append({
                'symbol': row[0],
                'timeframe': row[1],
                'error_message': row[2] or 'Unknown error',
                'last_update': row[3]
            })
        return results
    except Exception:
        return []
    finally:
        conn.close()


def clear_historical_data():
    """Clear all historical data and backfill status to start fresh"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        
        # Drop historical tables if they exist
        cur.execute("DROP TABLE IF EXISTS historical_ohlcv")
        cur.execute("DROP TABLE IF EXISTS backfill_status")
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error clearing historical data: {e}")
        return False
    finally:
        conn.close()


def retry_failed_downloads():
    """Reset ERROR status to PENDING so backfill will retry them"""
    conn = get_connection()
    if not conn:
        return 0
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backfill_status'")
        if not cur.fetchone():
            return 0
        
        # Reset ERROR to PENDING
        cur.execute('''
            UPDATE backfill_status 
            SET status = 'PENDING', error_message = NULL, last_update = datetime('now')
            WHERE status = 'ERROR'
        ''')
        
        count = cur.rowcount
        conn.commit()
        return count
    except Exception as e:
        print(f"Error retrying failed downloads: {e}")
        return 0
    finally:
        conn.close()
