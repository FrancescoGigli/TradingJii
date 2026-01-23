"""
📊 ML Labels CRUD Operations

Basic read and delete operations for ML training labels.
"""

import pandas as pd
from ..connection import get_connection


def get_training_labels(
    timeframe: str = None, 
    symbol: str = None, 
    limit: int = None
) -> pd.DataFrame:
    """
    Get training labels from training_labels table.
    
    Args:
        timeframe: Filter by timeframe ('15m' or '1h')
        symbol: Filter by symbol (optional)
        limit: Max rows to return (optional)
    
    Returns:
        DataFrame with labels indexed by timestamp
    """
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        query = '''
            SELECT 
                timestamp, symbol, timeframe,
                score_long, score_short,
                realized_return_long, realized_return_short,
                mfe_long, mfe_short, mae_long, mae_short,
                bars_held_long, bars_held_short,
                exit_type_long, exit_type_short, atr_pct
            FROM training_labels
        '''
        
        conditions = []
        params = []
        
        if timeframe:
            conditions.append('timeframe = ?')
            params.append(timeframe)
        
        if symbol:
            conditions.append('symbol = ?')
            params.append(symbol)
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += ' ORDER BY timestamp'
        
        if limit:
            query += f' LIMIT {int(limit)}'
        
        df = pd.read_sql_query(query, conn, params=params if params else None)
        
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # Rename columns to match expected format
            tf = timeframe if timeframe else '15m'
            rename_map = {
                'score_long': f'score_long_{tf}',
                'score_short': f'score_short_{tf}',
                'realized_return_long': f'realized_return_long_{tf}',
                'realized_return_short': f'realized_return_short_{tf}',
                'mfe_long': f'mfe_long_{tf}',
                'mfe_short': f'mfe_short_{tf}',
                'mae_long': f'mae_long_{tf}',
                'mae_short': f'mae_short_{tf}',
                'bars_held_long': f'bars_held_long_{tf}',
                'bars_held_short': f'bars_held_short_{tf}',
                'exit_type_long': f'exit_type_long_{tf}',
                'exit_type_short': f'exit_type_short_{tf}',
                'atr_pct': f'atr_pct_{tf}'
            }
            df = df.rename(columns=rename_map)
        
        return df
    except Exception as e:
        print(f"Error getting training labels: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_ml_labels(symbol: str, timeframe: str, limit: int = 5000) -> pd.DataFrame:
    """Get ML labels from database for a symbol/timeframe."""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    try:
        cur = conn.cursor()
        
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='ml_training_labels'"
        )
        if not cur.fetchone():
            return pd.DataFrame()
        
        query = '''
            SELECT 
                timestamp, open, high, low, close, volume,
                score_long, realized_return_long, mfe_long, mae_long, 
                bars_held_long, exit_type_long,
                score_short, realized_return_short, mfe_short, mae_short, 
                bars_held_short, exit_type_short
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


def get_ml_labels_full(
    symbol: str = None, 
    timeframe: str = None, 
    limit: int = 10000
) -> pd.DataFrame:
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
        
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='ml_training_labels'"
        )
        if not cur.fetchone():
            return pd.DataFrame()
        
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


def clear_ml_labels(symbol: str = None, timeframe: str = None) -> int:
    """Clear ML labels from database (all or filtered by symbol/timeframe)."""
    conn = get_connection()
    if not conn:
        return 0
    try:
        cur = conn.cursor()
        
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='ml_training_labels'"
        )
        if not cur.fetchone():
            return 0
        
        if symbol and timeframe:
            cur.execute(
                'DELETE FROM ml_training_labels WHERE symbol = ? AND timeframe = ?', 
                (symbol, timeframe)
            )
        elif symbol:
            cur.execute(
                'DELETE FROM ml_training_labels WHERE symbol = ?', 
                (symbol,)
            )
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
