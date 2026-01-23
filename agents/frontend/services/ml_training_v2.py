"""
🚀 ML Training Service V2 - Uses trading_data.db
==================================================

Uses the correct tables:
- training_data: OHLCV + indicators (features)
- training_labels: score_long, score_short (targets)
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

def get_db_path():
    """Get database path (works in Docker and locally)"""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    return Path(shared_path) / "data_cache" / "trading_data.db"


def get_model_dir():
    """Get model directory"""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    model_dir = Path(shared_path) / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE COLUMNS (matching training_data table)
# ═══════════════════════════════════════════════════════════════════════════════

FEATURE_COLUMNS = [
    'open', 'high', 'low', 'close', 'volume',
    'sma_20', 'sma_50', 'ema_12', 'ema_26',
    'bb_upper', 'bb_mid', 'bb_lower',
    'macd', 'macd_signal', 'macd_hist',
    'rsi', 'stoch_k', 'stoch_d',
    'atr', 'volume_sma', 'obv'
]


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def get_available_training_data() -> Dict[str, Any]:
    """Get info about available training data"""
    db_path = get_db_path()
    
    if not db_path.exists():
        return {'error': f'Database not found: {db_path}'}
    
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    
    try:
        # Get symbols
        symbols_df = pd.read_sql_query(
            "SELECT DISTINCT symbol FROM training_labels ORDER BY symbol",
            conn
        )
        
        # Get timeframes
        timeframes_df = pd.read_sql_query(
            "SELECT DISTINCT timeframe FROM training_labels ORDER BY timeframe",
            conn
        )
        
        # Get counts per symbol/timeframe
        counts_df = pd.read_sql_query("""
            SELECT symbol, timeframe, 
                   COUNT(*) as count,
                   MIN(timestamp) as start_date,
                   MAX(timestamp) as end_date
            FROM training_labels 
            GROUP BY symbol, timeframe
            ORDER BY symbol, timeframe
        """, conn)
        
        # Get date range
        dates_df = pd.read_sql_query(
            "SELECT MIN(timestamp) as min_date, MAX(timestamp) as max_date, COUNT(*) as total FROM training_labels",
            conn
        )
        
        counts_list = []
        for _, row in counts_df.iterrows():
            counts_list.append({
                'symbol': row['symbol'],
                'timeframe': row['timeframe'],
                'count': int(row['count']),
                'start_date': row['start_date'],
                'end_date': row['end_date'],
            })
        
        return {
            'symbols': symbols_df['symbol'].tolist(),
            'timeframes': timeframes_df['timeframe'].tolist(),
            'min_date': dates_df['min_date'].iloc[0],
            'max_date': dates_df['max_date'].iloc[0],
            'total_rows': int(dates_df['total'].iloc[0]),
            'counts': counts_list,
        }
        
    except Exception as e:
        return {'error': str(e)}
    finally:
        conn.close()


def load_training_data(
    symbols: list, 
    timeframes: list, 
    progress_callback: Callable = None
) -> pd.DataFrame:
    """Load training data by joining training_data and training_labels"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    
    if progress_callback:
        progress_callback(0.1, "Loading data from database...")
    
    try:
        # Build query with JOIN
        symbol_placeholders = ','.join(['?' for _ in symbols])
        timeframe_placeholders = ','.join(['?' for _ in timeframes])
        
        feature_select = ', '.join([f'd.{c}' for c in FEATURE_COLUMNS])
        
        query = f'''
            SELECT 
                d.timestamp, d.symbol, d.timeframe,
                {feature_select},
                l.score_long, l.score_short
            FROM training_data d
            INNER JOIN training_labels l
                ON d.symbol = l.symbol 
                AND d.timeframe = l.timeframe 
                AND d.timestamp = l.timestamp
            WHERE d.symbol IN ({symbol_placeholders})
            AND d.timeframe IN ({timeframe_placeholders})
            ORDER BY d.symbol, d.timeframe, d.timestamp ASC
        '''
        
        df = pd.read_sql_query(query, conn, params=symbols + timeframes)
        
        if progress_callback:
            progress_callback(0.3, f"Loaded {len(df):,} rows")
        
        return df
        
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def prepare_features(df: pd.DataFrame, progress_callback: Callable = None) -> Tuple:
    """Prepare features and targets for training"""
    
    if progress_callback:
        progress_callback(0.35, "Preparing features...")
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Get available features
    available_features = [c for c in FEATURE_COLUMNS if c in df.columns]
    
    # Remove NaN rows
    X = df[available_features]
    y_long = df['score_long']
    y_short = df['score_short']
    
    valid_mask = ~(X.isna().any(axis=1) | y_long.isna() | y_short.isna())
    df = df[valid_mask].reset_index(drop=True)
    
    if progress_callback:
        progress_callback(0.4, f"Prepared {len(df):,} samples")
    
    return df[available_features], df['score_long'], df['score_short'], df['timestamp'], available_features


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
    """Train XGBoost models"""
    
    if progress_callback:
        progress_callback(0.05, "Starting training...")
    
    # Load data
    df = load_training_data(symbols, timeframes, progress_callback)
    
    if len(df) == 0:
        return {'error': 'No training data found'}
    
    # Prepare features
    X, y_long, y_short, timestamps, feature_names = prepare_features(df, progress_callback)
    
    if len(X) < 100:
        return {'error': f'Not enough samples ({len(X)}). Need at least 100.'}
    
    # Split data temporally
    split_idx = int(len(X) * train_ratio)
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_long_train, y_long_test = y_long.iloc[:split_idx], y_long.iloc[split_idx:]
    y_short_train, y_short_test = y_short.iloc[:split_idx], y_short.iloc[split_idx:]
    ts_train, ts_test = timestamps.iloc[:split_idx], timestamps.iloc[split_idx:]
    
    if progress_callback:
        progress_callback(0.45, f"Split: {len(X_train):,} train / {len(X_test):,} test")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train LONG model
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
        'train_r2': r2_score(y_long_train, y_pred_long_train),
        'test_r2': r2_score(y_long_test, y_pred_long_test),
        'ranking': calculate_ranking_metrics(y_long_test, y_pred_long_test)
    }
    
    # Train SHORT model
    if progress_callback:
        progress_callback(0.75, "Training SHORT model...")
    
    model_short = XGBRegressor(**xgb_params)
    model_short.fit(X_train_scaled, y_short_train, eval_set=[(X_test_scaled, y_short_test)], verbose=False)
    
    y_pred_short_train = model_short.predict(X_train_scaled)
    y_pred_short_test = model_short.predict(X_test_scaled)
    
    metrics_short = {
        'train_rmse': np.sqrt(mean_squared_error(y_short_train, y_pred_short_train)),
        'test_rmse': np.sqrt(mean_squared_error(y_short_test, y_pred_short_test)),
        'train_r2': r2_score(y_short_train, y_pred_short_train),
        'test_r2': r2_score(y_short_test, y_pred_short_test),
        'ranking': calculate_ranking_metrics(y_short_test, y_pred_short_test)
    }
    
    # Save models
    if progress_callback:
        progress_callback(0.9, "Saving models...")
    
    model_dir = get_model_dir()
    version = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Determine primary timeframe for filename
    tf_suffix = '_'.join(timeframes) if len(timeframes) > 1 else timeframes[0]
    
    with open(model_dir / f"model_long_{tf_suffix}_{version}.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(model_dir / f"model_short_{tf_suffix}_{version}.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(model_dir / f"scaler_{tf_suffix}_{version}.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save as latest for each timeframe
    for tf in timeframes:
        with open(model_dir / f"model_long_{tf}_latest.pkl", 'wb') as f:
            pickle.dump(model_long, f)
        with open(model_dir / f"model_short_{tf}_latest.pkl", 'wb') as f:
            pickle.dump(model_short, f)
        with open(model_dir / f"scaler_{tf}_latest.pkl", 'wb') as f:
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
    
    for tf in timeframes:
        with open(model_dir / f"metadata_{tf}_{version}.json", 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        with open(model_dir / f"metadata_{tf}_latest.json", 'w') as f:
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
        'data_range': metadata['data_range'],
        'timeframes': timeframes
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL LOADING & INFERENCE
# ═══════════════════════════════════════════════════════════════════════════════

def list_available_models() -> Dict[str, Any]:
    """List all available trained models"""
    model_dir = get_model_dir()
    
    if not model_dir.exists():
        return {'models': [], 'error': None}
    
    models = {}
    
    # Find all metadata files
    for meta_file in model_dir.glob("metadata_*_latest.json"):
        try:
            with open(meta_file) as f:
                metadata = json.load(f)
            
            # Extract timeframe from filename
            name = meta_file.stem  # e.g., "metadata_15m_latest"
            parts = name.split('_')
            if len(parts) >= 3:
                timeframe = parts[1]  # "15m" or "1h"
                
                models[timeframe] = {
                    'timeframe': timeframe,
                    'version': metadata.get('version'),
                    'created_at': metadata.get('created_at'),
                    'n_features': metadata.get('n_features'),
                    'metrics_long': metadata.get('metrics_long'),
                    'metrics_short': metadata.get('metrics_short'),
                    'data_range': metadata.get('data_range'),
                    'symbols': metadata.get('symbols'),
                }
        except Exception as e:
            continue
    
    return {'models': models, 'error': None}


def load_model(timeframe: str) -> Tuple[Any, Any, Any, Dict]:
    """Load trained model for a specific timeframe"""
    model_dir = get_model_dir()
    
    model_long_path = model_dir / f"model_long_{timeframe}_latest.pkl"
    model_short_path = model_dir / f"model_short_{timeframe}_latest.pkl"
    scaler_path = model_dir / f"scaler_{timeframe}_latest.pkl"
    metadata_path = model_dir / f"metadata_{timeframe}_latest.json"
    
    if not model_long_path.exists():
        raise FileNotFoundError(f"Model not found for timeframe {timeframe}")
    
    with open(model_long_path, 'rb') as f:
        model_long = pickle.load(f)
    with open(model_short_path, 'rb') as f:
        model_short = pickle.load(f)
    with open(scaler_path, 'rb') as f:
        scaler = pickle.load(f)
    
    metadata = {}
    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)
    
    return model_long, model_short, scaler, metadata


def run_inference_realtime(timeframe: str, n_candles: int = 200) -> pd.DataFrame:
    """
    Run inference on real-time data (last N candles).
    
    Returns DataFrame with columns:
        symbol, timestamp, close, score_long, score_short, signal
    """
    # Load model
    model_long, model_short, scaler, metadata = load_model(timeframe)
    feature_names = metadata.get('feature_names', FEATURE_COLUMNS)
    
    # Load real-time data
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path), timeout=30)
    
    try:
        # Get latest candles from realtime_ohlcv (or training_data as fallback)
        # realtime_ohlcv has same structure but more recent data
        
        # First check if realtime_ohlcv has the indicators we need
        query = f"""
            SELECT symbol, timestamp, open, high, low, close, volume,
                   sma_20, sma_50, ema_12, ema_26,
                   bb_upper, bb_mid, bb_lower,
                   macd, macd_signal, macd_hist,
                   rsi, stoch_k, stoch_d,
                   atr, volume_sma, obv
            FROM realtime_ohlcv
            WHERE timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """
        
        df = pd.read_sql_query(query, conn, params=[timeframe, n_candles * 100])
        
        if len(df) == 0:
            # Fallback to training_data
            query = query.replace('realtime_ohlcv', 'training_data')
            df = pd.read_sql_query(query, conn, params=[timeframe, n_candles * 100])
        
        if len(df) == 0:
            return pd.DataFrame()
        
        # Group by symbol and get last N candles per symbol
        result_dfs = []
        
        for symbol in df['symbol'].unique():
            sym_df = df[df['symbol'] == symbol].sort_values('timestamp', ascending=False).head(n_candles)
            sym_df = sym_df.sort_values('timestamp')  # Sort ascending for inference
            
            # Prepare features
            available_features = [c for c in feature_names if c in sym_df.columns]
            X = sym_df[available_features].dropna()
            
            if len(X) == 0:
                continue
            
            # Scale and predict
            X_scaled = scaler.transform(X)
            
            pred_long = model_long.predict(X_scaled)
            pred_short = model_short.predict(X_scaled)
            
            # Create result DataFrame
            result = pd.DataFrame({
                'symbol': symbol,
                'timestamp': sym_df.iloc[-len(X):]['timestamp'].values,
                'close': sym_df.iloc[-len(X):]['close'].values,
                'score_long': pred_long,
                'score_short': pred_short,
            })
            
            # Add signal column
            result['signal'] = 'HOLD'
            result.loc[result['score_long'] > 0.5, 'signal'] = 'LONG'
            result.loc[result['score_short'] > 0.5, 'signal'] = 'SHORT'
            
            result_dfs.append(result)
        
        if result_dfs:
            return pd.concat(result_dfs, ignore_index=True)
        return pd.DataFrame()
        
    finally:
        conn.close()
