"""
ML Training Labels functions
"""

import streamlit as st
import pandas as pd
from .connection import get_connection


def create_ml_labels_table():
    """Create table for ML training labels if not exists"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        
        # Create ml_training_labels table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS ml_training_labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                
                -- OHLCV base data
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                
                -- LONG labels
                score_long REAL,
                realized_return_long REAL,
                mfe_long REAL,
                mae_long REAL,
                bars_held_long INTEGER,
                exit_type_long TEXT,
                
                -- SHORT labels
                score_short REAL,
                realized_return_short REAL,
                mfe_short REAL,
                mae_short REAL,
                bars_held_short INTEGER,
                exit_type_short TEXT,
                
                -- Config used
                trailing_stop_pct REAL,
                max_bars INTEGER,
                time_penalty_lambda REAL,
                trading_cost REAL,
                
                -- Metadata
                generated_at TEXT,
                
                UNIQUE(symbol, timeframe, timestamp)
            )
        ''')
        
        # Create indexes for fast queries
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ml_labels_symbol_tf ON ml_training_labels(symbol, timeframe)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ml_labels_timestamp ON ml_training_labels(timestamp)')
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating ml_training_labels table: {e}")
        return False
    finally:
        conn.close()


def _safe_float(value, default=0.0):
    """Convert value to float safely, handling NaN/None"""
    if value is None:
        return default
    try:
        f = float(value)
        if pd.isna(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


def _safe_int(value, default=0):
    """Convert value to int safely, handling NaN/None"""
    if value is None:
        return default
    try:
        f = float(value)
        if pd.isna(f):
            return default
        return int(f)
    except (ValueError, TypeError):
        return default


def save_ml_labels_to_db(symbol: str, timeframe: str, ohlcv_df: pd.DataFrame, 
                         labels_df: pd.DataFrame, config: dict):
    """
    Save ML training labels to database.
    
    Args:
        symbol: Trading pair symbol
        timeframe: Candle timeframe (15m, 1h)
        ohlcv_df: DataFrame with OHLCV data (index=timestamp)
        labels_df: DataFrame with labels (same index)
        config: Dict with trailing_stop_pct, max_bars, time_penalty_lambda, trading_cost
    
    Returns:
        Number of rows saved
    """
    conn = get_connection()
    if not conn:
        print(f"Error: No database connection")
        return 0
    
    try:
        # Ensure table exists
        create_ml_labels_table()
        
        cur = conn.cursor()
        
        # Delete existing labels for this symbol/timeframe
        cur.execute('''
            DELETE FROM ml_training_labels 
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        
        # Prepare data
        generated_at = pd.Timestamp.now().isoformat()
        rows_saved = 0
        skipped = 0
        
        # Get common indices
        common_indices = ohlcv_df.index.intersection(labels_df.index)
        
        for idx in common_indices:
            # Get OHLCV
            ohlcv_row = ohlcv_df.loc[idx]
            label_row = labels_df.loc[idx]
            
            # Skip invalid labels
            exit_type_col = f'exit_type_long_{timeframe}'
            exit_type_val = label_row.get(exit_type_col, None) if hasattr(label_row, 'get') else (label_row[exit_type_col] if exit_type_col in label_row.index else None)
            
            if exit_type_val == 'invalid':
                skipped += 1
                continue
            
            # Helper to safely get label values
            def get_label_val(col_suffix, is_int=False):
                col_name = f'{col_suffix}_{timeframe}'
                if hasattr(label_row, 'get'):
                    val = label_row.get(col_name, 0)
                elif col_name in label_row.index:
                    val = label_row[col_name]
                else:
                    val = 0
                return _safe_int(val) if is_int else _safe_float(val)
            
            try:
                # Insert row
                cur.execute('''
                    INSERT INTO ml_training_labels (
                        symbol, timeframe, timestamp,
                        open, high, low, close, volume,
                        score_long, realized_return_long, mfe_long, mae_long, bars_held_long, exit_type_long,
                        score_short, realized_return_short, mfe_short, mae_short, bars_held_short, exit_type_short,
                        trailing_stop_pct, max_bars, time_penalty_lambda, trading_cost,
                        generated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol, timeframe, str(idx),
                    _safe_float(ohlcv_row['open']), _safe_float(ohlcv_row['high']), 
                    _safe_float(ohlcv_row['low']), _safe_float(ohlcv_row['close']), 
                    _safe_float(ohlcv_row['volume']),
                    get_label_val('score_long'),
                    get_label_val('realized_return_long'),
                    get_label_val('mfe_long'),
                    get_label_val('mae_long'),
                    get_label_val('bars_held_long', is_int=True),
                    str(exit_type_val or ''),
                    get_label_val('score_short'),
                    get_label_val('realized_return_short'),
                    get_label_val('mfe_short'),
                    get_label_val('mae_short'),
                    get_label_val('bars_held_short', is_int=True),
                    str(label_row.get(f'exit_type_short_{timeframe}', '') if hasattr(label_row, 'get') else (label_row[f'exit_type_short_{timeframe}'] if f'exit_type_short_{timeframe}' in label_row.index else '')),
                    _safe_float(config.get('trailing_stop_pct', 0)),
                    _safe_int(config.get('max_bars', 0)),
                    _safe_float(config.get('time_penalty_lambda', 0)),
                    _safe_float(config.get('trading_cost', 0)),
                    generated_at
                ))
                rows_saved += 1
            except Exception as row_error:
                print(f"Error saving row at {idx}: {row_error}")
                continue
        
        conn.commit()
        return rows_saved
    except Exception as e:
        print(f"Error saving ML labels: {e}")
        import traceback
        traceback.print_exc()
        return 0
    finally:
        conn.close()


@st.cache_data(ttl=60, show_spinner=False)
def get_ml_labels_stats():
    """Get statistics for saved ML training labels (cached 60s)"""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_training_labels'")
        if not cur.fetchone():
            return {'exists': False}
        
        cur.execute('''
            SELECT 
                COUNT(DISTINCT symbol) as symbols,
                COUNT(DISTINCT timeframe) as timeframes,
                COUNT(*) as total_labels,
                AVG(score_long) as avg_score_long,
                AVG(score_short) as avg_score_short,
                SUM(CASE WHEN score_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pct_positive_long,
                MIN(timestamp) as min_date,
                MAX(timestamp) as max_date,
                MAX(generated_at) as last_generated
            FROM ml_training_labels
        ''')
        r = cur.fetchone()
        
        if r[0] == 0:
            return {'exists': True, 'empty': True}
        
        return {
            'exists': True,
            'empty': False,
            'symbols': r[0],
            'timeframes': r[1],
            'total_labels': r[2],
            'avg_score_long': r[3],
            'avg_score_short': r[4],
            'pct_positive_long': r[5],
            'min_date': r[6],
            'max_date': r[7],
            'last_generated': r[8]
        }
    except Exception as e:
        return {'exists': False, 'error': str(e)}
    finally:
        conn.close()


@st.cache_data(ttl=60, show_spinner=False)
def get_ml_labels_by_symbol():
    """Get ML labels info grouped by symbol (cached 60s)"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_training_labels'")
        if not cur.fetchone():
            return []
        
        cur.execute('''
            SELECT 
                symbol,
                timeframe,
                COUNT(*) as total_labels,
                AVG(score_long) as avg_score_long,
                AVG(score_short) as avg_score_short,
                SUM(CASE WHEN score_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pct_positive,
                MIN(timestamp) as from_date,
                MAX(timestamp) as to_date,
                MAX(generated_at) as generated_at
            FROM ml_training_labels
            GROUP BY symbol, timeframe
            ORDER BY symbol, timeframe
        ''')
        
        results = []
        for row in cur.fetchall():
            results.append({
                'symbol': row[0],
                'timeframe': row[1],
                'total_labels': row[2],
                'avg_score_long': row[3],
                'avg_score_short': row[4],
                'pct_positive': row[5],
                'from_date': row[6],
                'to_date': row[7],
                'generated_at': row[8]
            })
        return results
    except Exception:
        return []
    finally:
        conn.close()


def get_ml_labels(symbol: str, timeframe: str, limit: int = 5000):
    """Get ML labels from database for a symbol/timeframe"""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    try:
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_training_labels'")
        if not cur.fetchone():
            return pd.DataFrame()
        
        query = '''
            SELECT 
                timestamp, open, high, low, close, volume,
                score_long, realized_return_long, mfe_long, mae_long, bars_held_long, exit_type_long,
                score_short, realized_return_short, mfe_short, mae_short, bars_held_short, exit_type_short
            FROM ml_training_labels
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
        '''
        
        df = pd.read_sql_query(query, conn, params=(symbol, timeframe, limit))
        
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            df.set_index('timestamp', inplace=True)
        
        return df
    except Exception as e:
        print(f"Error getting ML labels: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_ml_training_dataset(symbol: str = None, timeframe: str = None, 
                            symbols: list = None, limit: int = None):
    """
    Get complete ML training dataset with JOIN between training_data (features) 
    and ml_training_labels (labels/targets).
    
    This is the main function for exporting data ready for ML training.
    
    Args:
        symbol: Single symbol to filter (optional)
        timeframe: Timeframe to filter (optional, '15m' or '1h')
        symbols: List of symbols to include (optional)
        limit: Max rows to return (optional)
    
    Returns:
        Tuple of (DataFrame, stats_dict, errors_list)
        - DataFrame with features + labels
        - stats_dict with dataset statistics
        - errors_list with any warnings/errors
    """
    conn = get_connection()
    if not conn:
        return pd.DataFrame(), {'error': 'No database connection'}, ['No database connection']
    
    try:
        cur = conn.cursor()
        errors = []
        
        # Check if tables exist
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_data'")
        if not cur.fetchone():
            return pd.DataFrame(), {'error': 'training_data table not found'}, ['training_data table not found']
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_training_labels'")
        if not cur.fetchone():
            return pd.DataFrame(), {'error': 'ml_training_labels table not found'}, ['ml_training_labels table not found']
        
        # Get column names from training_data (indicators)
        cur.execute("PRAGMA table_info(training_data)")
        historical_cols = [row[1] for row in cur.fetchall()]
        
        # Columns to exclude from historical (will get OHLCV from labels, avoid duplicates)
        exclude_cols = {'id', 'symbol', 'timeframe', 'timestamp', 'fetched_at', 'interpolated',
                       'open', 'high', 'low', 'close', 'volume'}  # OHLCV comes from labels
        
        # Indicator columns to select
        indicator_cols = [c for c in historical_cols if c not in exclude_cols]
        
        # Build the JOIN query
        # Labels table has: symbol, timeframe, timestamp, OHLCV, labels
        # Historical table has: symbol, timeframe, timestamp, OHLCV, indicators
        
        indicator_select = ', '.join([f'h.{c}' for c in indicator_cols])
        
        query = f'''
            SELECT 
                l.timestamp,
                l.symbol,
                l.timeframe,
                l.open,
                l.high,
                l.low,
                l.close,
                l.volume,
                
                -- Indicators (features)
                {indicator_select},
                
                -- Labels (targets)
                l.score_long,
                l.score_short,
                l.realized_return_long,
                l.realized_return_short,
                l.mfe_long,
                l.mae_long,
                l.mfe_short,
                l.mae_short,
                l.bars_held_long,
                l.bars_held_short,
                l.exit_type_long,
                l.exit_type_short,
                l.trailing_stop_pct,
                l.max_bars,
                l.time_penalty_lambda,
                l.trading_cost
                
            FROM ml_training_labels l
            INNER JOIN training_data h 
                ON l.symbol = h.symbol 
                AND l.timeframe = h.timeframe 
                AND l.timestamp = h.timestamp
        '''
        
        # Add WHERE conditions
        conditions = []
        params = []
        
        if symbol:
            conditions.append('l.symbol = ?')
            params.append(symbol)
        elif symbols and len(symbols) > 0:
            placeholders = ','.join(['?' for _ in symbols])
            conditions.append(f'l.symbol IN ({placeholders})')
            params.extend(symbols)
        
        if timeframe:
            conditions.append('l.timeframe = ?')
            params.append(timeframe)
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += ' ORDER BY l.symbol, l.timeframe, l.timestamp ASC'
        
        if limit:
            query += f' LIMIT {int(limit)}'
        
        # Execute query
        df = pd.read_sql_query(query, conn, params=params if params else None)
        
        if len(df) == 0:
            return pd.DataFrame(), {'total_rows': 0, 'error': 'No matching data found'}, ['No matching data found']
        
        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # === FILTER OUT NaN ROWS (warm-up period for indicators) ===
        rows_before = len(df)
        
        # Find columns with nulls before filtering
        null_counts_before = df.isnull().sum()
        cols_with_nulls_before = null_counts_before[null_counts_before > 0].index.tolist()
        
        # For each symbol/timeframe group, find the first row with NO nulls
        # and keep only from that row onwards (ensures consecutive clean data)
        clean_dfs = []
        
        for (sym, tf), group in df.groupby(['symbol', 'timeframe']):
            group = group.sort_values('timestamp').reset_index(drop=True)
            
            # Find first row where ALL columns are non-null
            first_complete_idx = None
            for idx in range(len(group)):
                if not group.iloc[idx].isnull().any():
                    first_complete_idx = idx
                    break
            
            if first_complete_idx is not None:
                # Keep from first complete row onwards
                clean_group = group.iloc[first_complete_idx:].copy()
                clean_dfs.append(clean_group)
        
        if clean_dfs:
            df = pd.concat(clean_dfs, ignore_index=True)
        else:
            df = pd.DataFrame()
        
        rows_removed = rows_before - len(df)
        
        if rows_removed > 0:
            errors.append(f"Filtered {rows_removed:,} warm-up rows (first rows with NaN in: {', '.join(cols_with_nulls_before[:5])}{'...' if len(cols_with_nulls_before) > 5 else ''})")
        
        # === VERIFY TIMESTAMP CONSECUTIVITY ===
        gaps_found = []
        timeframe_minutes = {'15m': 15, '1h': 60, '4h': 240, '1d': 1440}
        
        for (sym, tf), group in df.groupby(['symbol', 'timeframe']):
            group = group.sort_values('timestamp')
            expected_delta = pd.Timedelta(minutes=timeframe_minutes.get(tf, 15))
            
            # Calculate time differences
            time_diffs = group['timestamp'].diff()
            
            # Find gaps (where diff != expected)
            gap_mask = (time_diffs.notna()) & (time_diffs != expected_delta)
            gap_rows = group[gap_mask]
            
            for _, row in gap_rows.iterrows():
                gaps_found.append({
                    'symbol': sym,
                    'timeframe': tf,
                    'timestamp': row['timestamp'],
                    'actual_gap': time_diffs.loc[row.name]
                })
        
        # Calculate statistics
        stats = {
            'total_rows': len(df),
            'symbols': df['symbol'].nunique(),
            'timeframes': df['timeframe'].nunique(),
            'date_from': df['timestamp'].min().strftime('%Y-%m-%d %H:%M'),
            'date_to': df['timestamp'].max().strftime('%Y-%m-%d %H:%M'),
            'features_count': len(indicator_cols),
            'labels_count': 12,  # score_long/short, mfe/mae, etc
            'total_columns': len(df.columns),
        }
        
        # Data quality checks
        null_counts = df.isnull().sum()
        cols_with_nulls = null_counts[null_counts > 0]
        
        if len(cols_with_nulls) > 0:
            stats['columns_with_nulls'] = len(cols_with_nulls)
            stats['null_percentage'] = (cols_with_nulls.sum() / (len(df) * len(df.columns)) * 100)
            errors.append(f"Warning: {len(cols_with_nulls)} columns have null values")
        else:
            stats['columns_with_nulls'] = 0
            stats['null_percentage'] = 0
        
        # Score distribution
        if 'score_long' in df.columns:
            stats['avg_score_long'] = df['score_long'].mean()
            stats['pct_positive_long'] = (df['score_long'] > 0).mean() * 100
            stats['pct_negative_long'] = (df['score_long'] < 0).mean() * 100
        
        if 'score_short' in df.columns:
            stats['avg_score_short'] = df['score_short'].mean()
            stats['pct_positive_short'] = (df['score_short'] > 0).mean() * 100
        
        # Per-symbol stats
        symbol_counts = df.groupby('symbol').size().to_dict()
        stats['rows_per_symbol'] = symbol_counts
        
        # Add gap stats
        stats['gaps_count'] = len(gaps_found)
        stats['is_consecutive'] = len(gaps_found) == 0
        
        if gaps_found:
            # Show first 3 gaps as warning
            gap_msgs = []
            for gap in gaps_found[:3]:
                gap_msgs.append(f"{gap['symbol']} {gap['timeframe']}: gap of {gap['actual_gap']} at {gap['timestamp']}")
            errors.append(f"⚠️ {len(gaps_found)} gaps in timeline: {'; '.join(gap_msgs)}")
        
        return df, stats, errors
        
    except Exception as e:
        import traceback
        error_msg = f"Error in get_ml_training_dataset: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return pd.DataFrame(), {'error': error_msg}, [error_msg]
    finally:
        conn.close()


def get_dataset_availability():
    """
    Get availability stats for ML dataset: which symbols have both historical data AND labels.
    
    Returns:
        List of dicts with symbol info and availability status
    """
    conn = get_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        
        # Check if tables exist
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_data'")
        if not cur.fetchone():
            return []
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_training_labels'")
        if not cur.fetchone():
            return []
        
        # Get availability for each symbol/timeframe
        query = '''
            WITH historical_stats AS (
                SELECT 
                    symbol,
                    timeframe,
                    COUNT(*) as historical_candles,
                    MIN(timestamp) as h_from,
                    MAX(timestamp) as h_to
                FROM training_data
                GROUP BY symbol, timeframe
            ),
            labels_stats AS (
                SELECT 
                    symbol,
                    timeframe,
                    COUNT(*) as labels_count,
                    MIN(timestamp) as l_from,
                    MAX(timestamp) as l_to
                FROM ml_training_labels
                GROUP BY symbol, timeframe
            ),
            joined_count AS (
                SELECT 
                    h.symbol,
                    h.timeframe,
                    COUNT(*) as joinable_rows
                FROM training_data h
                INNER JOIN ml_training_labels l 
                    ON h.symbol = l.symbol 
                    AND h.timeframe = l.timeframe 
                    AND h.timestamp = l.timestamp
                GROUP BY h.symbol, h.timeframe
            )
            SELECT 
                COALESCE(h.symbol, l.symbol) as symbol,
                COALESCE(h.timeframe, l.timeframe) as timeframe,
                COALESCE(h.historical_candles, 0) as historical_candles,
                COALESCE(l.labels_count, 0) as labels_count,
                COALESCE(j.joinable_rows, 0) as joinable_rows,
                h.h_from,
                h.h_to,
                l.l_from,
                l.l_to,
                COALESCE(ts.rank, 999) as rank
            FROM historical_stats h
            FULL OUTER JOIN labels_stats l 
                ON h.symbol = l.symbol AND h.timeframe = l.timeframe
            LEFT JOIN joined_count j 
                ON COALESCE(h.symbol, l.symbol) = j.symbol 
                AND COALESCE(h.timeframe, l.timeframe) = j.timeframe
            LEFT JOIN top_symbols ts 
                ON COALESCE(h.symbol, l.symbol) = ts.symbol
            ORDER BY COALESCE(ts.rank, 999) ASC, COALESCE(h.symbol, l.symbol), COALESCE(h.timeframe, l.timeframe)
        '''
        
        cur.execute(query)
        
        results = []
        for row in cur.fetchall():
            results.append({
                'symbol': row[0],
                'timeframe': row[1],
                'historical_candles': row[2] or 0,
                'labels_count': row[3] or 0,
                'joinable_rows': row[4] or 0,
                'h_from': row[5],
                'h_to': row[6],
                'l_from': row[7],
                'l_to': row[8],
                'rank': row[9] or 999,
                'ready': (row[4] or 0) > 0  # Has joinable data
            })
        
        return results
        
    except Exception as e:
        print(f"Error in get_dataset_availability: {e}")
        return []
    finally:
        conn.close()


def clear_ml_labels(symbol: str = None, timeframe: str = None):
    """Clear ML labels from database (all or filtered by symbol/timeframe)"""
    conn = get_connection()
    if not conn:
        return 0
    try:
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_training_labels'")
        if not cur.fetchone():
            return 0
        
        if symbol and timeframe:
            cur.execute('DELETE FROM ml_training_labels WHERE symbol = ? AND timeframe = ?', 
                       (symbol, timeframe))
        elif symbol:
            cur.execute('DELETE FROM ml_training_labels WHERE symbol = ?', (symbol,))
        else:
            cur.execute('DELETE FROM ml_training_labels')
        
        count = cur.rowcount
        conn.commit()
        return count
    except Exception as e:
        print(f"Error clearing ML labels: {e}")
        return 0
    finally:
        conn.close()


@st.cache_data(ttl=300, show_spinner=False)
def get_ml_labels_table_schema():
    """Get the schema of ml_training_labels table (cached 5min)"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_training_labels'")
        if not cur.fetchone():
            return []
        
        cur.execute("PRAGMA table_info(ml_training_labels)")
        columns = []
        for row in cur.fetchall():
            columns.append({
                'cid': row[0],
                'name': row[1],
                'type': row[2],
                'notnull': row[3],
                'default': row[4],
                'pk': row[5]
            })
        return columns
    except Exception:
        return []
    finally:
        conn.close()


@st.cache_data(ttl=60, show_spinner=False)
def get_available_symbols_for_labels():
    """Get list of symbols that have ML labels in database (cached 60s)"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_training_labels'")
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
    """
    Get per-symbol inventory with label counts and scores, ordered by volume rank.
    Similar to get_historical_inventory but for ML labels. (cached 60s)
    """
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_training_labels'")
        if not cur.fetchone():
            return []
        
        # Get all symbols with their label stats, joined with top_symbols for ranking
        query = '''
            WITH label_stats AS (
                SELECT 
                    symbol,
                    timeframe,
                    COUNT(*) as total_labels,
                    ROUND(AVG(score_long) * 100, 4) as avg_score_long,
                    ROUND(AVG(score_short) * 100, 4) as avg_score_short,
                    ROUND(SUM(CASE WHEN score_long > 0 THEN 1.0 ELSE 0.0 END) / COUNT(*) * 100, 1) as pct_positive_long,
                    ROUND(SUM(CASE WHEN score_short > 0 THEN 1.0 ELSE 0.0 END) / COUNT(*) * 100, 1) as pct_positive_short,
                    MIN(timestamp) as from_date,
                    MAX(timestamp) as to_date,
                    MAX(generated_at) as generated_at
                FROM ml_training_labels
                GROUP BY symbol, timeframe
            ),
            symbol_summary AS (
                SELECT 
                    s.symbol,
                    MAX(CASE WHEN s.timeframe = '15m' THEN s.total_labels ELSE 0 END) as labels_15m,
                    MAX(CASE WHEN s.timeframe = '1h' THEN s.total_labels ELSE 0 END) as labels_1h,
                    MAX(CASE WHEN s.timeframe = '15m' THEN s.avg_score_long ELSE NULL END) as avg_score_long_15m,
                    MAX(CASE WHEN s.timeframe = '1h' THEN s.avg_score_long ELSE NULL END) as avg_score_long_1h,
                    MAX(CASE WHEN s.timeframe = '15m' THEN s.pct_positive_long ELSE NULL END) as pct_positive_15m,
                    MAX(CASE WHEN s.timeframe = '1h' THEN s.pct_positive_long ELSE NULL END) as pct_positive_1h,
                    MAX(s.from_date) as from_date,
                    MAX(s.to_date) as to_date,
                    MAX(s.generated_at) as generated_at
                FROM label_stats s
                GROUP BY s.symbol
            )
            SELECT 
                COALESCE(ts.rank, 999) as rank,
                ss.symbol,
                ss.labels_15m,
                ss.labels_1h,
                ss.avg_score_long_15m,
                ss.avg_score_long_1h,
                ss.pct_positive_15m,
                ss.pct_positive_1h,
                ss.from_date,
                ss.to_date,
                ss.generated_at
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
                'labels_15m': row[2] or 0,
                'labels_1h': row[3] or 0,
                'avg_score_long_15m': row[4],
                'avg_score_long_1h': row[5],
                'pct_positive_15m': row[6],
                'pct_positive_1h': row[7],
                'from_date': row[8],
                'to_date': row[9],
                'generated_at': row[10]
            })
        return results
    except Exception as e:
        print(f"Error in get_ml_labels_inventory: {e}")
        return []
    finally:
        conn.close()


def get_ml_labels_full(symbol: str = None, timeframe: str = None, limit: int = 10000):
    """
    Get ML labels with all columns for Database Explorer.
    
    Args:
        symbol: Filter by symbol (optional)
        timeframe: Filter by timeframe (optional)
        limit: Max rows to return
    
    Returns:
        DataFrame with all label columns
    """
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    try:
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_training_labels'")
        if not cur.fetchone():
            return pd.DataFrame()
        
        # Build query with optional filters
        query = 'SELECT * FROM ml_training_labels'
        params = []
        
        conditions = []
        if symbol:
            conditions.append('symbol = ?')
            params.append(symbol)
        if timeframe:
            conditions.append('timeframe = ?')
            params.append(timeframe)
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += f' ORDER BY timestamp DESC LIMIT {limit}'
        
        df = pd.read_sql_query(query, conn, params=params if params else None)
        
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
        
        return df
    except Exception as e:
        print(f"Error getting ML labels: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
