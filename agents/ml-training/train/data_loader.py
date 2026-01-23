"""
📊 Data Loading and Validation

Load and validate ML training datasets from database.
"""

import sys
import sqlite3
import pandas as pd
from pathlib import Path
from .config import FEATURE_COLUMNS, TARGET_LONG, TARGET_SHORT


def load_dataset(db_path: Path, symbol: str = None, timeframe: str = None) -> pd.DataFrame:
    """Load ML training dataset from SQLite database."""
    print(f"\n📊 Loading dataset from: {db_path}")
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    
    try:
        cursor = conn.cursor()
        for table in ['historical_ohlcv', 'ml_training_labels']:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                print(f"❌ Table '{table}' not found")
                sys.exit(1)
        
        cursor.execute("PRAGMA table_info(historical_ohlcv)")
        exclude = {'id', 'symbol', 'timeframe', 'timestamp', 'fetched_at', 'interpolated', 'open', 'high', 'low', 'close', 'volume'}
        indicator_cols = [r[1] for r in cursor.fetchall() if r[1] not in exclude]
        ind_select = ', '.join([f'h.{c}' for c in indicator_cols])
        
        query = f'''
            SELECT l.timestamp, l.symbol, l.timeframe, l.open, l.high, l.low, l.close, l.volume,
                {ind_select},
                l.score_long, l.score_short, l.realized_return_long, l.realized_return_short,
                l.mfe_long, l.mae_long, l.mfe_short, l.mae_short,
                l.bars_held_long, l.bars_held_short, l.exit_type_long, l.exit_type_short,
                l.trailing_stop_pct, l.max_bars, l.time_penalty_lambda, l.trading_cost
            FROM ml_training_labels l
            INNER JOIN historical_ohlcv h ON l.symbol = h.symbol AND l.timeframe = h.timeframe AND l.timestamp = h.timestamp
        '''
        conditions, params = [], []
        if symbol:
            conditions.append('l.symbol LIKE ?')
            params.append(f'%{symbol}%')
        if timeframe:
            conditions.append('l.timeframe = ?')
            params.append(timeframe)
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        query += ' ORDER BY l.symbol, l.timeframe, l.timestamp ASC'
        
        df = pd.read_sql_query(query, conn, params=params if params else None)
        print(f"   ✅ Loaded {len(df):,} rows from database")
        return df
    finally:
        conn.close()


def validate_data_quality(df: pd.DataFrame, features: list, timeframe: str = '15m') -> dict:
    """Rigorous data quality validation for ML training."""
    print("\n🔍 DATA QUALITY VALIDATION")
    print("="*60)
    
    validation = {'total_rows': len(df), 'nan_features': {}, 'nan_targets': {}, 'timestamp_gaps': [], 'is_valid': True}
    
    total_nan = 0
    for col in features:
        if col in df.columns:
            n = df[col].isna().sum()
            if n > 0:
                validation['nan_features'][col] = n
                total_nan += n
    
    print(f"   {'⚠️' if total_nan else '✅'} NaN in features: {total_nan}")
    
    for target in [TARGET_LONG, TARGET_SHORT]:
        n = df[target].isna().sum()
        if n > 0:
            validation['nan_targets'][target] = n
            validation['is_valid'] = False
            print(f"   ❌ {target}: {n} NaN")
        else:
            print(f"   ✅ {target}: NO NaN")
    
    print("="*60)
    return validation


def prepare_dataset(df: pd.DataFrame) -> tuple:
    """Prepare dataset for training. Returns (X, y_long, y_short, timestamps, features)."""
    print("\n🔧 Preparing dataset...")
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    available = [c for c in FEATURE_COLUMNS if c in df.columns]
    print(f"   📊 Using {len(available)} features")
    
    validate_data_quality(df, available)
    
    # Find first complete row
    rows_before = len(df)
    feature_df = df[available]
    first_idx = None
    for i in range(len(df)):
        if not feature_df.iloc[i].isnull().any():
            first_idx = i
            break
    
    if first_idx is None:
        print("❌ No complete rows found")
        sys.exit(1)
    
    df = df.iloc[first_idx:].reset_index(drop=True)
    print(f"   ✅ Filtered {rows_before - len(df):,} warm-up rows")
    
    # Remove residual NaN
    X_temp = df[available]
    valid_mask = ~(X_temp.isna().any(axis=1) | df[TARGET_LONG].isna() | df[TARGET_SHORT].isna())
    df = df[valid_mask].reset_index(drop=True)
    
    X = df[available].copy()
    y_long = df[TARGET_LONG].copy()
    y_short = df[TARGET_SHORT].copy()
    timestamps = df['timestamp'].copy()
    
    assert X.isna().sum().sum() == 0, "NaN in features!"
    assert y_long.isna().sum() == 0, "NaN in score_long!"
    assert y_short.isna().sum() == 0, "NaN in score_short!"
    
    print(f"   ✅ FINAL Dataset: {len(df):,} rows")
    return X, y_long, y_short, timestamps, available
