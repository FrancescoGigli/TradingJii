"""
📈 ML Labels Statistics

Statistics and inventory functions for ML labels.
"""

import streamlit as st
from ..connection import get_connection


@st.cache_data(ttl=60, show_spinner=False)
def get_ml_labels_stats():
    """Get statistics for saved ML training labels (cached 60s)."""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='ml_training_labels'"
        )
        if not cur.fetchone():
            return {'exists': False}
        
        cur.execute('''
            SELECT 
                COUNT(DISTINCT symbol) as symbols,
                COUNT(DISTINCT timeframe) as timeframes,
                COUNT(*) as total_labels,
                AVG(score_long) as avg_score_long,
                AVG(score_short) as avg_score_short,
                SUM(CASE WHEN score_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                MIN(timestamp), MAX(timestamp), MAX(generated_at)
            FROM ml_training_labels
        ''')
        r = cur.fetchone()
        
        if r[0] == 0:
            return {'exists': True, 'empty': True}
        
        return {
            'exists': True, 'empty': False,
            'symbols': r[0], 'timeframes': r[1], 'total_labels': r[2],
            'avg_score_long': r[3], 'avg_score_short': r[4],
            'pct_positive_long': r[5],
            'min_date': r[6], 'max_date': r[7], 'last_generated': r[8]
        }
    except Exception as e:
        return {'exists': False, 'error': str(e)}
    finally:
        conn.close()


@st.cache_data(ttl=60, show_spinner=False)
def get_ml_labels_by_symbol():
    """Get ML labels info grouped by symbol (cached 60s)."""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='ml_training_labels'"
        )
        if not cur.fetchone():
            return []
        
        cur.execute('''
            SELECT symbol, timeframe, COUNT(*) as total_labels,
                AVG(score_long), AVG(score_short),
                SUM(CASE WHEN score_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                MIN(timestamp), MAX(timestamp), MAX(generated_at)
            FROM ml_training_labels
            GROUP BY symbol, timeframe
            ORDER BY symbol, timeframe
        ''')
        
        results = []
        for row in cur.fetchall():
            results.append({
                'symbol': row[0], 'timeframe': row[1], 'total_labels': row[2],
                'avg_score_long': row[3], 'avg_score_short': row[4],
                'pct_positive': row[5],
                'from_date': row[6], 'to_date': row[7], 'generated_at': row[8]
            })
        return results
    except Exception:
        return []
    finally:
        conn.close()


@st.cache_data(ttl=60, show_spinner=False)
def get_available_symbols_for_labels():
    """Get list of symbols with ML labels in database (cached 60s)."""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='ml_training_labels'"
        )
        if not cur.fetchone():
            return []
        
        cur.execute('SELECT DISTINCT symbol FROM ml_training_labels ORDER BY symbol')
        return [r[0] for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


@st.cache_data(ttl=60, show_spinner=False)
def get_ml_labels_inventory():
    """Get per-symbol inventory with label counts (cached 60s)."""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='ml_training_labels'"
        )
        if not cur.fetchone():
            return []
        
        query = '''
            WITH label_stats AS (
                SELECT symbol, timeframe, COUNT(*) as total_labels,
                    ROUND(AVG(score_long) * 100, 4) as avg_score_long,
                    ROUND(SUM(CASE WHEN score_long > 0 THEN 1.0 ELSE 0.0 END) / COUNT(*) * 100, 1) as pct_positive,
                    MIN(timestamp) as from_date, MAX(timestamp) as to_date,
                    MAX(generated_at) as generated_at
                FROM ml_training_labels
                GROUP BY symbol, timeframe
            ),
            symbol_summary AS (
                SELECT symbol,
                    MAX(CASE WHEN timeframe = '15m' THEN total_labels ELSE 0 END) as labels_15m,
                    MAX(CASE WHEN timeframe = '1h' THEN total_labels ELSE 0 END) as labels_1h,
                    MAX(CASE WHEN timeframe = '15m' THEN avg_score_long ELSE NULL END) as avg_score_15m,
                    MAX(CASE WHEN timeframe = '15m' THEN pct_positive ELSE NULL END) as pct_pos_15m,
                    MAX(from_date) as from_date, MAX(to_date) as to_date,
                    MAX(generated_at) as generated_at
                FROM label_stats GROUP BY symbol
            )
            SELECT COALESCE(ts.rank, 999), ss.*
            FROM symbol_summary ss
            LEFT JOIN top_symbols ts ON ss.symbol = ts.symbol
            ORDER BY COALESCE(ts.rank, 999)
        '''
        cur.execute(query)
        
        results = []
        for row in cur.fetchall():
            results.append({
                'rank': row[0], 'symbol': row[1],
                'labels_15m': row[2] or 0, 'labels_1h': row[3] or 0,
                'avg_score_long_15m': row[4], 'pct_positive_15m': row[5],
                'from_date': row[6], 'to_date': row[7], 'generated_at': row[8]
            })
        return results
    except Exception as e:
        print(f"Error in get_ml_labels_inventory: {e}")
        return []
    finally:
        conn.close()
