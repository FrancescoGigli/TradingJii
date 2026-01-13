#!/usr/bin/env python3
"""
🎯 ML Training with Optuna Hyperparameter Tuning
=================================================

Automatically finds optimal XGBoost hyperparameters using Optuna.
Optimizes for Spearman correlation (ranking quality) - what matters for trading!

Usage:
    cd agents/ml-training
    pip install optuna
    python train_optuna.py --trials 50

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
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scipy.stats import spearmanr
from xgboost import XGBRegressor

# Optuna for hyperparameter tuning
import optuna
from optuna.samplers import TPESampler

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DB_PATH = PROJECT_ROOT / "shared" / "data_cache" / "trading_data.db"
MODEL_OUTPUT_DIR = PROJECT_ROOT / "shared" / "models"

# Train/Validation/Test split
TRAIN_RATIO = 0.7
VAL_RATIO = 0.15
TEST_RATIO = 0.15

# Optuna defaults
DEFAULT_N_TRIALS = 50
DEFAULT_TIMEOUT = None  # seconds, or None for no timeout

# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE COLUMNS (same as train.py)
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

TARGET_LONG = 'score_long'
TARGET_SHORT = 'score_short'


def print_banner():
    """Print startup banner"""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║       🎯 OPTUNA HYPERPARAMETER TUNING - XGBoost Regressor            ║
║                                                                      ║
║  Objective:  Maximize Spearman Correlation (Ranking Quality)         ║
║  Method:     TPE (Tree-structured Parzen Estimator)                  ║
║  Split:      70/15/15 Temporal (Train/Val/Test)                      ║
╚══════════════════════════════════════════════════════════════════════╝
    """)


def load_dataset(db_path: Path, symbol: str = None, timeframe: str = None) -> pd.DataFrame:
    """Load ML training dataset from SQLite database."""
    print(f"\n📊 Loading dataset from: {db_path}")
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(str(db_path))
    
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(historical_ohlcv)")
        historical_cols = [row[1] for row in cursor.fetchall()]
        
        exclude_cols = {'id', 'symbol', 'timeframe', 'timestamp', 'fetched_at', 'interpolated',
                        'open', 'high', 'low', 'close', 'volume'}
        
        indicator_cols = [c for c in historical_cols if c not in exclude_cols]
        indicator_select = ', '.join([f'h.{c}' for c in indicator_cols])
        
        query = f'''
            SELECT 
                l.timestamp, l.symbol, l.timeframe,
                l.open, l.high, l.low, l.close, l.volume,
                {indicator_select},
                l.score_long, l.score_short,
                l.realized_return_long, l.realized_return_short
            FROM ml_training_labels l
            INNER JOIN historical_ohlcv h 
                ON l.symbol = h.symbol 
                AND l.timeframe = h.timeframe 
                AND l.timestamp = h.timestamp
        '''
        
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
        
        df = pd.read_sql_query(query, conn, params=params if params else None)
        print(f"   ✅ Loaded {len(df):,} rows")
        return df
        
    finally:
        conn.close()


def prepare_dataset(df: pd.DataFrame) -> tuple:
    """Prepare dataset for training."""
    print("\n🔧 Preparing dataset...")
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    available_features = [c for c in FEATURE_COLUMNS if c in df.columns]
    print(f"   📊 Using {len(available_features)} features")
    
    # Find first complete row (no NaN)
    feature_df = df[available_features]
    first_complete_idx = None
    
    for idx in range(len(df)):
        if not feature_df.iloc[idx].isnull().any():
            first_complete_idx = idx
            break
    
    if first_complete_idx is None:
        print("❌ No complete rows found")
        sys.exit(1)
    
    df = df.iloc[first_complete_idx:].reset_index(drop=True)
    
    # Remove any remaining NaN rows
    X_temp = df[available_features]
    y_long_temp = df[TARGET_LONG]
    y_short_temp = df[TARGET_SHORT]
    
    valid_mask = ~(X_temp.isna().any(axis=1) | y_long_temp.isna() | y_short_temp.isna())
    df = df[valid_mask].reset_index(drop=True)
    
    X = df[available_features].copy()
    y_long = df[TARGET_LONG].copy()
    y_short = df[TARGET_SHORT].copy()
    timestamps = df['timestamp'].copy()
    
    print(f"   ✅ Final dataset: {len(df):,} rows")
    
    return X, y_long, y_short, timestamps, available_features


def temporal_split_three_way(X, y, timestamps):
    """
    Split data into train/validation/test sets temporally.
    """
    n = len(X)
    train_end = int(n * TRAIN_RATIO)
    val_end = int(n * (TRAIN_RATIO + VAL_RATIO))
    
    X_train = X.iloc[:train_end]
    X_val = X.iloc[train_end:val_end]
    X_test = X.iloc[val_end:]
    
    y_train = y.iloc[:train_end]
    y_val = y.iloc[train_end:val_end]
    y_test = y.iloc[val_end:]
    
    ts_train = timestamps.iloc[:train_end]
    ts_val = timestamps.iloc[train_end:val_end]
    ts_test = timestamps.iloc[val_end:]
    
    return (X_train, X_val, X_test, y_train, y_val, y_test, ts_train, ts_val, ts_test)


class OptunaObjective:
    """
    Optuna objective for XGBoost hyperparameter tuning.
    Optimizes for Spearman correlation on validation set.
    """
    
    def __init__(self, X_train, X_val, y_train, y_val, scaler, model_type='long'):
        self.X_train_scaled = scaler.transform(X_train)
        self.X_val_scaled = scaler.transform(X_val)
        self.y_train = y_train.values
        self.y_val = y_val.values
        self.model_type = model_type
        self.best_spearman = -1
        self.best_params = None
        self.trial_count = 0
    
    def __call__(self, trial):
        self.trial_count += 1
        
        # Hyperparameter search space
        params = {
            'objective': 'reg:squarederror',
            'eval_metric': 'rmse',
            'tree_method': 'hist',
            'verbosity': 0,
            'random_state': 42,
            
            # Tunable parameters
            'n_estimators': trial.suggest_int('n_estimators', 500, 3000),
            'max_depth': trial.suggest_int('max_depth', 4, 12),
            'learning_rate': trial.suggest_float('learning_rate', 0.005, 0.1, log=True),
            'min_child_weight': trial.suggest_int('min_child_weight', 5, 50),
            'subsample': trial.suggest_float('subsample', 0.5, 0.95),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 0.95),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 1.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 2.0, log=True),
            'gamma': trial.suggest_float('gamma', 1e-8, 1.0, log=True),
        }
        
        # Add early stopping
        params['early_stopping_rounds'] = 100
        
        try:
            # Train model
            model = XGBRegressor(**params)
            model.fit(
                self.X_train_scaled, self.y_train,
                eval_set=[(self.X_val_scaled, self.y_val)],
                verbose=False
            )
            
            # Predict on validation
            y_pred = model.predict(self.X_val_scaled)
            
            # Calculate Spearman correlation (what matters for ranking!)
            spearman_corr, _ = spearmanr(y_pred, self.y_val)
            
            # Also calculate R² and RMSE for logging
            r2 = r2_score(self.y_val, y_pred)
            rmse = np.sqrt(mean_squared_error(self.y_val, y_pred))
            
            # Track best
            if spearman_corr > self.best_spearman:
                self.best_spearman = spearman_corr
                self.best_params = params.copy()
                print(f"   🌟 New best! Trial {self.trial_count}: Spearman={spearman_corr:.4f}, R²={r2:.4f}")
            
            # Report intermediate values for pruning
            trial.report(spearman_corr, step=0)
            
            # Prune unpromising trials
            if trial.should_prune():
                raise optuna.TrialPruned()
            
            return spearman_corr
            
        except Exception as e:
            print(f"   ⚠️ Trial {self.trial_count} failed: {e}")
            return -1


def run_optuna_tuning(X_train, X_val, y_train, y_val, scaler, 
                      model_type: str, n_trials: int, timeout: int = None):
    """
    Run Optuna hyperparameter tuning.
    """
    print(f"\n{'📈' if model_type == 'long' else '📉'} Tuning {model_type.upper()} model...")
    print(f"   Trials: {n_trials}")
    print(f"   Train samples: {len(X_train):,}")
    print(f"   Val samples: {len(X_val):,}")
    
    # Create objective
    objective = OptunaObjective(X_train, X_val, y_train, y_val, scaler, model_type)
    
    # Create study with TPE sampler
    study = optuna.create_study(
        direction='maximize',  # Maximize Spearman correlation
        sampler=TPESampler(seed=42),
        study_name=f'{model_type}_tuning'
    )
    
    # Optimize
    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout,
        show_progress_bar=True,
        gc_after_trial=True
    )
    
    # Results
    print(f"\n   📊 Tuning Results for {model_type.upper()}:")
    print(f"   ╔══════════════════════════════════════════════════╗")
    print(f"   ║  Best Spearman:     {study.best_value:.4f}                     ║")
    print(f"   ║  Trials completed:  {len(study.trials):>5}                       ║")
    print(f"   ╠══════════════════════════════════════════════════╣")
    print(f"   ║  Best Parameters:                                ║")
    
    for key, value in study.best_params.items():
        if isinstance(value, float):
            print(f"   ║    {key:20s} {value:>10.6f}          ║")
        else:
            print(f"   ║    {key:20s} {value:>10}          ║")
    
    print(f"   ╚══════════════════════════════════════════════════╝")
    
    return study.best_params, study


def train_final_model(X_train, X_val, X_test, y_train, y_val, y_test, 
                      scaler, best_params: dict, model_type: str):
    """
    Train final model with best parameters on train+val, evaluate on test.
    """
    print(f"\n🏋️ Training FINAL {model_type.upper()} model with best params...")
    
    # Combine train and val for final training
    X_train_full = pd.concat([X_train, X_val])
    y_train_full = pd.concat([y_train, y_val])
    
    X_train_scaled = scaler.transform(X_train_full)
    X_test_scaled = scaler.transform(X_test)
    
    # Build final params (remove early stopping from best_params for final train)
    final_params = {
        'objective': 'reg:squarederror',
        'eval_metric': 'rmse',
        'tree_method': 'hist',
        'verbosity': 0,
        'random_state': 42,
        **best_params,
        'early_stopping_rounds': None  # No early stopping for final
    }
    
    # Train
    model = XGBRegressor(**final_params)
    model.fit(X_train_scaled, y_train_full.values, verbose=False)
    
    # Evaluate on test
    y_pred_test = model.predict(X_test_scaled)
    
    # Metrics
    test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
    test_mae = mean_absolute_error(y_test, y_pred_test)
    test_r2 = r2_score(y_test, y_pred_test)
    spearman_corr, spearman_pval = spearmanr(y_pred_test, y_test)
    
    metrics = {
        'test_rmse': test_rmse,
        'test_mae': test_mae,
        'test_r2': test_r2,
        'test_spearman': spearman_corr,
        'test_spearman_pval': spearman_pval,
        'best_params': best_params,
    }
    
    # Ranking metrics (Precision@K)
    for k_pct in [1, 5, 10, 20]:
        k = max(1, int(len(y_pred_test) * k_pct / 100))
        top_k_idx = np.argsort(y_pred_test)[-k:]
        top_k_true_scores = y_test.iloc[top_k_idx] if hasattr(y_test, 'iloc') else y_test[top_k_idx]
        
        metrics[f'top{k_pct}pct_avg_score'] = np.mean(top_k_true_scores)
        metrics[f'top{k_pct}pct_positive'] = (top_k_true_scores > 0).mean() * 100
    
    print(f"\n   📊 FINAL TEST Results ({model_type.upper()}):")
    print(f"   ╔══════════════════════════════════════════════════╗")
    print(f"   ║  RMSE:              {test_rmse:.6f}                  ║")
    print(f"   ║  MAE:               {test_mae:.6f}                  ║")
    print(f"   ║  R²:                {test_r2:.4f}                      ║")
    print(f"   ║  Spearman:          {spearman_corr:.4f}                      ║")
    print(f"   ╠══════════════════════════════════════════════════╣")
    print(f"   ║  Precision@K (TOP predictions quality):          ║")
    print(f"   ║    Top 1%:  {metrics['top1pct_positive']:>5.1f}% positive, avg={metrics['top1pct_avg_score']:.6f}  ║")
    print(f"   ║    Top 5%:  {metrics['top5pct_positive']:>5.1f}% positive, avg={metrics['top5pct_avg_score']:.6f}  ║")
    print(f"   ║    Top 10%: {metrics['top10pct_positive']:>5.1f}% positive, avg={metrics['top10pct_avg_score']:.6f}  ║")
    print(f"   ║    Top 20%: {metrics['top20pct_positive']:>5.1f}% positive, avg={metrics['top20pct_avg_score']:.6f}  ║")
    print(f"   ╚══════════════════════════════════════════════════╝")
    
    return model, metrics


def save_models(model_long, model_short, scaler, feature_names, 
                metrics_long, metrics_short, best_params_long, best_params_short,
                output_dir: Path):
    """Save models, scaler, and metadata."""
    print(f"\n💾 Saving models to: {output_dir}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    version = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save models
    with open(output_dir / f"model_long_{version}.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(output_dir / f"model_short_{version}.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(output_dir / f"scaler_{version}.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save best params
    with open(output_dir / f"best_params_{version}.json", 'w') as f:
        json.dump({
            'long': best_params_long,
            'short': best_params_short
        }, f, indent=2, default=str)
    
    # Save metadata
    metadata = {
        'version': version,
        'created_at': datetime.now().isoformat(),
        'tuning_method': 'optuna_tpe',
        'feature_names': feature_names,
        'n_features': len(feature_names),
        'split_ratios': {'train': TRAIN_RATIO, 'val': VAL_RATIO, 'test': TEST_RATIO},
        'metrics_long': metrics_long,
        'metrics_short': metrics_short,
        'best_params_long': best_params_long,
        'best_params_short': best_params_short,
    }
    
    with open(output_dir / f"metadata_{version}.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    
    # Save as "latest"
    with open(output_dir / "model_long_latest.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(output_dir / "model_short_latest.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(output_dir / "scaler_latest.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    with open(output_dir / "best_params_latest.json", 'w') as f:
        json.dump({
            'long': best_params_long,
            'short': best_params_short
        }, f, indent=2, default=str)
    with open(output_dir / "metadata_latest.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    
    print(f"   ✅ All files saved with version: {version}")
    
    return version


def main():
    parser = argparse.ArgumentParser(description='Optuna Hyperparameter Tuning')
    parser.add_argument('--trials', type=int, default=DEFAULT_N_TRIALS, 
                        help=f'Number of Optuna trials (default: {DEFAULT_N_TRIALS})')
    parser.add_argument('--timeout', type=int, default=None,
                        help='Timeout in seconds (default: None)')
    parser.add_argument('--symbol', type=str, default=None, help='Filter by symbol')
    parser.add_argument('--timeframe', type=str, default=None, help='Filter by timeframe')
    parser.add_argument('--db-path', type=str, default=None, help='Custom database path')
    parser.add_argument('--output-dir', type=str, default=None, help='Custom output directory')
    args = parser.parse_args()
    
    print_banner()
    
    # Suppress Optuna logs (we have our own)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    
    # Paths
    db_path = Path(args.db_path) if args.db_path else DB_PATH
    output_dir = Path(args.output_dir) if args.output_dir else MODEL_OUTPUT_DIR
    
    # Load data
    df = load_dataset(db_path, args.symbol, args.timeframe)
    
    if len(df) == 0:
        print("❌ No data found!")
        sys.exit(1)
    
    # Prepare
    X, y_long, y_short, timestamps, feature_names = prepare_dataset(df)
    
    # Split into train/val/test
    print(f"\n🔀 Temporal split: {int(TRAIN_RATIO*100)}% train / {int(VAL_RATIO*100)}% val / {int(TEST_RATIO*100)}% test")
    
    (X_train, X_val, X_test, 
     y_long_train, y_long_val, y_long_test, 
     ts_train, ts_val, ts_test) = temporal_split_three_way(X, y_long, timestamps)
    
    _, _, _, y_short_train, y_short_val, y_short_test, _, _, _ = temporal_split_three_way(X, y_short, timestamps)
    
    print(f"   Train:  {ts_train.iloc[0]} → {ts_train.iloc[-1]} ({len(X_train):,} samples)")
    print(f"   Val:    {ts_val.iloc[0]} → {ts_val.iloc[-1]} ({len(X_val):,} samples)")
    print(f"   Test:   {ts_test.iloc[0]} → {ts_test.iloc[-1]} ({len(X_test):,} samples)")
    
    # Scale features
    scaler = StandardScaler()
    scaler.fit(X_train)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # OPTUNA TUNING
    # ═══════════════════════════════════════════════════════════════════════════
    
    start_time = datetime.now()
    
    # Tune LONG model
    best_params_long, study_long = run_optuna_tuning(
        X_train, X_val, y_long_train, y_long_val, scaler,
        model_type='long', n_trials=args.trials, timeout=args.timeout
    )
    
    # Tune SHORT model
    best_params_short, study_short = run_optuna_tuning(
        X_train, X_val, y_short_train, y_short_val, scaler,
        model_type='short', n_trials=args.trials, timeout=args.timeout
    )
    
    tuning_time = (datetime.now() - start_time).total_seconds()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRAIN FINAL MODELS
    # ═══════════════════════════════════════════════════════════════════════════
    
    model_long, metrics_long = train_final_model(
        X_train, X_val, X_test, 
        y_long_train, y_long_val, y_long_test,
        scaler, best_params_long, 'long'
    )
    
    model_short, metrics_short = train_final_model(
        X_train, X_val, X_test,
        y_short_train, y_short_val, y_short_test,
        scaler, best_params_short, 'short'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SAVE
    # ═══════════════════════════════════════════════════════════════════════════
    
    version = save_models(
        model_long, model_short, scaler, feature_names,
        metrics_long, metrics_short,
        best_params_long, best_params_short,
        output_dir
    )
    
    # Summary
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║                    ✅ OPTUNA TUNING COMPLETE                         ║
╠══════════════════════════════════════════════════════════════════════╣
║  Version:          {version}                                 ║
║  Tuning time:      {tuning_time/60:.1f} minutes                                  ║
║  Trials per model: {args.trials}                                          ║
║  Dataset size:     {len(X):,} samples                              ║
╠══════════════════════════════════════════════════════════════════════╣
║  LONG MODEL:                                                         ║
║    Spearman:  {metrics_long['test_spearman']:.4f}   |  R²:  {metrics_long['test_r2']:.4f}   |  RMSE: {metrics_long['test_rmse']:.6f}     ║
║  SHORT MODEL:                                                        ║
║    Spearman:  {metrics_short['test_spearman']:.4f}   |  R²:  {metrics_short['test_r2']:.4f}   |  RMSE: {metrics_short['test_rmse']:.6f}     ║
╠══════════════════════════════════════════════════════════════════════╣
║  Models saved to: {str(output_dir):<47} ║
╚══════════════════════════════════════════════════════════════════════╝
    """)


if __name__ == '__main__':
    main()
