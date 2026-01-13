#!/usr/bin/env python3
"""
🚀 ML Training Script - Standalone
===================================

Trains two XGBoost Regressor models:
- model_long: predicts score_long
- model_short: predicts score_short

Usage:
    cd agents/ml-training
    python train.py

Or with symbol filter:
    python train.py --symbol BTC --timeframe 15m

Author: Trae ML Pipeline
"""

import os
import sys
import argparse
import sqlite3
import pickle
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scipy.stats import spearmanr
from xgboost import XGBRegressor

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Database path (relative to script location)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DB_PATH = PROJECT_ROOT / "shared" / "data_cache" / "trading_data.db"
MODEL_OUTPUT_DIR = PROJECT_ROOT / "shared" / "models"

# Train/test split ratio (temporal, NO shuffle!)
TRAIN_RATIO = 0.8

# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE COLUMNS - Market state at time t (NO future info!)
# ═══════════════════════════════════════════════════════════════════════════════

FEATURE_COLUMNS = [
    # OHLCV base
    'open', 'high', 'low', 'close', 'volume',
    
    # Trend / Moving Averages
    'sma_20', 'sma_50', 'ema_12', 'ema_26',
    
    # Bollinger Bands
    'bb_upper', 'bb_mid', 'bb_lower', 'bb_width', 'bb_position',
    
    # Momentum
    'rsi', 'macd', 'macd_signal', 'macd_hist',
    'stoch_k', 'stoch_d',
    
    # Volatility
    'atr', 'atr_pct',
    
    # Volume
    'obv', 'volume_sma',
    
    # ADX (trend strength)
    'adx_14', 'adx_14_norm',
    
    # Returns
    'ret_5', 'ret_10', 'ret_20',
    
    # EMA distances
    'ema_20_dist', 'ema_50_dist', 'ema_200_dist',
    
    # EMA crossovers
    'ema_20_50_cross', 'ema_50_200_cross',
    
    # RSI normalized
    'rsi_14_norm', 'macd_hist_norm',
    
    # Trend direction
    'trend_direction', 'momentum_10', 'momentum_20',
    
    # Volatility features
    'vol_5', 'vol_10', 'vol_20',
    
    # Range
    'range_pct_5', 'range_pct_10', 'range_pct_20',
    
    # Volume analysis
    'vol_percentile', 'vol_ratio', 'vol_change', 'obv_slope',
    'vwap_dist', 'vol_stability',
    
    # Candlestick
    'body_pct', 'candle_direction', 'upper_shadow_pct', 'lower_shadow_pct',
    'gap_pct', 'consecutive_up', 'consecutive_down',
    
    # Speed/Acceleration
    'speed_5', 'speed_20', 'accel_5', 'accel_20',
    
    # Percentiles
    'ret_percentile_50', 'ret_percentile_100',
    
    # Price position
    'price_position_20', 'price_position_50', 'price_position_100',
    'dist_from_high_20', 'dist_from_low_20',
]

# ═══════════════════════════════════════════════════════════════════════════════
# TARGET COLUMNS - What the model predicts
# ═══════════════════════════════════════════════════════════════════════════════

TARGET_LONG = 'score_long'
TARGET_SHORT = 'score_short'

# ═══════════════════════════════════════════════════════════════════════════════
# EXCLUDE COLUMNS - NEVER use these as features (future leakage!)
# ═══════════════════════════════════════════════════════════════════════════════

EXCLUDE_COLUMNS = [
    # Targets (labels)
    'score_long', 'score_short',
    'realized_return_long', 'realized_return_short',
    'mfe_long', 'mae_long', 'mfe_short', 'mae_short',
    'bars_held_long', 'bars_held_short',
    'exit_type_long', 'exit_type_short',
    
    # Label config (not features)
    'trailing_stop_pct', 'max_bars', 'time_penalty_lambda', 'trading_cost',
    'generated_at',
    
    # Identifiers (not features)
    'id', 'timestamp', 'symbol', 'timeframe',
]


# ═══════════════════════════════════════════════════════════════════════════════
# XGBoost Parameters for Regression
# ═══════════════════════════════════════════════════════════════════════════════

XGBOOST_PARAMS = {
    'objective': 'reg:squarederror',
    'eval_metric': 'rmse',
    'tree_method': 'hist',
    'max_depth': 6,
    'learning_rate': 0.05,
    'colsample_bytree': 0.8,
    'subsample': 0.8,
    'min_child_weight': 10,
    'n_estimators': 500,
    'early_stopping_rounds': 50,
    'verbosity': 1,
    'random_state': 42,
}


def print_banner():
    """Print startup banner"""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           🚀 ML TRAINING PIPELINE - SCORE PREDICTION             ║
║                                                                  ║
║  Target:  score_long, score_short (continuous)                   ║
║  Model:   XGBoost Regressor                                      ║
║  Split:   80/20 Temporal (NO shuffle)                            ║
╚══════════════════════════════════════════════════════════════════╝
    """)


def load_dataset(db_path: Path, symbol: str = None, timeframe: str = None) -> pd.DataFrame:
    """
    Load ML training dataset from SQLite database.
    Uses the same JOIN query as the frontend export.
    """
    print(f"\n📊 Loading dataset from: {db_path}")
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(str(db_path))
    
    try:
        # Check tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='historical_ohlcv'")
        if not cursor.fetchone():
            print("❌ Table 'historical_ohlcv' not found")
            sys.exit(1)
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_training_labels'")
        if not cursor.fetchone():
            print("❌ Table 'ml_training_labels' not found")
            sys.exit(1)
        
        # Get indicator columns from historical_ohlcv
        cursor.execute("PRAGMA table_info(historical_ohlcv)")
        historical_cols = [row[1] for row in cursor.fetchall()]
        
        # Columns to exclude from historical (get OHLCV from labels)
        exclude_cols = {'id', 'symbol', 'timeframe', 'timestamp', 'fetched_at', 'interpolated',
                        'open', 'high', 'low', 'close', 'volume'}
        
        indicator_cols = [c for c in historical_cols if c not in exclude_cols]
        indicator_select = ', '.join([f'h.{c}' for c in indicator_cols])
        
        # Build query
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
            INNER JOIN historical_ohlcv h 
                ON l.symbol = h.symbol 
                AND l.timeframe = h.timeframe 
                AND l.timestamp = h.timestamp
        '''
        
        # Add filters
        conditions = []
        params = []
        
        if symbol:
            conditions.append('l.symbol LIKE ?')
            params.append(f'%{symbol}%')
        
        if timeframe:
            conditions.append('l.timeframe = ?')
            params.append(timeframe)
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += ' ORDER BY l.symbol, l.timeframe, l.timestamp ASC'
        
        # Execute
        df = pd.read_sql_query(query, conn, params=params if params else None)
        
        print(f"   ✅ Loaded {len(df):,} rows from database")
        
        return df
        
    finally:
        conn.close()


def validate_data_quality(df: pd.DataFrame, features: list, timeframe: str = '15m') -> dict:
    """
    🔍 Rigorous data quality validation for ML training.
    
    Checks:
    1. NaN in features
    2. NaN in targets
    3. Consecutive timestamps (no gaps)
    
    Returns:
        dict with validation statistics
    """
    print("\n🔍 DATA QUALITY VALIDATION")
    print("="*60)
    
    validation = {
        'total_rows': len(df),
        'nan_features': {},
        'nan_targets': {},
        'timestamp_gaps': [],
        'is_valid': True
    }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 1. CHECK NaN IN FEATURES
    # ═══════════════════════════════════════════════════════════════════════════
    
    print("\n   📊 Checking NaN in FEATURES...")
    total_nan_features = 0
    
    for col in features:
        if col in df.columns:
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                validation['nan_features'][col] = nan_count
                total_nan_features += nan_count
    
    if total_nan_features > 0:
        print(f"   ⚠️ Found {total_nan_features:,} NaN values in features:")
        for col, count in sorted(validation['nan_features'].items(), key=lambda x: -x[1])[:5]:
            pct = count / len(df) * 100
            print(f"      - {col}: {count:,} ({pct:.2f}%)")
    else:
        print(f"   ✅ NO NaN in features!")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 2. CHECK NaN IN TARGETS
    # ═══════════════════════════════════════════════════════════════════════════
    
    print("\n   🎯 Checking NaN in TARGETS...")
    
    for target in [TARGET_LONG, TARGET_SHORT]:
        nan_count = df[target].isna().sum()
        if nan_count > 0:
            validation['nan_targets'][target] = nan_count
            validation['is_valid'] = False
            pct = nan_count / len(df) * 100
            print(f"   ❌ {target}: {nan_count:,} NaN ({pct:.2f}%)")
        else:
            print(f"   ✅ {target}: NO NaN")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 3. CHECK TIMESTAMP CONSECUTIVITY
    # ═══════════════════════════════════════════════════════════════════════════
    
    print("\n   ⏱️ Checking timestamp consecutivity...")
    
    # Expected interval based on timeframe
    tf_intervals = {
        '15m': pd.Timedelta(minutes=15),
        '1h': pd.Timedelta(hours=1),
        '4h': pd.Timedelta(hours=4),
        '1d': pd.Timedelta(days=1),
    }
    
    # Process per symbol/timeframe
    groups = df.groupby(['symbol', 'timeframe'])
    total_gaps = 0
    
    for (symbol, tf), group in groups:
        expected_interval = tf_intervals.get(tf, pd.Timedelta(minutes=15))
        
        group = group.sort_values('timestamp')
        ts_diff = group['timestamp'].diff()
        
        # Find gaps (where diff != expected interval, allowing for first row)
        gaps = ts_diff[ts_diff > expected_interval * 1.5]  # 1.5x tolerance
        
        if len(gaps) > 0:
            total_gaps += len(gaps)
            validation['timestamp_gaps'].append({
                'symbol': symbol,
                'timeframe': tf,
                'n_gaps': len(gaps),
                'max_gap': str(gaps.max()),
                'sample_gaps': gaps.head(3).tolist()
            })
    
    if total_gaps > 0:
        print(f"   ⚠️ Found {total_gaps} timestamp gaps:")
        for gap_info in validation['timestamp_gaps'][:3]:
            print(f"      - {gap_info['symbol']}/{gap_info['timeframe']}: {gap_info['n_gaps']} gaps (max: {gap_info['max_gap']})")
    else:
        print(f"   ✅ Timestamps are CONSECUTIVE (no gaps)")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════════════════
    
    print("\n" + "="*60)
    print("   📋 VALIDATION SUMMARY:")
    print(f"      Total rows:      {validation['total_rows']:,}")
    print(f"      NaN in features: {total_nan_features:,}")
    print(f"      NaN in targets:  {sum(validation['nan_targets'].values()):,}")
    print(f"      Timestamp gaps:  {total_gaps}")
    
    if validation['is_valid'] and total_nan_features == 0:
        print(f"   \n   ✅ DATA IS CLEAN AND READY FOR TRAINING!")
    else:
        print(f"   \n   ⚠️ Some issues found - will filter problematic rows")
    
    print("="*60)
    
    return validation


def prepare_dataset(df: pd.DataFrame) -> tuple:
    """
    Prepare dataset for training:
    - Convert timestamp
    - RIGOROSA validazione NaN e timestamp
    - Filter NaN (from first complete row)
    - Select feature columns
    - Extract targets
    """
    print("\n🔧 Preparing dataset...")
    
    # Convert timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Sort by timestamp
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Find first row without any NaN in features
    rows_before = len(df)
    
    # Check which features are available
    available_features = [c for c in FEATURE_COLUMNS if c in df.columns]
    missing_features = [c for c in FEATURE_COLUMNS if c not in df.columns]
    
    if missing_features:
        print(f"   ⚠️ Missing {len(missing_features)} features: {missing_features[:5]}...")
    
    print(f"   📊 Using {len(available_features)} features")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RIGOROUS DATA QUALITY VALIDATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    validation = validate_data_quality(df, available_features)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FILTER ROWS WITH NaN
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Find first row where all features are non-null
    feature_df = df[available_features]
    first_complete_idx = None
    
    for idx in range(len(df)):
        if not feature_df.iloc[idx].isnull().any():
            first_complete_idx = idx
            break
    
    if first_complete_idx is None:
        print("❌ No complete rows found (all have NaN)")
        sys.exit(1)
    
    # Keep from first complete row
    df = df.iloc[first_complete_idx:].reset_index(drop=True)
    rows_removed = rows_before - len(df)
    
    print(f"\n   ✅ Filtered {rows_removed:,} warm-up rows (NaN indicators)")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FINAL CHECK: NO NaN IN FEATURES AND TARGETS
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Double-check: remove any rows with residual NaN
    X_temp = df[available_features]
    y_long_temp = df[TARGET_LONG]
    y_short_temp = df[TARGET_SHORT]
    
    # Valid rows mask (no NaN in features AND no NaN in targets)
    valid_mask = ~(X_temp.isna().any(axis=1) | y_long_temp.isna() | y_short_temp.isna())
    
    rows_with_nan = (~valid_mask).sum()
    if rows_with_nan > 0:
        print(f"   🧹 Removing {rows_with_nan:,} additional rows with residual NaN")
        df = df[valid_mask].reset_index(drop=True)
    
    print(f"   ✅ FINAL Dataset: {len(df):,} rows from {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ABSOLUTE CHECK: ASSERT NO NaN
    # ═══════════════════════════════════════════════════════════════════════════
    
    X = df[available_features].copy()
    y_long = df[TARGET_LONG].copy()
    y_short = df[TARGET_SHORT].copy()
    timestamps = df['timestamp'].copy()
    
    # Final ASSERT
    assert X.isna().sum().sum() == 0, f"❌ ERROR: Still NaN in features!"
    assert y_long.isna().sum() == 0, f"❌ ERROR: Still NaN in score_long!"
    assert y_short.isna().sum() == 0, f"❌ ERROR: Still NaN in score_short!"
    
    print(f"   ✅ ASSERT PASSED: Zero NaN in features and targets!")
    
    return X, y_long, y_short, timestamps, available_features


def temporal_split(X, y, timestamps, train_ratio=0.8):
    """
    Split data temporally (NO shuffle!).
    Earlier data for training, later data for testing.
    """
    split_idx = int(len(X) * train_ratio)
    
    X_train = X.iloc[:split_idx]
    X_test = X.iloc[split_idx:]
    y_train = y.iloc[:split_idx]
    y_test = y.iloc[split_idx:]
    
    ts_train = timestamps.iloc[:split_idx]
    ts_test = timestamps.iloc[split_idx:]
    
    return X_train, X_test, y_train, y_test, ts_train, ts_test


def calculate_ranking_metrics(y_true: np.ndarray, y_pred: np.ndarray, realized_returns: np.ndarray = None) -> dict:
    """
    Calculate ranking metrics that matter for trading.
    
    These metrics answer: "When the model says 'this is better than that', is it right?"
    
    Args:
        y_true: True scores
        y_pred: Predicted scores
        realized_returns: Optional realized returns for Precision@K analysis
    
    Returns:
        Dictionary with ranking metrics
    """
    # 1. Spearman Rank Correlation
    # Measures how well the model ranks opportunities (not absolute values)
    spearman_corr, spearman_pval = spearmanr(y_pred, y_true)
    
    # 2. Precision@K metrics
    # "If I only trade the top K% by predicted score, how good are they?"
    precision_metrics = {}
    
    for k_pct in [1, 5, 10, 20]:
        # Get top K% by predicted score
        k = int(len(y_pred) * k_pct / 100)
        if k < 1:
            k = 1
        
        # Indices of top K predictions
        top_k_idx = np.argsort(y_pred)[-k:]
        
        # Metrics for top K
        top_k_true_scores = y_true.iloc[top_k_idx] if hasattr(y_true, 'iloc') else y_true[top_k_idx]
        
        # Average true score of top K predictions
        avg_true_score = np.mean(top_k_true_scores)
        
        # % of top K that have positive true score
        pct_positive = (top_k_true_scores > 0).mean() * 100
        
        # If we have realized returns, use those too
        if realized_returns is not None:
            top_k_returns = realized_returns.iloc[top_k_idx] if hasattr(realized_returns, 'iloc') else realized_returns[top_k_idx]
            avg_return = np.mean(top_k_returns) * 100  # as percentage
            precision_metrics[f'top{k_pct}pct_avg_return'] = avg_return
        
        precision_metrics[f'top{k_pct}pct_avg_score'] = avg_true_score
        precision_metrics[f'top{k_pct}pct_positive'] = pct_positive
    
    return {
        'spearman_corr': spearman_corr,
        'spearman_pval': spearman_pval,
        **precision_metrics
    }


def print_ranking_metrics(metrics: dict, model_name: str):
    """Print ranking metrics in a nice format"""
    print(f"\n   🎯 RANKING METRICS ({model_name}):")
    print(f"   ╔══════════════════════════════════════════════════╗")
    print(f"   ║  Spearman Correlation: {metrics['spearman_corr']:>8.4f}  (p={metrics['spearman_pval']:.2e})")
    
    if metrics['spearman_corr'] > 0.10:
        quality = "🟢 EXCELLENT"
    elif metrics['spearman_corr'] > 0.05:
        quality = "🟡 GOOD"
    elif metrics['spearman_corr'] > 0.02:
        quality = "🟠 WEAK"
    else:
        quality = "🔴 NO SIGNAL"
    
    print(f"   ║  Signal Quality:       {quality}")
    print(f"   ╠══════════════════════════════════════════════════╣")
    print(f"   ║  Precision@K (only trade top predictions):")
    print(f"   ║  ┌────────┬────────────┬──────────────┐")
    print(f"   ║  │ Top K% │ Avg Score  │ % Positive   │")
    print(f"   ║  ├────────┼────────────┼──────────────┤")
    
    for k_pct in [1, 5, 10, 20]:
        avg_score = metrics.get(f'top{k_pct}pct_avg_score', 0)
        pct_pos = metrics.get(f'top{k_pct}pct_positive', 0)
        print(f"   ║  │  {k_pct:>3}% │ {avg_score:>10.6f} │ {pct_pos:>10.1f}%  │")
    
    print(f"   ║  └────────┴────────────┴──────────────┘")
    print(f"   ╚══════════════════════════════════════════════════╝")


def train_model(X_train, y_train, X_test, y_test, model_name: str):
    """
    Train XGBoost Regressor model.
    """
    print(f"\n{'📈' if 'long' in model_name.lower() else '📉'} Training {model_name}...")
    print(f"   Train: {len(X_train):,} samples")
    print(f"   Test:  {len(X_test):,} samples")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train model
    model = XGBRegressor(**XGBOOST_PARAMS)
    
    model.fit(
        X_train_scaled, y_train,
        eval_set=[(X_test_scaled, y_test)],
        verbose=False
    )
    
    # Predictions
    y_pred_train = model.predict(X_train_scaled)
    y_pred_test = model.predict(X_test_scaled)
    
    # Metrics
    metrics = {
        'train_rmse': np.sqrt(mean_squared_error(y_train, y_pred_train)),
        'test_rmse': np.sqrt(mean_squared_error(y_test, y_pred_test)),
        'train_mae': mean_absolute_error(y_train, y_pred_train),
        'test_mae': mean_absolute_error(y_test, y_pred_test),
        'train_r2': r2_score(y_train, y_pred_train),
        'test_r2': r2_score(y_test, y_pred_test),
    }
    
    print(f"\n   📊 Results:")
    print(f"   ├── Train RMSE: {metrics['train_rmse']:.6f}")
    print(f"   ├── Test RMSE:  {metrics['test_rmse']:.6f}")
    print(f"   ├── Train MAE:  {metrics['train_mae']:.6f}")
    print(f"   ├── Test MAE:   {metrics['test_mae']:.6f}")
    print(f"   ├── Train R²:   {metrics['train_r2']:.4f}")
    print(f"   └── Test R²:    {metrics['test_r2']:.4f}")
    
    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': X_train.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print(f"\n   🏆 Top 10 Features:")
    for i, row in feature_importance.head(10).iterrows():
        print(f"   {row['feature']:25s} {row['importance']:.4f}")
    
    return model, scaler, metrics, feature_importance


def save_models(model_long, model_short, scaler, feature_names, metrics_long, metrics_short, output_dir: Path):
    """
    Save trained models, scaler, and metadata.
    """
    print(f"\n💾 Saving models to: {output_dir}")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Version string
    version = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save models
    model_long_path = output_dir / f"model_long_{version}.pkl"
    model_short_path = output_dir / f"model_short_{version}.pkl"
    scaler_path = output_dir / f"scaler_{version}.pkl"
    metadata_path = output_dir / f"metadata_{version}.json"
    
    with open(model_long_path, 'wb') as f:
        pickle.dump(model_long, f)
    print(f"   ✅ {model_long_path.name}")
    
    with open(model_short_path, 'wb') as f:
        pickle.dump(model_short, f)
    print(f"   ✅ {model_short_path.name}")
    
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)
    print(f"   ✅ {scaler_path.name}")
    
    # Save metadata
    metadata = {
        'version': version,
        'created_at': datetime.now().isoformat(),
        'feature_names': feature_names,
        'n_features': len(feature_names),
        'xgboost_params': XGBOOST_PARAMS,
        'train_ratio': TRAIN_RATIO,
        'metrics_long': metrics_long,
        'metrics_short': metrics_short,
    }
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    print(f"   ✅ {metadata_path.name}")
    
    # Also save as "latest" for easy loading
    with open(output_dir / "model_long_latest.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(output_dir / "model_short_latest.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(output_dir / "scaler_latest.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    with open(output_dir / "metadata_latest.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    
    print(f"   ✅ latest versions saved")
    
    return version


def main():
    """Main training pipeline"""
    parser = argparse.ArgumentParser(description='ML Training Pipeline')
    parser.add_argument('--symbol', type=str, default=None, help='Filter by symbol (e.g., BTC)')
    parser.add_argument('--timeframe', type=str, default=None, help='Filter by timeframe (e.g., 15m)')
    parser.add_argument('--db-path', type=str, default=None, help='Custom database path')
    parser.add_argument('--output-dir', type=str, default=None, help='Custom output directory')
    args = parser.parse_args()
    
    print_banner()
    
    # Paths
    db_path = Path(args.db_path) if args.db_path else DB_PATH
    output_dir = Path(args.output_dir) if args.output_dir else MODEL_OUTPUT_DIR
    
    # Load data
    df = load_dataset(db_path, args.symbol, args.timeframe)
    
    if len(df) == 0:
        print("❌ No data found!")
        sys.exit(1)
    
    # Prepare dataset
    X, y_long, y_short, timestamps, feature_names = prepare_dataset(df)
    
    # Split temporally
    print(f"\n🔀 Temporal split: {int(TRAIN_RATIO*100)}% train / {int((1-TRAIN_RATIO)*100)}% test")
    
    X_train, X_test, y_long_train, y_long_test, ts_train, ts_test = temporal_split(
        X, y_long, timestamps, TRAIN_RATIO
    )
    _, _, y_short_train, y_short_test, _, _ = temporal_split(
        X, y_short, timestamps, TRAIN_RATIO
    )
    
    print(f"   Train period: {ts_train.iloc[0]} → {ts_train.iloc[-1]}")
    print(f"   Test period:  {ts_test.iloc[0]} → {ts_test.iloc[-1]}")
    
    # Train LONG model
    model_long, scaler, metrics_long, fi_long = train_model(
        X_train, y_long_train, X_test, y_long_test, "LONG Model"
    )
    
    # Train SHORT model (use same scaler)
    X_train_scaled = scaler.transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    print(f"\n📉 Training SHORT Model...")
    print(f"   Train: {len(X_train):,} samples")
    print(f"   Test:  {len(X_test):,} samples")
    
    model_short = XGBRegressor(**XGBOOST_PARAMS)
    model_short.fit(
        X_train_scaled, y_short_train,
        eval_set=[(X_test_scaled, y_short_test)],
        verbose=False
    )
    
    # SHORT metrics
    y_pred_train_short = model_short.predict(X_train_scaled)
    y_pred_test_short = model_short.predict(X_test_scaled)
    
    metrics_short = {
        'train_rmse': np.sqrt(mean_squared_error(y_short_train, y_pred_train_short)),
        'test_rmse': np.sqrt(mean_squared_error(y_short_test, y_pred_test_short)),
        'train_mae': mean_absolute_error(y_short_train, y_pred_train_short),
        'test_mae': mean_absolute_error(y_short_test, y_pred_test_short),
        'train_r2': r2_score(y_short_train, y_pred_train_short),
        'test_r2': r2_score(y_short_test, y_pred_test_short),
    }
    
    print(f"\n   📊 Results:")
    print(f"   ├── Train RMSE: {metrics_short['train_rmse']:.6f}")
    print(f"   ├── Test RMSE:  {metrics_short['test_rmse']:.6f}")
    print(f"   ├── Train R²:   {metrics_short['train_r2']:.4f}")
    print(f"   └── Test R²:    {metrics_short['test_r2']:.4f}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RANKING METRICS - The ones that REALLY matter for trading!
    # ═══════════════════════════════════════════════════════════════════════════
    
    print("\n" + "="*70)
    print("   🎯 RANKING METRICS - Trading Decision Quality")
    print("="*70)
    
    # LONG ranking metrics
    y_pred_test_long = model_long.predict(X_test_scaled)
    ranking_long = calculate_ranking_metrics(y_long_test, y_pred_test_long)
    print_ranking_metrics(ranking_long, "LONG")
    
    # SHORT ranking metrics
    ranking_short = calculate_ranking_metrics(y_short_test, y_pred_test_short)
    print_ranking_metrics(ranking_short, "SHORT")
    
    # Add ranking metrics to saved metrics
    metrics_long['ranking'] = ranking_long
    metrics_short['ranking'] = ranking_short
    
    # Save models
    version = save_models(
        model_long, model_short, scaler, feature_names,
        metrics_long, metrics_short, output_dir
    )
    
    # Summary
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║                    ✅ TRAINING COMPLETE                          ║
╠══════════════════════════════════════════════════════════════════╣
║  Version:       {version}                               ║
║  Dataset:       {len(X):>10,} samples                            ║
║  Features:      {len(feature_names):>10} columns                             ║
╠══════════════════════════════════════════════════════════════════╣
║  LONG Model:    R² = {metrics_long['test_r2']:.4f}  |  RMSE = {metrics_long['test_rmse']:.6f}          ║
║  SHORT Model:   R² = {metrics_short['test_r2']:.4f}  |  RMSE = {metrics_short['test_rmse']:.6f}          ║
╠══════════════════════════════════════════════════════════════════╣
║  Models saved to: {str(output_dir):<45} ║
╚══════════════════════════════════════════════════════════════════╝
    """)


if __name__ == '__main__':
    main()
