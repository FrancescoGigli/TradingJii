"""
📦 Local Models Service
=======================

Service to load and manage locally trained XGBoost models.
Provides model loading, metadata access, and inference capabilities.
"""

import os
import json
import pickle
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ModelInfo:
    """Container for model information."""
    version: str
    timeframe: str
    created_at: str
    n_features: int
    n_train_samples: int
    n_test_samples: int
    training_duration_seconds: float
    feature_names: List[str]
    metrics_long: Dict[str, Any]
    metrics_short: Dict[str, Any]
    feature_importance_long: Dict[str, float]
    feature_importance_short: Dict[str, float]
    best_params_long: Dict[str, Any]
    best_params_short: Dict[str, Any]
    data_range: Dict[str, str]
    training_mode: str = "local"


def get_models_dir() -> Path:
    """Get the models directory path."""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    return Path(shared_path) / "models"


def list_available_models() -> List[Dict[str, Any]]:
    """
    List all available trained models.
    
    Returns:
        List of dicts with version, timeframe, created_at
    """
    models_dir = get_models_dir()
    if not models_dir.exists():
        return []
    
    models = []
    
    # Find all metadata files
    for meta_file in models_dir.glob("metadata_*.json"):
        if "_latest" in meta_file.name:
            continue  # Skip latest symlinks
        
        try:
            with open(meta_file, 'r') as f:
                meta = json.load(f)
                models.append({
                    'version': meta.get('version', 'Unknown'),
                    'timeframe': meta.get('timeframe', 'Unknown'),
                    'created_at': meta.get('created_at', 'Unknown'),
                    'n_features': meta.get('n_features', 0),
                    'spearman_long': meta.get('metrics_long', {}).get('ranking', {}).get('spearman_corr', 0),
                    'spearman_short': meta.get('metrics_short', {}).get('ranking', {}).get('spearman_corr', 0),
                })
        except Exception:
            continue
    
    # Sort by created_at descending
    models.sort(key=lambda x: x['created_at'], reverse=True)
    return models


def load_model_metadata(timeframe: str) -> Optional[ModelInfo]:
    """
    Load metadata for a specific timeframe's latest model.
    
    Args:
        timeframe: '15m' or '1h'
    
    Returns:
        ModelInfo object or None
    """
    models_dir = get_models_dir()
    metadata_file = models_dir / f"metadata_{timeframe}_latest.json"
    
    if not metadata_file.exists():
        return None
    
    try:
        with open(metadata_file, 'r') as f:
            meta = json.load(f)
        
        return ModelInfo(
            version=meta.get('version', 'Unknown'),
            timeframe=meta.get('timeframe', timeframe),
            created_at=meta.get('created_at', 'Unknown'),
            n_features=meta.get('n_features', 0),
            n_train_samples=meta.get('n_train_samples', 0),
            n_test_samples=meta.get('n_test_samples', 0),
            training_duration_seconds=meta.get('training_duration_seconds', 0),
            feature_names=meta.get('feature_names', []),
            metrics_long=meta.get('metrics_long', {}),
            metrics_short=meta.get('metrics_short', {}),
            feature_importance_long=meta.get('feature_importance_long', {}),
            feature_importance_short=meta.get('feature_importance_short', {}),
            best_params_long=meta.get('best_params_long', {}),
            best_params_short=meta.get('best_params_short', {}),
            data_range=meta.get('data_range', {}),
            training_mode=meta.get('training_mode', 'local')
        )
    except Exception as e:
        print(f"Error loading metadata for {timeframe}: {e}")
        return None


def load_models(timeframe: str) -> Tuple[Any, Any, Any]:
    """
    Load trained models and scaler for a timeframe.
    
    Args:
        timeframe: '15m' or '1h'
    
    Returns:
        Tuple of (model_long, model_short, scaler) or (None, None, None)
    """
    models_dir = get_models_dir()
    
    model_long_path = models_dir / f"model_long_{timeframe}_latest.pkl"
    model_short_path = models_dir / f"model_short_{timeframe}_latest.pkl"
    scaler_path = models_dir / f"scaler_{timeframe}_latest.pkl"
    
    if not all(p.exists() for p in [model_long_path, model_short_path, scaler_path]):
        return None, None, None
    
    try:
        with open(model_long_path, 'rb') as f:
            model_long = pickle.load(f)
        with open(model_short_path, 'rb') as f:
            model_short = pickle.load(f)
        with open(scaler_path, 'rb') as f:
            scaler = pickle.load(f)
        
        return model_long, model_short, scaler
    except Exception as e:
        print(f"Error loading models for {timeframe}: {e}")
        return None, None, None


def model_exists(timeframe: str) -> bool:
    """Check if a trained model exists for a timeframe."""
    models_dir = get_models_dir()
    model_file = models_dir / f"model_long_{timeframe}_latest.pkl"
    return model_file.exists()


def _get_realtime_db_path() -> str:
    """Get the path to the real-time trading database."""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    return f"{shared_path}/data_cache/trading_data.db"


def _convert_symbol_to_ccxt_format(symbol: str) -> str:
    """
    Convert symbol from simple format to CCXT format used by data-fetcher.
    
    Examples:
        BTCUSDT -> BTC/USDT:USDT
        ETHUSDT -> ETH/USDT:USDT
    """
    # If already in CCXT format, return as-is
    if '/' in symbol:
        return symbol
    
    # Remove USDT suffix and add CCXT format
    if symbol.endswith('USDT'):
        base = symbol[:-4]  # Remove 'USDT'
        return f"{base}/USDT:USDT"
    
    return symbol


def run_inference(
    timeframe: str,
    symbol: str = "BTCUSDT",
    n_candles: int = 200
) -> Optional[pd.DataFrame]:
    """
    Run inference on a symbol using the trained model.
    
    Uses real-time data from data-fetcher's realtime_ohlcv table.
    
    Args:
        timeframe: '15m' or '1h'
        symbol: Trading pair symbol
        n_candles: Number of candles to process
    
    Returns:
        DataFrame with timestamp, ohlcv, score_long, score_short, signal
    """
    import sqlite3
    
    # Load models
    model_long, model_short, scaler = load_models(timeframe)
    if model_long is None:
        return None
    
    # Load metadata to get feature names
    meta = load_model_metadata(timeframe)
    if meta is None:
        return None
    
    feature_names = meta.feature_names
    
    # Connect to real-time database (trading_data.db)
    db_path = _get_realtime_db_path()
    if not Path(db_path).exists():
        print(f"Real-time database not found: {db_path}")
        return None
    
    try:
        conn = sqlite3.connect(db_path, timeout=30)
        
        # Convert symbol to CCXT format (BTCUSDT -> BTC/USDT:USDT)
        ccxt_symbol = _convert_symbol_to_ccxt_format(symbol)
        
        # Get data from realtime_ohlcv (data-fetcher table)
        query = f'''
            SELECT timestamp, open, high, low, close, volume,
                   sma_20, sma_50, ema_12, ema_26,
                   bb_upper, bb_mid as bb_middle, bb_lower,
                   rsi, macd, macd_signal, macd_hist,
                   stoch_k, stoch_d, atr, volume_sma, obv
            FROM realtime_ohlcv
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
        '''
        
        df = pd.read_sql_query(query, conn, params=(ccxt_symbol, timeframe, n_candles))
        
        if len(df) == 0:
            return None
        
        # Reverse to chronological order
        df = df.iloc[::-1].reset_index(drop=True)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Get available features
        available_features = [f for f in feature_names if f in df.columns]
        
        if len(available_features) < 3:
            return None
        
        # Prepare features
        X = df[available_features].copy()
        
        # Handle NaN
        X = X.fillna(method='ffill').fillna(0)
        
        # Scale features
        X_scaled = scaler.transform(X)
        
        # Run inference
        df['score_long'] = model_long.predict(X_scaled)
        df['score_short'] = model_short.predict(X_scaled)
        
        # Generate signals
        df['signal'] = 'HOLD'
        df.loc[df['score_long'] > 0.7, 'signal'] = 'STRONG BUY'
        df.loc[(df['score_long'] > 0.5) & (df['score_long'] <= 0.7), 'signal'] = 'BUY'
        df.loc[df['score_short'] > 0.7, 'signal'] = 'STRONG SELL'
        df.loc[(df['score_short'] > 0.5) & (df['score_short'] <= 0.7), 'signal'] = 'SELL'
        
        # Calculate net score
        df['net_score'] = df['score_long'] - df['score_short']
        
        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume',
                   'score_long', 'score_short', 'net_score', 'signal']]
        
    except Exception as e:
        print(f"Error running inference: {e}")
        return None
    finally:
        conn.close()


def get_latest_signals(
    timeframe: str,
    symbol: str = "BTCUSDT"
) -> Optional[Dict[str, Any]]:
    """
    Get the latest inference signals for a symbol.
    
    Returns dict with current scores and signal.
    """
    df = run_inference(timeframe, symbol, n_candles=10)
    
    if df is None or len(df) == 0:
        return None
    
    latest = df.iloc[-1]
    
    return {
        'timestamp': str(latest['timestamp']),
        'close': float(latest['close']),
        'score_long': float(latest['score_long']),
        'score_short': float(latest['score_short']),
        'net_score': float(latest['net_score']),
        'signal': latest['signal'],
    }


__all__ = [
    'ModelInfo',
    'get_models_dir',
    'list_available_models',
    'load_model_metadata',
    'load_models',
    'model_exists',
    'run_inference',
    'get_latest_signals'
]
