#!/usr/bin/env python3
"""
Train XGBoost models for both 15m and 1h timeframes.
Run this inside Docker container or with proper environment.
"""

import sqlite3
import pandas as pd
import numpy as np
import pickle
import json
from pathlib import Path
from datetime import datetime
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scipy.stats import spearmanr

try:
    import optuna
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

from xgboost import XGBRegressor

# Configuration
DB_PATH = '/app/shared/data_cache/trading_data.db'
MODEL_DIR = Path('/app/shared/models')
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Features - using v_xgb_training VIEW columns
FEATURE_COLUMNS = ['open', 'high', 'low', 'close', 'volume', 'rsi', 'atr', 'macd']


def load_training_data(timeframe: str):
    """Load data from v_xgb_training VIEW."""
    conn = sqlite3.connect(DB_PATH)
    
    df = pd.read_sql_query('''
        SELECT 
            timestamp, symbol, timeframe,
            open, high, low, close, volume,
            rsi, atr, macd,
            score_long, score_short
        FROM v_xgb_training
        WHERE timeframe = ?
        ORDER BY symbol, timestamp
    ''', conn, params=(timeframe,))
    
    conn.close()
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    print(f"[{timeframe}] Loaded {len(df):,} samples")
    return df


def prepare_features(df: pd.DataFrame):
    """Prepare features and targets."""
    available = [c for c in FEATURE_COLUMNS if c in df.columns]
    
    X = df[available].copy()
    y_long = df['score_long'].copy()
    y_short = df['score_short'].copy()
    timestamps = df['timestamp'].copy()
    
    # Remove NaN
    valid = ~(X.isna().any(axis=1) | y_long.isna() | y_short.isna())
    X = X[valid]
    y_long = y_long[valid]
    y_short = y_short[valid]
    timestamps = timestamps[valid]
    
    print(f"  Prepared {len(X):,} samples with {len(available)} features")
    return X, y_long, y_short, timestamps, available


def calculate_ranking_metrics(y_true, y_pred):
    """Calculate ranking metrics."""
    spearman_corr, spearman_pval = spearmanr(y_pred, y_true)
    
    metrics = {
        'spearman_corr': float(spearman_corr),
        'spearman_pval': float(spearman_pval),
    }
    
    for k_pct in [1, 5, 10, 20]:
        k = max(1, int(len(y_pred) * k_pct / 100))
        top_k_idx = np.argsort(y_pred)[-k:]
        top_k_true = y_true.iloc[top_k_idx] if hasattr(y_true, 'iloc') else y_true[top_k_idx]
        
        metrics[f'top{k_pct}pct_avg_score'] = float(np.mean(top_k_true))
        metrics[f'top{k_pct}pct_positive'] = float((top_k_true > 0).mean() * 100)
    
    return metrics


def objective_long(trial, X_train, X_test, y_train, y_test):
    """Optuna objective for LONG model."""
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 30),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'objective': 'reg:squarederror',
        'eval_metric': 'rmse',
        'tree_method': 'hist',
        'verbosity': 0,
        'random_state': 42
    }
    
    model = XGBRegressor(**params)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    
    y_pred = model.predict(X_test)
    spearman, _ = spearmanr(y_pred, y_test)
    
    return spearman  # Maximize Spearman correlation


def train_with_optuna(timeframe: str, n_trials: int = 30, train_ratio: float = 0.8):
    """Train models using Optuna hyperparameter optimization."""
    print(f"\n{'='*60}")
    print(f"TRAINING {timeframe.upper()} with Optuna ({n_trials} trials)")
    print(f"{'='*60}")
    
    # Load and prepare data
    df = load_training_data(timeframe)
    X, y_long, y_short, timestamps, feature_names = prepare_features(df)
    
    if len(X) < 100:
        print(f"ERROR: Not enough samples ({len(X)})")
        return None
    
    # Temporal split
    split_idx = int(len(X) * train_ratio)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_long_train, y_long_test = y_long.iloc[:split_idx], y_long.iloc[split_idx:]
    y_short_train, y_short_test = y_short.iloc[:split_idx], y_short.iloc[split_idx:]
    ts_train, ts_test = timestamps.iloc[:split_idx], timestamps.iloc[split_idx:]
    
    print(f"  Split: {len(X_train):,} train / {len(X_test):,} test")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Optuna study for LONG
    print(f"\n[LONG] Optimizing hyperparameters...")
    study_long = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=42))
    study_long.optimize(
        lambda trial: objective_long(trial, X_train_scaled, X_test_scaled, y_long_train, y_long_test),
        n_trials=n_trials,
        show_progress_bar=True
    )
    
    best_params_long = study_long.best_params
    best_params_long.update({
        'objective': 'reg:squarederror',
        'eval_metric': 'rmse',
        'tree_method': 'hist',
        'verbosity': 0,
        'random_state': 42
    })
    
    print(f"  Best Spearman (LONG): {study_long.best_value:.4f}")
    
    # Train final LONG model
    model_long = XGBRegressor(**best_params_long)
    model_long.fit(X_train_scaled, y_long_train, eval_set=[(X_test_scaled, y_long_test)], verbose=False)
    y_pred_long = model_long.predict(X_test_scaled)
    
    metrics_long = {
        'test_r2': float(r2_score(y_long_test, y_pred_long)),
        'test_rmse': float(np.sqrt(mean_squared_error(y_long_test, y_pred_long))),
        'test_mae': float(mean_absolute_error(y_long_test, y_pred_long)),
        'ranking': calculate_ranking_metrics(y_long_test, y_pred_long)
    }
    
    # Optuna study for SHORT
    print(f"\n[SHORT] Optimizing hyperparameters...")
    study_short = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=42))
    study_short.optimize(
        lambda trial: objective_long(trial, X_train_scaled, X_test_scaled, y_short_train, y_short_test),
        n_trials=n_trials,
        show_progress_bar=True
    )
    
    best_params_short = study_short.best_params
    best_params_short.update({
        'objective': 'reg:squarederror',
        'eval_metric': 'rmse',
        'tree_method': 'hist',
        'verbosity': 0,
        'random_state': 42
    })
    
    print(f"  Best Spearman (SHORT): {study_short.best_value:.4f}")
    
    # Train final SHORT model
    model_short = XGBRegressor(**best_params_short)
    model_short.fit(X_train_scaled, y_short_train, eval_set=[(X_test_scaled, y_short_test)], verbose=False)
    y_pred_short = model_short.predict(X_test_scaled)
    
    metrics_short = {
        'test_r2': float(r2_score(y_short_test, y_pred_short)),
        'test_rmse': float(np.sqrt(mean_squared_error(y_short_test, y_pred_short))),
        'test_mae': float(mean_absolute_error(y_short_test, y_pred_short)),
        'ranking': calculate_ranking_metrics(y_short_test, y_pred_short)
    }
    
    # Save models with timeframe suffix
    version = f"{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    with open(MODEL_DIR / f"model_long_{version}.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(MODEL_DIR / f"model_short_{version}.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(MODEL_DIR / f"scaler_{version}.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save as latest for this timeframe
    latest_suffix = f"{timeframe}_latest"
    with open(MODEL_DIR / f"model_long_{latest_suffix}.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(MODEL_DIR / f"model_short_{latest_suffix}.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(MODEL_DIR / f"scaler_{latest_suffix}.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    
    # Also save as generic "latest" (overwrite for each timeframe)
    with open(MODEL_DIR / "model_long_latest.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(MODEL_DIR / "model_short_latest.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(MODEL_DIR / "scaler_latest.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    
    # Metadata
    metadata = {
        'version': version,
        'created_at': datetime.now().isoformat(),
        'timeframe': timeframe,
        'feature_names': feature_names,
        'n_features': len(feature_names),
        'n_trials': n_trials,
        'train_ratio': train_ratio,
        'best_params_long': best_params_long,
        'best_params_short': best_params_short,
        'metrics_long': metrics_long,
        'metrics_short': metrics_short,
        'data_range': {
            'train_start': str(ts_train.iloc[0]),
            'train_end': str(ts_train.iloc[-1]),
            'test_start': str(ts_test.iloc[0]),
            'test_end': str(ts_test.iloc[-1]),
        },
        'n_train_samples': len(X_train),
        'n_test_samples': len(X_test),
    }
    
    with open(MODEL_DIR / f"metadata_{version}.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    with open(MODEL_DIR / f"metadata_{latest_suffix}.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    with open(MODEL_DIR / "metadata_latest.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    
    # Print results
    print(f"\n{'='*60}")
    print(f"RESULTS {timeframe.upper()}")
    print(f"{'='*60}")
    print(f"  LONG Model:")
    print(f"    R²: {metrics_long['test_r2']:.4f}")
    print(f"    RMSE: {metrics_long['test_rmse']:.6f}")
    print(f"    Spearman: {metrics_long['ranking']['spearman_corr']:.4f}")
    print(f"    Top1% Positive: {metrics_long['ranking']['top1pct_positive']:.1f}%")
    print(f"  SHORT Model:")
    print(f"    R²: {metrics_short['test_r2']:.4f}")
    print(f"    RMSE: {metrics_short['test_rmse']:.6f}")
    print(f"    Spearman: {metrics_short['ranking']['spearman_corr']:.4f}")
    print(f"    Top1% Positive: {metrics_short['ranking']['top1pct_positive']:.1f}%")
    print(f"\n  Saved to: {MODEL_DIR}")
    print(f"  Version: {version}")
    
    return version


if __name__ == '__main__':
    import sys
    
    # Disable Optuna logging
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    
    n_trials = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    
    print("="*60)
    print("  XGBoost Training - Both Timeframes")
    print(f"  Optuna Trials: {n_trials}")
    print("="*60)
    
    # Train 15m
    train_with_optuna('15m', n_trials=n_trials)
    
    # Train 1h
    train_with_optuna('1h', n_trials=n_trials)
    
    print("\n" + "="*60)
    print("  TRAINING COMPLETE!")
    print("="*60)
