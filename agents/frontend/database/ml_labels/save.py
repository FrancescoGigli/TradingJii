"""
💾 ML Labels Save Operations

Functions to save ML labels to database.
"""

import pandas as pd
from ..connection import get_connection
from .schema import create_ml_labels_table


def _safe_float(value, default=0.0):
    """Convert value to float safely, handling NaN/None."""
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
    """Convert value to int safely, handling NaN/None."""
    if value is None:
        return default
    try:
        f = float(value)
        if pd.isna(f):
            return default
        return int(f)
    except (ValueError, TypeError):
        return default


def save_ml_labels_to_db(
    symbol: str, 
    timeframe: str, 
    ohlcv_df: pd.DataFrame, 
    labels_df: pd.DataFrame, 
    config: dict
) -> int:
    """
    Save ML training labels to database.
    
    Args:
        symbol: Trading pair symbol
        timeframe: Candle timeframe (15m, 1h)
        ohlcv_df: DataFrame with OHLCV data (index=timestamp)
        labels_df: DataFrame with labels (same index)
        config: Dict with trailing_stop_pct, max_bars, etc.
    
    Returns:
        Number of rows saved
    """
    conn = get_connection()
    if not conn:
        print("Error: No database connection")
        return 0
    
    try:
        create_ml_labels_table()
        cur = conn.cursor()
        
        # Delete existing labels for this symbol/timeframe
        cur.execute(
            'DELETE FROM ml_training_labels WHERE symbol = ? AND timeframe = ?',
            (symbol, timeframe)
        )
        
        generated_at = pd.Timestamp.now().isoformat()
        rows_saved = 0
        
        common_indices = ohlcv_df.index.intersection(labels_df.index)
        
        for idx in common_indices:
            ohlcv_row = ohlcv_df.loc[idx]
            label_row = labels_df.loc[idx]
            
            # Skip invalid labels
            exit_col = f'exit_type_long_{timeframe}'
            if hasattr(label_row, 'get'):
                exit_type_val = label_row.get(exit_col, None)
            elif exit_col in label_row.index:
                exit_type_val = label_row[exit_col]
            else:
                exit_type_val = None
            
            if exit_type_val == 'invalid':
                continue
            
            def get_label_val(col_suffix, is_int=False):
                col_name = f'{col_suffix}_{timeframe}'
                if hasattr(label_row, 'get'):
                    val = label_row.get(col_name, 0)
                elif col_name in label_row.index:
                    val = label_row[col_name]
                else:
                    val = 0
                return _safe_int(val) if is_int else _safe_float(val)
            
            def get_exit_short():
                col = f'exit_type_short_{timeframe}'
                if hasattr(label_row, 'get'):
                    return str(label_row.get(col, ''))
                elif col in label_row.index:
                    return str(label_row[col])
                return ''
            
            try:
                cur.execute('''
                    INSERT INTO ml_training_labels (
                        symbol, timeframe, timestamp,
                        open, high, low, close, volume,
                        score_long, realized_return_long, mfe_long, mae_long, 
                        bars_held_long, exit_type_long,
                        score_short, realized_return_short, mfe_short, mae_short, 
                        bars_held_short, exit_type_short,
                        trailing_stop_pct, max_bars, time_penalty_lambda, trading_cost,
                        generated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol, timeframe, str(idx),
                    _safe_float(ohlcv_row['open']), 
                    _safe_float(ohlcv_row['high']), 
                    _safe_float(ohlcv_row['low']), 
                    _safe_float(ohlcv_row['close']), 
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
                    get_exit_short(),
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
