"""
🗄️ ML Labels Schema and Dataset Export

Table creation and dataset export functions.
"""

import streamlit as st
import pandas as pd
from ..connection import get_connection


def create_ml_labels_table():
    """Create ml_training_labels table if not exists."""
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS ml_training_labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL, timeframe TEXT NOT NULL, timestamp TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL, volume REAL,
                score_long REAL, realized_return_long REAL, mfe_long REAL, mae_long REAL,
                bars_held_long INTEGER, exit_type_long TEXT,
                score_short REAL, realized_return_short REAL, mfe_short REAL, mae_short REAL,
                bars_held_short INTEGER, exit_type_short TEXT,
                trailing_stop_pct REAL, max_bars INTEGER, time_penalty_lambda REAL, trading_cost REAL,
                generated_at TEXT,
                UNIQUE(symbol, timeframe, timestamp)
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ml_labels_symbol_tf ON ml_training_labels(symbol, timeframe)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ml_labels_timestamp ON ml_training_labels(timestamp)')
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating table: {e}")
        return False
    finally:
        conn.close()


@st.cache_data(ttl=300, show_spinner=False)
def get_ml_labels_table_schema():
    """Get schema of ml_training_labels table (cached 5min)."""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_training_labels'")
        if not cur.fetchone():
            return []
        cur.execute("PRAGMA table_info(ml_training_labels)")
        return [{'cid': r[0], 'name': r[1], 'type': r[2], 'notnull': r[3], 'default': r[4], 'pk': r[5]} for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def get_ml_training_dataset(symbol: str = None, timeframe: str = None, symbols: list = None, limit: int = None):
    """Get ML training dataset by joining features and labels. Returns (DataFrame, stats, errors)."""
    conn = get_connection()
    if not conn:
        return pd.DataFrame(), {'error': 'No connection'}, ['No connection']
    
    try:
        cur = conn.cursor()
        errors = []
        
        # Check tables
        for table in ['training_data', 'ml_training_labels']:
            cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cur.fetchone():
                return pd.DataFrame(), {'error': f'{table} not found'}, [f'{table} not found']
        
        # Get indicator columns
        cur.execute("PRAGMA table_info(training_data)")
        exclude = {'id', 'symbol', 'timeframe', 'timestamp', 'fetched_at', 'interpolated', 'open', 'high', 'low', 'close', 'volume'}
        indicator_cols = [r[1] for r in cur.fetchall() if r[1] not in exclude]
        ind_select = ', '.join([f'h.{c}' for c in indicator_cols])
        
        query = f'''
            SELECT l.timestamp, l.symbol, l.timeframe, l.open, l.high, l.low, l.close, l.volume,
                {ind_select},
                l.score_long, l.score_short, l.realized_return_long, l.realized_return_short,
                l.mfe_long, l.mae_long, l.mfe_short, l.mae_short,
                l.bars_held_long, l.bars_held_short, l.exit_type_long, l.exit_type_short
            FROM ml_training_labels l
            INNER JOIN training_data h ON l.symbol = h.symbol AND l.timeframe = h.timeframe AND l.timestamp = h.timestamp
        '''
        
        conditions, params = [], []
        if symbol:
            conditions.append('l.symbol = ?')
            params.append(symbol)
        elif symbols:
            conditions.append(f'l.symbol IN ({",".join(["?" for _ in symbols])})')
            params.extend(symbols)
        if timeframe:
            conditions.append('l.timeframe = ?')
            params.append(timeframe)
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        query += ' ORDER BY l.symbol, l.timeframe, l.timestamp'
        if limit:
            query += f' LIMIT {int(limit)}'
        
        df = pd.read_sql_query(query, conn, params=params if params else None)
        if len(df) == 0:
            return pd.DataFrame(), {'total_rows': 0}, ['No data found']
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filter NaN rows
        rows_before = len(df)
        clean_dfs = []
        for (sym, tf), group in df.groupby(['symbol', 'timeframe']):
            group = group.sort_values('timestamp').reset_index(drop=True)
            for idx in range(len(group)):
                if not group.iloc[idx].isnull().any():
                    clean_dfs.append(group.iloc[idx:].copy())
                    break
        df = pd.concat(clean_dfs, ignore_index=True) if clean_dfs else pd.DataFrame()
        
        if rows_before - len(df) > 0:
            errors.append(f"Filtered {rows_before - len(df)} warm-up rows")
        
        stats = {
            'total_rows': len(df),
            'symbols': df['symbol'].nunique() if len(df) > 0 else 0,
            'features_count': len(indicator_cols),
            'columns_with_nulls': df.isnull().sum().gt(0).sum() if len(df) > 0 else 0
        }
        return df, stats, errors
    except Exception as e:
        return pd.DataFrame(), {'error': str(e)}, [str(e)]
    finally:
        conn.close()


def get_dataset_availability():
    """Get availability stats for ML dataset."""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        for table in ['training_data', 'ml_training_labels']:
            cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cur.fetchone():
                return []
        
        cur.execute('''
            SELECT COALESCE(h.symbol, l.symbol), COALESCE(h.timeframe, l.timeframe),
                COALESCE(h.cnt, 0), COALESCE(l.cnt, 0), COALESCE(j.cnt, 0)
            FROM (SELECT symbol, timeframe, COUNT(*) as cnt FROM training_data GROUP BY symbol, timeframe) h
            FULL OUTER JOIN (SELECT symbol, timeframe, COUNT(*) as cnt FROM ml_training_labels GROUP BY symbol, timeframe) l
                ON h.symbol = l.symbol AND h.timeframe = l.timeframe
            LEFT JOIN (
                SELECT h.symbol, h.timeframe, COUNT(*) as cnt FROM training_data h
                INNER JOIN ml_training_labels l ON h.symbol = l.symbol AND h.timeframe = l.timeframe AND h.timestamp = l.timestamp
                GROUP BY h.symbol, h.timeframe
            ) j ON COALESCE(h.symbol, l.symbol) = j.symbol AND COALESCE(h.timeframe, l.timeframe) = j.timeframe
        ''')
        return [{'symbol': r[0], 'timeframe': r[1], 'historical': r[2], 'labels': r[3], 'joinable': r[4], 'ready': r[4] > 0} for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()
