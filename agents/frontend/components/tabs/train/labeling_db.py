"""
🏷️ Labeling Database Functions

Database operations for training labels:
- Create/manage training_labels table
- Query training_data
- Save generated labels
- Create VIEW for XGBoost
"""

import pandas as pd
from database import get_connection


def get_training_features_symbols(timeframe: str) -> list:
    """Get only symbols with >= 95% data completeness for BOTH timeframes"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        expected_15m = 35000
        expected_1h = 8760
        threshold = 0.95
        
        cur.execute('''
            SELECT symbol
            FROM (
                SELECT 
                    symbol,
                    SUM(CASE WHEN timeframe = '15m' THEN 1 ELSE 0 END) as candles_15m,
                    SUM(CASE WHEN timeframe = '1h' THEN 1 ELSE 0 END) as candles_1h
                FROM training_data
                GROUP BY symbol
            )
            WHERE 
                CAST(candles_15m AS REAL) / ? >= ? 
                AND CAST(candles_1h AS REAL) / ? >= ?
            ORDER BY symbol
        ''', (expected_15m, threshold, expected_1h, threshold))
        
        return [r[0] for r in cur.fetchall()]
    except Exception as e:
        return []
    finally:
        conn.close()


def get_training_features_data(symbol: str, timeframe: str) -> pd.DataFrame:
    """Load data from training_data for a specific symbol"""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    try:
        df = pd.read_sql_query('''
            SELECT * FROM training_data 
            WHERE symbol=? AND timeframe=?
            ORDER BY timestamp
        ''', conn, params=(symbol, timeframe))
        
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        
        return df
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()


def get_training_labels_stats():
    """Get stats from training_labels table"""
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_labels'")
        if not cur.fetchone():
            return None
        
        cur.execute('''
            SELECT 
                COUNT(DISTINCT symbol) as symbols,
                COUNT(*) as total_rows,
                MIN(timestamp) as min_date,
                MAX(timestamp) as max_date,
                timeframe,
                AVG(score_long) as avg_score_long,
                AVG(score_short) as avg_score_short
            FROM training_labels
            GROUP BY timeframe
        ''')
        
        results = {}
        for row in cur.fetchall():
            results[row[4]] = {
                'symbols': row[0],
                'total_rows': row[1],
                'min_date': row[2],
                'max_date': row[3],
                'avg_score_long': row[5],
                'avg_score_short': row[6]
            }
        return results
    except Exception as e:
        return None
    finally:
        conn.close()


def create_training_labels_table():
    """Create training_labels table - LABELS ONLY (no OHLCV)"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        
        cur.execute('DROP TABLE IF EXISTS training_labels')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS training_labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                score_long REAL,
                score_short REAL,
                realized_return_long REAL,
                realized_return_short REAL,
                mfe_long REAL,
                mfe_short REAL,
                mae_long REAL,
                mae_short REAL,
                bars_held_long INTEGER,
                bars_held_short INTEGER,
                exit_type_long TEXT,
                exit_type_short TEXT,
                atr_pct REAL,
                UNIQUE(symbol, timeframe, timestamp)
            )
        ''')
        
        cur.execute('CREATE INDEX IF NOT EXISTS idx_tl_symbol_tf_ts ON training_labels(symbol, timeframe, timestamp)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_tl_score_long ON training_labels(score_long)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_tl_score_short ON training_labels(score_short)')
        
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()


def create_xgb_training_view():
    """Create VIEW v_xgb_training for XGBoost training - includes ALL 21 features"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        
        cur.execute('DROP VIEW IF EXISTS v_xgb_training')
        
        # Include ALL 21 features: 5 OHLCV + 16 technical indicators
        cur.execute('''
            CREATE VIEW v_xgb_training AS
            SELECT
                d.symbol, d.timeframe, d.timestamp,
                -- OHLCV (5 features)
                d.open, d.high, d.low, d.close, d.volume,
                -- Moving Averages (4 features)
                d.sma_20, d.sma_50, d.ema_12, d.ema_26,
                -- Bollinger Bands (3 features)
                d.bb_upper, d.bb_middle, d.bb_lower,
                -- Momentum indicators (4 features)
                d.rsi, d.macd, d.macd_signal, d.macd_hist,
                -- Other indicators (5 features)
                d.atr, d.adx, d.cci, d.willr, d.obv,
                -- Labels
                l.score_long, l.score_short,
                l.realized_return_long, l.realized_return_short,
                l.mfe_long, l.mfe_short, l.mae_long, l.mae_short,
                l.bars_held_long, l.bars_held_short,
                l.exit_type_long, l.exit_type_short,
                l.atr_pct
            FROM training_data d
            INNER JOIN training_labels l
                ON d.symbol = l.symbol
               AND d.timeframe = l.timeframe
               AND d.timestamp = l.timestamp
        ''')
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating VIEW: {e}")
        return False
    finally:
        conn.close()


def get_label_statistics(timeframe: str) -> dict:
    """Get statistics about generated labels"""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        
        cur.execute('''
            SELECT 
                COUNT(*) as total,
                AVG(score_long) as avg_score_long,
                AVG(score_short) as avg_score_short,
                SUM(CASE WHEN score_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pct_positive_long,
                SUM(CASE WHEN score_short > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pct_positive_short,
                AVG(realized_return_long) as avg_return_long,
                AVG(realized_return_short) as avg_return_short,
                AVG(bars_held_long) as avg_bars_long,
                AVG(bars_held_short) as avg_bars_short,
                SUM(CASE WHEN exit_type_long = 'trailing' THEN 1 ELSE 0 END) as trailing_exits_long,
                SUM(CASE WHEN exit_type_long = 'time' THEN 1 ELSE 0 END) as time_exits_long
            FROM training_labels
            WHERE timeframe = ?
        ''', (timeframe,))
        
        row = cur.fetchone()
        if row and row[0] > 0:
            return {
                'total_samples': row[0],
                'avg_score_long': row[1],
                'avg_score_short': row[2],
                'pct_positive_long': row[3],
                'pct_positive_short': row[4],
                'avg_return_long': row[5] * 100,
                'avg_return_short': row[6] * 100,
                'avg_bars_long': row[7],
                'avg_bars_short': row[8],
                'trailing_exits_long': row[9],
                'time_exits_long': row[10]
            }
        return {}
    except Exception as e:
        return {}
    finally:
        conn.close()


__all__ = [
    'get_training_features_symbols',
    'get_training_features_data',
    'get_training_labels_stats',
    'create_training_labels_table',
    'create_xgb_training_view',
    'get_label_statistics'
]
