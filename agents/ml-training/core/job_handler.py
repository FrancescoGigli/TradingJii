"""
🚂 ML Training - Job Handler

Handles training job execution with Optuna hyperparameter optimization.
Updates progress in database for frontend monitoring.
"""

import os
import pickle
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scipy.stats import spearmanr
from xgboost import XGBRegressor
import optuna

from core.database import (
    get_connection,
    mark_job_running,
    update_job_progress,
    mark_job_completed,
    mark_job_failed,
    is_job_cancelled
)


# Feature columns for XGBoost training
FEATURE_COLUMNS = [
    'open', 'high', 'low', 'close', 'volume',
    'sma_20', 'sma_50', 'ema_12', 'ema_26',
    'bb_upper', 'bb_middle', 'bb_lower',
    'rsi', 'macd', 'macd_signal', 'macd_hist',
    'atr', 'adx', 'cci', 'willr', 'obv'
]


def get_model_dir() -> Path:
    """Get model output directory."""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    model_dir = Path(shared_path) / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def load_training_data(timeframe: str) -> pd.DataFrame:
    """
    Load training data from database.
    
    Tries v_xgb_training view first, falls back to ml_training_labels.
    Dynamically queries available columns.
    """
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        # Try to get columns from v_xgb_training first
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(v_xgb_training)")
            view_cols = [row[1] for row in cur.fetchall()]
            
            if view_cols:
                # Build dynamic query with available columns
                cols_to_select = ['timestamp', 'symbol', 'timeframe']
                for c in FEATURE_COLUMNS:
                    if c in view_cols:
                        cols_to_select.append(c)
                cols_to_select.extend(['score_long', 'score_short'])
                
                query = f'''
                    SELECT {', '.join(cols_to_select)}
                    FROM v_xgb_training
                    WHERE timeframe = ?
                    ORDER BY symbol, timestamp
                '''
                df = pd.read_sql_query(query, conn, params=(timeframe,))
                
                if len(df) > 0:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    print(f"   Loaded from v_xgb_training: {len(df):,} rows, {len(cols_to_select)-3} features")
                    return df
        except Exception as e:
            print(f"   v_xgb_training not available: {e}")
        
        # Fallback to ml_training_labels table
        df = pd.read_sql_query('''
            SELECT 
                timestamp, symbol, timeframe,
                open, high, low, close, volume,
                score_long, score_short
            FROM ml_training_labels
            WHERE timeframe = ?
            ORDER BY symbol, timestamp
        ''', conn, params=(timeframe,))
        
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            print(f"   Loaded from ml_training_labels: {len(df):,} rows, basic OHLCV features")
        
        return df
        
    except Exception as e:
        print(f"Error loading training data: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def prepare_features(df: pd.DataFrame) -> Tuple:
    """Prepare features and targets from dataframe."""
    available = [c for c in FEATURE_COLUMNS if c in df.columns]
    
    X = df[available].copy()
    y_long = df['score_long'].copy()
    y_short = df['score_short'].copy()
    timestamps = df['timestamp'].copy()
    
    # Remove rows with NaN
    valid = ~(X.isna().any(axis=1) | y_long.isna() | y_short.isna())
    X = X[valid]
    y_long = y_long[valid]
    y_short = y_short[valid]
    timestamps = timestamps[valid]
    
    return X, y_long, y_short, timestamps, available


def calculate_ranking_metrics(y_true, y_pred) -> Dict:
    """Calculate ranking metrics for trading."""
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


def run_training_job(job: Dict[str, Any]) -> bool:
    """
    Execute a training job with progress updates.
    
    Args:
        job: Job dict with id, timeframe, n_trials, train_ratio
    
    Returns:
        True if successful, False otherwise
    """
    job_id = job['id']
    timeframe = job['timeframe']
    n_trials = job['n_trials']
    train_ratio = job['train_ratio']
    
    print(f"\n{'='*60}")
    print(f"🚀 Starting training job {job_id} for {timeframe}")
    print(f"   Trials: {n_trials}, Train ratio: {train_ratio}")
    print(f"{'='*60}")
    
    # Total trials = LONG trials + SHORT trials
    total_trials = n_trials * 2
    
    # Mark job as running
    if not mark_job_running(job_id, total_trials):
        print(f"Failed to mark job {job_id} as running")
        return False
    
    try:
        # Load data
        print(f"\n📊 Loading {timeframe} data...")
        df = load_training_data(timeframe)
        
        if len(df) == 0:
            mark_job_failed(job_id, f"No data found for {timeframe}")
            return False
        
        print(f"   Loaded {len(df):,} samples")
        
        # Prepare features
        X, y_long, y_short, timestamps, feature_names = prepare_features(df)
        
        if len(X) < 100:
            mark_job_failed(job_id, f"Not enough samples ({len(X)}). Need at least 100.")
            return False
        
        # Temporal split
        split_idx = int(len(X) * train_ratio)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_long_train, y_long_test = y_long.iloc[:split_idx], y_long.iloc[split_idx:]
        y_short_train, y_short_test = y_short.iloc[:split_idx], y_short.iloc[split_idx:]
        ts_train, ts_test = timestamps.iloc[:split_idx], timestamps.iloc[split_idx:]
        
        print(f"   Split: {len(X_train):,} train / {len(X_test):,} test")
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Disable Optuna logging
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        
        # ===== TRAIN LONG MODEL =====
        print(f"\n📈 Training LONG model...")
        
        best_spearman_long = -1
        trial_counter = [0]  # Use list for closure
        
        def objective_long(trial):
            # Check for cancellation
            if is_job_cancelled(job_id):
                raise optuna.exceptions.OptunaError("Job cancelled")
            
            trial_counter[0] += 1
            current_trial = trial_counter[0]
            
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
            model.fit(X_train_scaled, y_long_train, 
                     eval_set=[(X_test_scaled, y_long_test)], verbose=False)
            
            y_pred = model.predict(X_test_scaled)
            spearman, _ = spearmanr(y_pred, y_long_test)
            
            nonlocal best_spearman_long
            if spearman > best_spearman_long:
                best_spearman_long = spearman
            
            # Update progress
            trial_result = {
                'trial': current_trial,
                'model': 'LONG',
                'spearman': float(spearman),
                'params': {k: v for k, v in params.items() 
                          if k not in ['objective', 'eval_metric', 'tree_method', 'verbosity', 'random_state']}
            }
            
            update_job_progress(
                job_id=job_id,
                current_trial=current_trial,
                current_model='LONG',
                best_score_long=best_spearman_long,
                trial_result=trial_result
            )
            
            print(f"   LONG Trial {current_trial}/{n_trials} | Spearman: {spearman:.4f} | Best: {best_spearman_long:.4f}")
            
            return spearman
        
        study_long = optuna.create_study(direction='maximize', 
                                         sampler=optuna.samplers.TPESampler(seed=42))
        
        try:
            study_long.optimize(objective_long, n_trials=n_trials, show_progress_bar=False)
        except optuna.exceptions.OptunaError as e:
            if "cancelled" in str(e).lower():
                print(f"Job {job_id} was cancelled")
                return False
            raise
        
        # Train final LONG model
        best_params_long = study_long.best_params
        best_params_long.update({
            'objective': 'reg:squarederror',
            'eval_metric': 'rmse',
            'tree_method': 'hist',
            'verbosity': 0,
            'random_state': 42
        })
        
        model_long = XGBRegressor(**best_params_long)
        model_long.fit(X_train_scaled, y_long_train,
                      eval_set=[(X_test_scaled, y_long_test)], verbose=False)
        y_pred_long = model_long.predict(X_test_scaled)
        
        metrics_long = {
            'test_r2': float(r2_score(y_long_test, y_pred_long)),
            'test_rmse': float(np.sqrt(mean_squared_error(y_long_test, y_pred_long))),
            'test_mae': float(mean_absolute_error(y_long_test, y_pred_long)),
            'ranking': calculate_ranking_metrics(y_long_test, y_pred_long)
        }
        
        # ===== TRAIN SHORT MODEL =====
        print(f"\n📉 Training SHORT model...")
        
        best_spearman_short = -1
        trial_counter[0] = n_trials  # Continue from where LONG left off
        
        def objective_short(trial):
            if is_job_cancelled(job_id):
                raise optuna.exceptions.OptunaError("Job cancelled")
            
            trial_counter[0] += 1
            current_trial = trial_counter[0]
            
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
            model.fit(X_train_scaled, y_short_train,
                     eval_set=[(X_test_scaled, y_short_test)], verbose=False)
            
            y_pred = model.predict(X_test_scaled)
            spearman, _ = spearmanr(y_pred, y_short_test)
            
            nonlocal best_spearman_short
            if spearman > best_spearman_short:
                best_spearman_short = spearman
            
            trial_result = {
                'trial': current_trial,
                'model': 'SHORT',
                'spearman': float(spearman),
                'params': {k: v for k, v in params.items() 
                          if k not in ['objective', 'eval_metric', 'tree_method', 'verbosity', 'random_state']}
            }
            
            update_job_progress(
                job_id=job_id,
                current_trial=current_trial,
                current_model='SHORT',
                best_score_short=best_spearman_short,
                trial_result=trial_result
            )
            
            print(f"   SHORT Trial {current_trial - n_trials}/{n_trials} | Spearman: {spearman:.4f} | Best: {best_spearman_short:.4f}")
            
            return spearman
        
        study_short = optuna.create_study(direction='maximize',
                                          sampler=optuna.samplers.TPESampler(seed=42))
        
        try:
            study_short.optimize(objective_short, n_trials=n_trials, show_progress_bar=False)
        except optuna.exceptions.OptunaError as e:
            if "cancelled" in str(e).lower():
                print(f"Job {job_id} was cancelled")
                return False
            raise
        
        # Train final SHORT model
        best_params_short = study_short.best_params
        best_params_short.update({
            'objective': 'reg:squarederror',
            'eval_metric': 'rmse',
            'tree_method': 'hist',
            'verbosity': 0,
            'random_state': 42
        })
        
        model_short = XGBRegressor(**best_params_short)
        model_short.fit(X_train_scaled, y_short_train,
                       eval_set=[(X_test_scaled, y_short_test)], verbose=False)
        y_pred_short = model_short.predict(X_test_scaled)
        
        metrics_short = {
            'test_r2': float(r2_score(y_short_test, y_pred_short)),
            'test_rmse': float(np.sqrt(mean_squared_error(y_short_test, y_pred_short))),
            'test_mae': float(mean_absolute_error(y_short_test, y_pred_short)),
            'ranking': calculate_ranking_metrics(y_short_test, y_pred_short)
        }
        
        # ===== SAVE MODELS =====
        print(f"\n💾 Saving models...")
        
        model_dir = get_model_dir()
        version = f"{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Save versioned
        with open(model_dir / f"model_long_{version}.pkl", 'wb') as f:
            pickle.dump(model_long, f)
        with open(model_dir / f"model_short_{version}.pkl", 'wb') as f:
            pickle.dump(model_short, f)
        with open(model_dir / f"scaler_{version}.pkl", 'wb') as f:
            pickle.dump(scaler, f)
        
        # Save as latest
        latest_suffix = f"{timeframe}_latest"
        with open(model_dir / f"model_long_{latest_suffix}.pkl", 'wb') as f:
            pickle.dump(model_long, f)
        with open(model_dir / f"model_short_{latest_suffix}.pkl", 'wb') as f:
            pickle.dump(model_short, f)
        with open(model_dir / f"scaler_{latest_suffix}.pkl", 'wb') as f:
            pickle.dump(scaler, f)
        
        # Feature importance
        feature_importance_long = dict(zip(
            feature_names,
            [float(x) for x in model_long.feature_importances_]
        ))
        feature_importance_short = dict(zip(
            feature_names,
            [float(x) for x in model_short.feature_importances_]
        ))
        
        # Save metadata
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
            'feature_importance_long': feature_importance_long,
            'feature_importance_short': feature_importance_short,
        }
        
        with open(model_dir / f"metadata_{version}.json", 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        with open(model_dir / f"metadata_{latest_suffix}.json", 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        # Mark job as completed
        mark_job_completed(job_id, version)
        
        print(f"\n✅ Training job {job_id} completed!")
        print(f"   LONG:  Spearman={metrics_long['ranking']['spearman_corr']:.4f}")
        print(f"   SHORT: Spearman={metrics_short['ranking']['spearman_corr']:.4f}")
        print(f"   Model version: {version}")
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ Training job {job_id} failed: {error_msg}")
        mark_job_failed(job_id, error_msg)
        return False


__all__ = ['run_training_job']
