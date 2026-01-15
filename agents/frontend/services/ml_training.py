"""
🚀 ML Training Service - Frontend Training for XGBoost Models
==============================================================

Provides training functionality directly from the Streamlit frontend.
"""

import os
import pickle
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, Callable

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scipy.stats import spearmanr
from xgboost import XGBRegressor


# ═══════════════════════════════════════════════════════════════════════════════
# PATH CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

def get_paths():
    """Get database and model paths (works in Docker and locally)"""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    
    if Path(shared_path).exists():
        db_path = Path(shared_path) / "data_cache" / "trading_data.db"
        model_dir = Path(shared_path) / "models"
    else:
        # Local development
        base = Path(__file__).parent.parent.parent.parent
        db_path = base / "shared" / "data_cache" / "trading_data.db"
        model_dir = base / "shared" / "models"
    
    return db_path, model_dir


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE COLUMNS
# ═══════════════════════════════════════════════════════════════════════════════

FEATURE_COLUMNS = [
    'open', 'high', 'low', 'close', 'volume',
    'sma_20', 'sma_50', 'ema_12', 'ema_26',
    'bb_upper', 'bb_mid', 'bb_lower', 'bb_width', 'bb_position',
    'rsi', 'macd', 'macd_signal', 'macd_hist',
    'stoch_k', 'stoch_d', 'atr', 'atr_pct',
    'obv', 'volume_sma', 'adx_14', 'adx_14_norm',
    'ret_5', 'ret_10', 'ret_20',
    'ema_20_dist', 'ema_50_dist', 'ema_200_dist',
    'ema_20_50_cross', 'ema_50_200_cross',
    'rsi_14_norm', 'macd_hist_norm',
    'trend_direction', 'momentum_10', 'momentum_20',
    'vol_5', 'vol_10', 'vol_20',
    'range_pct_5', 'range_pct_10', 'range_pct_20',
    'vol_percentile', 'vol_ratio', 'vol_change', 'obv_slope',
    'vwap_dist', 'vol_stability',
    'body_pct', 'candle_direction', 'upper_shadow_pct', 'lower_shadow_pct',
    'gap_pct', 'consecutive_up', 'consecutive_down',
    'speed_5', 'speed_20', 'accel_5', 'accel_20',
    'ret_percentile_50', 'ret_percentile_100',
    'price_position_20', 'price_position_50', 'price_position_100',
    'dist_from_high_20', 'dist_from_low_20',
]

TARGET_LONG = 'score_long'
TARGET_SHORT = 'score_short'


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

# Expected candles for 12 months of data
EXPECTED_CANDLES = {
    '15m': 35000,  # ~35k candele 15m in 12 mesi
    '1h': 8760,    # ~8.7k candele 1h in 12 mesi
}
COMPLETE_THRESHOLD = 0.95  # 95% = complete


def get_available_training_data() -> Dict[str, Any]:
    """Get info about available training data in the database with completeness info"""
    db_path, _ = get_paths()
    
    if not db_path.exists():
        return {'error': f'Database not found: {db_path}'}
    
    conn = sqlite3.connect(str(db_path))
    
    try:
        # Get symbols
        symbols_df = pd.read_sql_query(
            "SELECT DISTINCT symbol FROM ml_training_labels ORDER BY symbol",
            conn
        )
        
        # Get timeframes
        timeframes_df = pd.read_sql_query(
            "SELECT DISTINCT timeframe FROM ml_training_labels ORDER BY timeframe",
            conn
        )
        
        # Get date range
        dates_df = pd.read_sql_query(
            "SELECT MIN(timestamp) as min_date, MAX(timestamp) as max_date, COUNT(*) as total FROM ml_training_labels",
            conn
        )
        
        # Get count per symbol/timeframe WITH dates
        counts_df = pd.read_sql_query("""
            SELECT symbol, timeframe, 
                   COUNT(*) as count,
                   MIN(timestamp) as start_date,
                   MAX(timestamp) as end_date
            FROM ml_training_labels 
            GROUP BY symbol, timeframe
            ORDER BY symbol, timeframe
        """, conn)
        
        # Calculate completeness for each row
        counts_list = []
        for _, row in counts_df.iterrows():
            expected = EXPECTED_CANDLES.get(row['timeframe'], 35000)
            pct = (row['count'] / expected) * 100
            is_complete = pct >= COMPLETE_THRESHOLD * 100
            
            counts_list.append({
                'symbol': row['symbol'],
                'timeframe': row['timeframe'],
                'count': int(row['count']),
                'start_date': row['start_date'],
                'end_date': row['end_date'],
                'pct': round(pct, 1),
                'is_complete': is_complete
            })
        
        # Get list of complete symbols (both 15m and 1h complete)
        symbol_completeness = {}
        for item in counts_list:
            sym = item['symbol']
            if sym not in symbol_completeness:
                symbol_completeness[sym] = {'15m': False, '1h': False}
            symbol_completeness[sym][item['timeframe']] = item['is_complete']
        
        complete_symbols = [
            sym for sym, tfs in symbol_completeness.items()
            if tfs.get('15m', False) and tfs.get('1h', False)
        ]
        
        return {
            'symbols': symbols_df['symbol'].tolist(),
            'timeframes': timeframes_df['timeframe'].tolist(),
            'min_date': dates_df['min_date'].iloc[0],
            'max_date': dates_df['max_date'].iloc[0],
            'total_rows': int(dates_df['total'].iloc[0]),
            'counts': counts_list,
            'complete_symbols': complete_symbols,
            'n_complete': len(complete_symbols),
            'n_total': len(symbols_df)
        }
        
    except Exception as e:
        return {'error': str(e)}
    finally:
        conn.close()


def load_training_data(symbols: list, timeframes: list, progress_callback: Callable = None, align_timeframes: bool = True) -> pd.DataFrame:
    """
    Load training data from database with optional timeframe alignment.
    
    Args:
        symbols: List of symbols to load
        timeframes: List of timeframes to load
        progress_callback: Optional callback for progress updates
        align_timeframes: If True, align data across timeframes (ceil to 1h)
    
    Returns:
        DataFrame with training data
    """
    db_path, _ = get_paths()
    conn = sqlite3.connect(str(db_path))
    
    if progress_callback:
        progress_callback(0.1, "Loading data from database...")
    
    try:
        # Get indicator columns
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(historical_ohlcv)")
        historical_cols = [row[1] for row in cursor.fetchall()]
        
        exclude_cols = {'id', 'symbol', 'timeframe', 'timestamp', 'fetched_at', 'interpolated',
                        'open', 'high', 'low', 'close', 'volume'}
        indicator_cols = [c for c in historical_cols if c not in exclude_cols]
        indicator_select = ', '.join([f'h.{c}' for c in indicator_cols])
        
        # Build query
        symbol_placeholders = ','.join(['?' for _ in symbols])
        timeframe_placeholders = ','.join(['?' for _ in timeframes])
        
        query = f'''
            SELECT 
                l.timestamp, l.symbol, l.timeframe,
                l.open, l.high, l.low, l.close, l.volume,
                {indicator_select},
                l.score_long, l.score_short
            FROM ml_training_labels l
            INNER JOIN historical_ohlcv h 
                ON l.symbol = h.symbol 
                AND l.timeframe = h.timeframe 
                AND l.timestamp = h.timestamp
            WHERE l.symbol IN ({symbol_placeholders})
            AND l.timeframe IN ({timeframe_placeholders})
            ORDER BY l.symbol, l.timeframe, l.timestamp ASC
        '''
        
        df = pd.read_sql_query(query, conn, params=symbols + timeframes)
        
        if progress_callback:
            progress_callback(0.2, f"Loaded {len(df):,} rows")
        
        # Apply timeframe alignment if needed
        if align_timeframes and len(timeframes) > 1 and len(df) > 0:
            df = _align_training_data(df, progress_callback)
        
        if progress_callback:
            progress_callback(0.3, f"Prepared {len(df):,} aligned rows")
        
        return df
        
    finally:
        conn.close()


def _align_training_data(df: pd.DataFrame, progress_callback: Callable = None) -> pd.DataFrame:
    """
    Align training data across timeframes for each symbol.
    
    For each symbol, finds the latest start date across all timeframes,
    rounds it to the next hour, and filters data to start from there.
    
    This ensures that when training with multiple timeframes (15m + 1h),
    the data is temporally aligned.
    """
    if progress_callback:
        progress_callback(0.22, "Aligning timeframes...")
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    aligned_dfs = []
    total_trimmed = 0
    
    symbols = df['symbol'].unique()
    
    for symbol in symbols:
        symbol_df = df[df['symbol'] == symbol].copy()
        
        if len(symbol_df) == 0:
            continue
        
        # Find max start date across timeframes for this symbol
        start_dates = symbol_df.groupby('timeframe')['timestamp'].min()
        max_start = start_dates.max()
        
        # Round up to next hour (ceil)
        aligned_start = max_start.ceil('H')
        
        # Filter data
        original_count = len(symbol_df)
        aligned_df = symbol_df[symbol_df['timestamp'] >= aligned_start]
        trimmed = original_count - len(aligned_df)
        total_trimmed += trimmed
        
        aligned_dfs.append(aligned_df)
    
    if aligned_dfs:
        result = pd.concat(aligned_dfs, ignore_index=True)
        
        if progress_callback and total_trimmed > 0:
            progress_callback(0.25, f"Aligned: trimmed {total_trimmed:,} candles")
        
        return result
    
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def prepare_features(df: pd.DataFrame, progress_callback: Callable = None) -> Tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series, list]:
    """Prepare features and targets for training"""
    
    if progress_callback:
        progress_callback(0.35, "Preparing features...")
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Get available features
    available_features = [c for c in FEATURE_COLUMNS if c in df.columns]
    
    # Find first complete row
    feature_df = df[available_features]
    first_complete_idx = 0
    for idx in range(len(df)):
        if not feature_df.iloc[idx].isnull().any():
            first_complete_idx = idx
            break
    
    df = df.iloc[first_complete_idx:].reset_index(drop=True)
    
    # Remove NaN rows
    X = df[available_features]
    y_long = df[TARGET_LONG]
    y_short = df[TARGET_SHORT]
    
    valid_mask = ~(X.isna().any(axis=1) | y_long.isna() | y_short.isna())
    df = df[valid_mask].reset_index(drop=True)
    
    if progress_callback:
        progress_callback(0.4, f"Prepared {len(df):,} samples")
    
    return df[available_features], df[TARGET_LONG], df[TARGET_SHORT], df['timestamp'], available_features


def calculate_ranking_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Calculate ranking metrics"""
    spearman_corr, spearman_pval = spearmanr(y_pred, y_true)
    
    metrics = {
        'spearman_corr': spearman_corr,
        'spearman_pval': spearman_pval,
    }
    
    for k_pct in [1, 5, 10, 20]:
        k = max(1, int(len(y_pred) * k_pct / 100))
        top_k_idx = np.argsort(y_pred)[-k:]
        top_k_true = y_true.iloc[top_k_idx] if hasattr(y_true, 'iloc') else y_true[top_k_idx]
        
        metrics[f'top{k_pct}pct_avg_score'] = np.mean(top_k_true)
        metrics[f'top{k_pct}pct_positive'] = (top_k_true > 0).mean() * 100
    
    return metrics


def train_xgb_model(
    symbols: list,
    timeframes: list,
    params: dict,
    train_ratio: float = 0.8,
    progress_callback: Callable = None
) -> Dict[str, Any]:
    """
    Train XGBoost models with progress callback.
    
    Args:
        symbols: List of symbols to train on
        timeframes: List of timeframes
        params: XGBoost parameters
        train_ratio: Train/test split ratio
        progress_callback: Callback function(progress, message)
    
    Returns:
        Dictionary with training results
    """
    
    # 1. Load data
    if progress_callback:
        progress_callback(0.05, "Starting training...")
    
    df = load_training_data(symbols, timeframes, progress_callback)
    
    if len(df) == 0:
        return {'error': 'No training data found'}
    
    # 2. Prepare features
    X, y_long, y_short, timestamps, feature_names = prepare_features(df, progress_callback)
    
    if len(X) < 100:
        return {'error': f'Not enough samples ({len(X)}). Need at least 100.'}
    
    # 3. Split data temporally
    split_idx = int(len(X) * train_ratio)
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_long_train, y_long_test = y_long.iloc[:split_idx], y_long.iloc[split_idx:]
    y_short_train, y_short_test = y_short.iloc[:split_idx], y_short.iloc[split_idx:]
    ts_train, ts_test = timestamps.iloc[:split_idx], timestamps.iloc[split_idx:]
    
    if progress_callback:
        progress_callback(0.45, f"Split: {len(X_train):,} train / {len(X_test):,} test")
    
    # 4. Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 5. Train LONG model
    if progress_callback:
        progress_callback(0.5, "Training LONG model...")
    
    xgb_params = {
        'objective': 'reg:squarederror',
        'eval_metric': 'rmse',
        'tree_method': 'hist',
        'verbosity': 0,
        'random_state': 42,
        **params
    }
    
    model_long = XGBRegressor(**xgb_params)
    model_long.fit(X_train_scaled, y_long_train, eval_set=[(X_test_scaled, y_long_test)], verbose=False)
    
    y_pred_long_train = model_long.predict(X_train_scaled)
    y_pred_long_test = model_long.predict(X_test_scaled)
    
    metrics_long = {
        'train_rmse': np.sqrt(mean_squared_error(y_long_train, y_pred_long_train)),
        'test_rmse': np.sqrt(mean_squared_error(y_long_test, y_pred_long_test)),
        'train_mae': mean_absolute_error(y_long_train, y_pred_long_train),
        'test_mae': mean_absolute_error(y_long_test, y_pred_long_test),
        'train_r2': r2_score(y_long_train, y_pred_long_train),
        'test_r2': r2_score(y_long_test, y_pred_long_test),
        'ranking': calculate_ranking_metrics(y_long_test, y_pred_long_test)
    }
    
    # 6. Train SHORT model
    if progress_callback:
        progress_callback(0.75, "Training SHORT model...")
    
    model_short = XGBRegressor(**xgb_params)
    model_short.fit(X_train_scaled, y_short_train, eval_set=[(X_test_scaled, y_short_test)], verbose=False)
    
    y_pred_short_train = model_short.predict(X_train_scaled)
    y_pred_short_test = model_short.predict(X_test_scaled)
    
    metrics_short = {
        'train_rmse': np.sqrt(mean_squared_error(y_short_train, y_pred_short_train)),
        'test_rmse': np.sqrt(mean_squared_error(y_short_test, y_pred_short_test)),
        'train_mae': mean_absolute_error(y_short_train, y_pred_short_train),
        'test_mae': mean_absolute_error(y_short_test, y_pred_short_test),
        'train_r2': r2_score(y_short_train, y_pred_short_train),
        'test_r2': r2_score(y_short_test, y_pred_short_test),
        'ranking': calculate_ranking_metrics(y_short_test, y_pred_short_test)
    }
    
    # 7. Save models
    if progress_callback:
        progress_callback(0.9, "Saving models...")
    
    _, model_dir = get_paths()
    model_dir.mkdir(parents=True, exist_ok=True)
    
    version = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    with open(model_dir / f"model_long_{version}.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(model_dir / f"model_short_{version}.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(model_dir / f"scaler_{version}.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    
    # Also save as latest
    with open(model_dir / "model_long_latest.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(model_dir / "model_short_latest.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(model_dir / "scaler_latest.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save metadata
    metadata = {
        'version': version,
        'created_at': datetime.now().isoformat(),
        'feature_names': feature_names,
        'n_features': len(feature_names),
        'xgboost_params': xgb_params,
        'train_ratio': train_ratio,
        'metrics_long': metrics_long,
        'metrics_short': metrics_short,
        'data_range': {
            'train_start': str(ts_train.iloc[0]),
            'train_end': str(ts_train.iloc[-1]),
            'test_start': str(ts_test.iloc[0]),
            'test_end': str(ts_test.iloc[-1]),
        },
        'symbols': symbols,
        'timeframes': timeframes,
        'n_train_samples': len(X_train),
        'n_test_samples': len(X_test),
    }
    
    with open(model_dir / f"metadata_{version}.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    with open(model_dir / "metadata_latest.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    
    if progress_callback:
        progress_callback(1.0, "Training complete!")
    
    return {
        'success': True,
        'version': version,
        'metrics_long': metrics_long,
        'metrics_short': metrics_short,
        'n_features': len(feature_names),
        'n_train': len(X_train),
        'n_test': len(X_test),
        'data_range': metadata['data_range']
    }


# ═══════════════════════════════════════════════════════════════════════════════
# OPTUNA HYPERPARAMETER TUNING
# ═══════════════════════════════════════════════════════════════════════════════

def run_optuna_optimization(
    symbols: list,
    timeframes: list,
    n_trials: int = 30,
    progress_callback: Callable = None
) -> Dict[str, Any]:
    """
    Run Optuna hyperparameter optimization.
    
    Optimizes for Spearman correlation (ranking quality).
    Uses TPE sampler for efficient search.
    
    Args:
        symbols: List of symbols
        timeframes: List of timeframes
        n_trials: Number of Optuna trials
        progress_callback: Progress callback(progress, message)
    
    Returns:
        Dictionary with optimization results
    """
    try:
        import optuna
        from optuna.samplers import TPESampler
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        return {'error': 'Optuna not installed. Run: pip install optuna'}
    
    if progress_callback:
        progress_callback(0.05, "Loading data for Optuna optimization...")
    
    # Load data
    df = load_training_data(symbols, timeframes, progress_callback)
    
    if len(df) == 0:
        return {'error': 'No training data found'}
    
    # Prepare features
    X, y_long, y_short, timestamps, feature_names = prepare_features(df, progress_callback)
    
    if len(X) < 200:
        return {'error': f'Not enough samples ({len(X)}). Need at least 200 for Optuna.'}
    
    # 3-way split: 70% train, 15% val, 15% test
    n = len(X)
    train_end = int(n * 0.7)
    val_end = int(n * 0.85)
    
    X_train, X_val, X_test = X.iloc[:train_end], X.iloc[train_end:val_end], X.iloc[val_end:]
    y_long_train, y_long_val, y_long_test = y_long.iloc[:train_end], y_long.iloc[train_end:val_end], y_long.iloc[val_end:]
    y_short_train, y_short_val, y_short_test = y_short.iloc[:train_end], y_short.iloc[train_end:val_end], y_short.iloc[val_end:]
    ts_train, ts_val, ts_test = timestamps.iloc[:train_end], timestamps.iloc[train_end:val_end], timestamps.iloc[val_end:]
    
    if progress_callback:
        progress_callback(0.15, f"Split: {len(X_train):,} train / {len(X_val):,} val / {len(X_test):,} test")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    # Store trial results for visualization
    trial_history = []
    best_spearman_long = -1
    best_spearman_short = -1
    
    # ═══════════════════════════════════════════════════════════════════
    # TUNE LONG MODEL
    # ═══════════════════════════════════════════════════════════════════
    
    def objective_long(trial):
        nonlocal best_spearman_long
        
        params = {
            'objective': 'reg:squarederror',
            'tree_method': 'hist',
            'verbosity': 0,
            'random_state': 42,
            'n_estimators': trial.suggest_int('n_estimators', 300, 1500),
            'max_depth': trial.suggest_int('max_depth', 4, 10),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
            'min_child_weight': trial.suggest_int('min_child_weight', 5, 30),
            'subsample': trial.suggest_float('subsample', 0.6, 0.95),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 0.95),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-6, 1.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-6, 1.0, log=True),
            'early_stopping_rounds': 50,
        }
        
        model = XGBRegressor(**params)
        model.fit(X_train_scaled, y_long_train.values, 
                  eval_set=[(X_val_scaled, y_long_val.values)], verbose=False)
        
        y_pred = model.predict(X_val_scaled)
        spearman, _ = spearmanr(y_pred, y_long_val.values)
        
        if spearman > best_spearman_long:
            best_spearman_long = spearman
        
        trial_history.append({
            'trial': trial.number,
            'model': 'long',
            'spearman': spearman,
            'params': params.copy()
        })
        
        return spearman
    
    if progress_callback:
        progress_callback(0.2, f"Tuning LONG model (0/{n_trials} trials)...")
    
    study_long = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
    
    for i in range(n_trials):
        study_long.optimize(objective_long, n_trials=1, show_progress_bar=False)
        if progress_callback:
            progress_callback(0.2 + (i+1)/n_trials * 0.3, 
                            f"LONG trial {i+1}/{n_trials} - Best: {best_spearman_long:.4f}")
    
    # ═══════════════════════════════════════════════════════════════════
    # TUNE SHORT MODEL
    # ═══════════════════════════════════════════════════════════════════
    
    def objective_short(trial):
        nonlocal best_spearman_short
        
        params = {
            'objective': 'reg:squarederror',
            'tree_method': 'hist',
            'verbosity': 0,
            'random_state': 42,
            'n_estimators': trial.suggest_int('n_estimators', 300, 1500),
            'max_depth': trial.suggest_int('max_depth', 4, 10),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
            'min_child_weight': trial.suggest_int('min_child_weight', 5, 30),
            'subsample': trial.suggest_float('subsample', 0.6, 0.95),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 0.95),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-6, 1.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-6, 1.0, log=True),
            'early_stopping_rounds': 50,
        }
        
        model = XGBRegressor(**params)
        model.fit(X_train_scaled, y_short_train.values,
                  eval_set=[(X_val_scaled, y_short_val.values)], verbose=False)
        
        y_pred = model.predict(X_val_scaled)
        spearman, _ = spearmanr(y_pred, y_short_val.values)
        
        if spearman > best_spearman_short:
            best_spearman_short = spearman
        
        trial_history.append({
            'trial': trial.number,
            'model': 'short',
            'spearman': spearman,
            'params': params.copy()
        })
        
        return spearman
    
    if progress_callback:
        progress_callback(0.5, f"Tuning SHORT model (0/{n_trials} trials)...")
    
    study_short = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
    
    for i in range(n_trials):
        study_short.optimize(objective_short, n_trials=1, show_progress_bar=False)
        if progress_callback:
            progress_callback(0.5 + (i+1)/n_trials * 0.3,
                            f"SHORT trial {i+1}/{n_trials} - Best: {best_spearman_short:.4f}")
    
    # ═══════════════════════════════════════════════════════════════════
    # TRAIN FINAL MODELS WITH BEST PARAMS
    # ═══════════════════════════════════════════════════════════════════
    
    if progress_callback:
        progress_callback(0.85, "Training final models with best params...")
    
    best_params_long = study_long.best_params
    best_params_short = study_short.best_params
    
    # Combine train+val for final training
    X_train_full = np.vstack([X_train_scaled, X_val_scaled])
    y_long_full = pd.concat([y_long_train, y_long_val]).values
    y_short_full = pd.concat([y_short_train, y_short_val]).values
    
    # Train final LONG
    final_params_long = {
        'objective': 'reg:squarederror',
        'tree_method': 'hist',
        'verbosity': 0,
        'random_state': 42,
        **best_params_long
    }
    final_params_long.pop('early_stopping_rounds', None)
    
    model_long = XGBRegressor(**final_params_long)
    model_long.fit(X_train_full, y_long_full, verbose=False)
    
    # Train final SHORT
    final_params_short = {
        'objective': 'reg:squarederror',
        'tree_method': 'hist',
        'verbosity': 0,
        'random_state': 42,
        **best_params_short
    }
    final_params_short.pop('early_stopping_rounds', None)
    
    model_short = XGBRegressor(**final_params_short)
    model_short.fit(X_train_full, y_short_full, verbose=False)
    
    # Evaluate on TEST set
    y_pred_long = model_long.predict(X_test_scaled)
    y_pred_short = model_short.predict(X_test_scaled)
    
    spearman_long, _ = spearmanr(y_pred_long, y_long_test.values)
    spearman_short, _ = spearmanr(y_pred_short, y_short_test.values)
    
    metrics_long = {
        'test_r2': r2_score(y_long_test, y_pred_long),
        'test_rmse': np.sqrt(mean_squared_error(y_long_test, y_pred_long)),
        'test_spearman': spearman_long,
        'ranking': calculate_ranking_metrics(y_long_test, y_pred_long)
    }
    
    metrics_short = {
        'test_r2': r2_score(y_short_test, y_pred_short),
        'test_rmse': np.sqrt(mean_squared_error(y_short_test, y_pred_short)),
        'test_spearman': spearman_short,
        'ranking': calculate_ranking_metrics(y_short_test, y_pred_short)
    }
    
    # Save models
    if progress_callback:
        progress_callback(0.95, "Saving optimized models...")
    
    _, model_dir = get_paths()
    model_dir.mkdir(parents=True, exist_ok=True)
    
    version = datetime.now().strftime('%Y%m%d_%H%M%S') + '_optuna'
    
    with open(model_dir / f"model_long_{version}.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(model_dir / f"model_short_{version}.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(model_dir / f"scaler_{version}.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save as latest
    with open(model_dir / "model_long_latest.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(model_dir / "model_short_latest.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(model_dir / "scaler_latest.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save metadata
    metadata = {
        'version': version,
        'created_at': datetime.now().isoformat(),
        'tuning_method': 'optuna_tpe',
        'n_trials': n_trials,
        'feature_names': feature_names,
        'n_features': len(feature_names),
        'best_params_long': best_params_long,
        'best_params_short': best_params_short,
        'metrics_long': metrics_long,
        'metrics_short': metrics_short,
        'data_range': {
            'train_start': str(ts_train.iloc[0]),
            'train_end': str(ts_train.iloc[-1]),
            'val_start': str(ts_val.iloc[0]),
            'val_end': str(ts_val.iloc[-1]),
            'test_start': str(ts_test.iloc[0]),
            'test_end': str(ts_test.iloc[-1]),
        },
        'symbols': symbols,
        'timeframes': timeframes,
    }
    
    with open(model_dir / f"metadata_{version}.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    with open(model_dir / "metadata_latest.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    
    if progress_callback:
        progress_callback(1.0, "Optuna optimization complete!")
    
    return {
        'success': True,
        'version': version,
        'n_trials': n_trials,
        'best_params_long': best_params_long,
        'best_params_short': best_params_short,
        'metrics_long': metrics_long,
        'metrics_short': metrics_short,
        'best_spearman_long': study_long.best_value,
        'best_spearman_short': study_short.best_value,
        'trial_history': trial_history,
        'n_train': len(X_train),
        'n_val': len(X_val),
        'n_test': len(X_test),
        'data_range': metadata['data_range']
    }
