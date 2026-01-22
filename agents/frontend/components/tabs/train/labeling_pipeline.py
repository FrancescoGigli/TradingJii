"""
🏷️ Labeling Pipeline (ATR-Based) - OPTIMIZED VERSION

Pipeline functions for generating and saving ATR-based training labels:
- Generate labels for single symbol  
- Batch insert for faster DB writes
- Run pipeline for both timeframes
"""

import os
from database import get_connection
from ai.core.labels import ATRLabeler, ATRLabelConfig
from .labeling_db import (
    get_training_features_symbols,
    get_training_features_data,
    create_training_labels_table,
    create_xgb_training_view
)


def generate_labels_for_symbol(
    symbol: str, 
    timeframe: str, 
    config: ATRLabelConfig,
    max_bars: int
) -> tuple:
    """
    Generate ATR-based labels for a symbol.
    Returns prepared data for batch insert.
    """
    
    df = get_training_features_data(symbol, timeframe)
    if df is None or len(df) == 0:
        return symbol, False, 0, None, "No data available"
    
    labeler = ATRLabeler(config)
    labels_df = labeler.generate_labels_for_timeframe(df, timeframe)
    
    result_df = df.join(labels_df)
    
    # Filter valid rows
    valid_mask = result_df[f'exit_type_long_{timeframe}'] != 'invalid'
    result_df = result_df[valid_mask]
    
    label_cols = [f'score_long_{timeframe}', f'score_short_{timeframe}']
    result_df = result_df.dropna(subset=label_cols)
    
    if len(result_df) == 0:
        return symbol, False, 0, None, "No valid labels generated"
    
    result_df = result_df.reset_index()
    
    # Prepare batch data
    batch_data = []
    for _, row in result_df.iterrows():
        atr_pct = row.get(f'atr_pct_{timeframe}', 0.0)
        if atr_pct is None or (hasattr(atr_pct, '__float__') and str(atr_pct) == 'nan'):
            atr_pct = 0.0
        
        batch_data.append((
            str(row['timestamp']),
            symbol,
            timeframe,
            row[f'score_long_{timeframe}'],
            row[f'score_short_{timeframe}'],
            row[f'realized_return_long_{timeframe}'],
            row[f'realized_return_short_{timeframe}'],
            row[f'mfe_long_{timeframe}'],
            row[f'mfe_short_{timeframe}'],
            row[f'mae_long_{timeframe}'],
            row[f'mae_short_{timeframe}'],
            int(row[f'bars_held_long_{timeframe}']),
            int(row[f'bars_held_short_{timeframe}']),
            row[f'exit_type_long_{timeframe}'],
            row[f'exit_type_short_{timeframe}'],
            float(atr_pct)
        ))
    
    return symbol, True, len(batch_data), batch_data, "Success"


def batch_insert_labels(all_batch_data: list, timeframe: str, symbols_to_delete: list) -> tuple:
    """
    Batch insert all labels in a single transaction.
    Much faster than row-by-row insert.
    """
    conn = get_connection()
    if not conn:
        return False, 0, "Database connection failed"
    
    try:
        cur = conn.cursor()
        
        # Delete existing labels for all processed symbols in one go
        for symbol in symbols_to_delete:
            cur.execute('DELETE FROM training_labels WHERE symbol=? AND timeframe=?', (symbol, timeframe))
        
        # Batch insert all data
        cur.executemany('''
            INSERT INTO training_labels 
            (timestamp, symbol, timeframe,
             score_long, score_short, 
             realized_return_long, realized_return_short,
             mfe_long, mfe_short, mae_long, mae_short,
             bars_held_long, bars_held_short,
             exit_type_long, exit_type_short,
             atr_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', all_batch_data)
        
        conn.commit()
        return True, len(all_batch_data), "Batch insert successful"
        
    except Exception as e:
        conn.rollback()
        return False, 0, str(e)
    finally:
        conn.close()


def run_labeling_pipeline_single(
    timeframe: str, 
    config: ATRLabelConfig, 
    progress_callback=None, 
    create_table: bool = True
):
    """
    Run ATR-based labeling for a single timeframe.
    Optimized with batch insert.
    """
    
    if create_table:
        if not create_training_labels_table():
            return False, 0, "Failed to create training_labels table"
    
    symbols = get_training_features_symbols(timeframe)
    if not symbols:
        return False, 0, f"No symbols found for {timeframe}"
    
    max_bars = config.get_max_bars(timeframe)
    
    # Process sequentially (Streamlit-safe) but batch insert at end
    all_batch_data = []
    symbols_processed = []
    errors = []
    
    for i, symbol in enumerate(symbols):
        if progress_callback:
            progress_callback(i + 1, len(symbols), symbol, timeframe)
        
        try:
            symbol_name, success, rows, batch_data, message = generate_labels_for_symbol(
                symbol, timeframe, config, max_bars
            )
            
            if success and batch_data:
                all_batch_data.extend(batch_data)
                symbols_processed.append(symbol_name)
            else:
                errors.append(f"{symbol_name}: {message}")
                
        except Exception as e:
            errors.append(f"{symbol}: {str(e)}")
    
    # Batch insert all results at the end
    if all_batch_data:
        success, total_rows, message = batch_insert_labels(all_batch_data, timeframe, symbols_processed)
        if not success:
            return False, 0, f"Batch insert failed: {message}"
    else:
        total_rows = 0
    
    if errors and len(errors) == len(symbols):
        return False, 0, f"All symbols failed. First error: {errors[0]}"
    
    return True, total_rows, f"{len(symbols) - len(errors)} symbols"


def run_labeling_pipeline_both(config: ATRLabelConfig, progress_callback=None):
    """Run ATR-based labeling for BOTH timeframes (15m and 1h)"""
    
    if not create_training_labels_table():
        return False, "Failed to create training_labels table"
    
    results = {}
    
    # 15m
    success_15m, rows_15m, msg_15m = run_labeling_pipeline_single('15m', config, progress_callback, create_table=False)
    results['15m'] = {'success': success_15m, 'rows': rows_15m, 'message': msg_15m}
    
    # 1h
    success_1h, rows_1h, msg_1h = run_labeling_pipeline_single('1h', config, progress_callback, create_table=False)
    results['1h'] = {'success': success_1h, 'rows': rows_1h, 'message': msg_1h}
    
    # Create view
    if not create_xgb_training_view():
        return False, "Failed to create v_xgb_training VIEW"
    
    total_rows = rows_15m + rows_1h
    
    return True, f"Generated ATR-based labels: 15m ({msg_15m}, {rows_15m:,} rows), 1h ({msg_1h}, {rows_1h:,} rows). Total: {total_rows:,} rows. VIEW v_xgb_training created."


# Legacy function for backwards compatibility
def generate_and_save_labels(
    symbol: str, 
    timeframe: str, 
    config: ATRLabelConfig,
    max_bars: int
) -> tuple:
    """Legacy single-symbol function"""
    
    symbol_name, success, rows, batch_data, message = generate_labels_for_symbol(
        symbol, timeframe, config, max_bars
    )
    
    if not success or not batch_data:
        return False, 0, message
    
    success, total, msg = batch_insert_labels(batch_data, timeframe, [symbol])
    return success, total, msg


__all__ = [
    'generate_and_save_labels',
    'generate_labels_for_symbol',
    'batch_insert_labels',
    'run_labeling_pipeline_single',
    'run_labeling_pipeline_both'
]
