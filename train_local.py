#!/usr/bin/env python3
"""
🚀 Local ML Training Script
===========================

Train XGBoost models locally without Docker.
Faster and more resource-efficient than container-based training.

Usage:
    python train_local.py --timeframe 15m --trials 30
    python train_local.py --timeframe 1h --trials 20 --verbose

Arguments:
    --timeframe: '15m' or '1h' (required)
    --trials: Number of Optuna trials (default: 20)
    --train-ratio: Train/test split ratio (default: 0.8)
    --verbose: Show detailed output for each trial
    --output-dir: Custom output directory (default: shared/models)
"""

import os
import sys
import json
import pickle
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple, List

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scipy.stats import spearmanr
from xgboost import XGBRegressor
import optuna
from tqdm import tqdm


# Feature columns for XGBoost training (21 features)
FEATURE_COLUMNS = [
    # OHLCV (5)
    'open', 'high', 'low', 'close', 'volume',
    # Moving Averages (4)
    'sma_20', 'sma_50', 'ema_12', 'ema_26',
    # Bollinger Bands (3)
    'bb_upper', 'bb_middle', 'bb_lower',
    # Momentum (4)
    'rsi', 'macd', 'macd_signal', 'macd_hist',
    # Stochastic (2)
    'stoch_k', 'stoch_d',
    # Other (3)
    'atr', 'volume_sma', 'obv'
]


def print_banner():
    """Print startup banner."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              🚀 LOCAL ML TRAINING (No Docker)                    ║
║                                                                  ║
║  Train XGBoost + Optuna models locally for faster performance    ║
║  Output compatible with frontend visualization                   ║
╚══════════════════════════════════════════════════════════════════╝
    """)


def get_database_path() -> Path:
    """Get path to SQLite database."""
    # Try different locations
    candidates = [
        Path("shared/data_cache/trading_data.db"),
        Path("shared/crypto_data.db"),
        Path("agents/frontend/shared/crypto_data.db"),
        Path(os.environ.get('SHARED_DATA_PATH', 'shared')) / "data_cache" / "trading_data.db",
    ]
    
    for path in candidates:
        if path.exists():
            return path
    
    # Default
    return Path("shared/data_cache/trading_data.db")


def load_training_data(timeframe: str, verbose: bool = False) -> pd.DataFrame:
    """Load training data from database."""
    import sqlite3
    
    db_path = get_database_path()
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        sys.exit(1)
    
    print(f"📂 Loading data from: {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    
    try:
        # Try v_xgb_training view first
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(v_xgb_training)")
            view_cols = [row[1] for row in cur.fetchall()]
            
            if view_cols:
                available_features = [c for c in FEATURE_COLUMNS if c in view_cols]
                missing_features = [c for c in FEATURE_COLUMNS if c not in view_cols]
                
                if verbose:
                    print(f"\n📊 Feature Check:")
                    print(f"   Available: {len(available_features)}/{len(FEATURE_COLUMNS)}")
                    if missing_features:
                        print(f"   Missing: {', '.join(missing_features[:5])}...")
                
                cols_to_select = ['timestamp', 'symbol', 'timeframe']
                cols_to_select.extend(available_features)
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
                    print(f"✅ Loaded {len(df):,} samples with {len(available_features)} features")
                    return df
                    
        except Exception as e:
            if verbose:
                print(f"   ⚠️ v_xgb_training not available: {e}")
        
        # Fallback to ml_training_labels
        print("⚠️ Using fallback table (limited features)")
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
            print(f"📦 Loaded {len(df):,} samples (5 OHLCV features only)")
        
        return df
        
    finally:
        conn.close()


def prepare_features(df: pd.DataFrame) -> Tuple:
    """Prepare features and targets from dataframe."""
    available = [c for c in FEATURE_COLUMNS if c in df.columns]
    
    X = df[available].copy()
    y_long = df['score_long'].copy()
    y_short = df['score_short'].copy()
    timestamps = df['timestamp'].copy()
    symbols = df['symbol'].copy() if 'symbol' in df.columns else None
    
    # Remove rows with NaN
    valid = ~(X.isna().any(axis=1) | y_long.isna() | y_short.isna())
    X = X[valid]
    y_long = y_long[valid]
    y_short = y_short[valid]
    timestamps = timestamps[valid]
    if symbols is not None:
        symbols = symbols[valid]
    
    return X, y_long, y_short, timestamps, available, symbols


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


def create_optuna_objective(
    X_train_scaled, y_train, X_test_scaled, y_test,
    model_type: str, verbose: bool, pbar
):
    """Create Optuna objective function."""
    best_score = [-1]  # Use list for closure
    
    def objective(trial):
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
            'random_state': 42,
            'n_jobs': -1  # Use all cores
        }
        
        model = XGBRegressor(**params)
        model.fit(X_train_scaled, y_train,
                 eval_set=[(X_test_scaled, y_test)], verbose=False)
        
        y_pred = model.predict(X_test_scaled)
        spearman, _ = spearmanr(y_pred, y_test)
        
        if spearman > best_score[0]:
            best_score[0] = spearman
        
        pbar.update(1)
        pbar.set_postfix({
            'spearman': f'{spearman:.4f}',
            'best': f'{best_score[0]:.4f}'
        })
        
        return spearman
    
    return objective, best_score


def train_model(
    timeframe: str,
    n_trials: int = 20,
    train_ratio: float = 0.8,
    output_dir: Path = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Train XGBoost models with Optuna optimization.
    
    Returns metadata dict with all training results.
    """
    start_time = datetime.now()
    
    # Set output directory
    if output_dir is None:
        output_dir = Path("shared/models")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n⚙️  Configuration:")
    print(f"   Timeframe: {timeframe}")
    print(f"   Trials: {n_trials}")
    print(f"   Train ratio: {train_ratio}")
    print(f"   Output: {output_dir}")
    
    # Load data
    print(f"\n📊 Loading {timeframe} data...")
    df = load_training_data(timeframe, verbose)
    
    if len(df) == 0:
        print("❌ No training data found!")
        return None
    
    # Prepare features
    X, y_long, y_short, timestamps, feature_names, symbols = prepare_features(df)
    
    if len(X) < 100:
        print(f"❌ Not enough samples ({len(X)}). Need at least 100.")
        return None
    
    print(f"\n📈 Data Summary:")
    print(f"   Total samples: {len(X):,}")
    print(f"   Features: {len(feature_names)}")
    print(f"   Date range: {timestamps.min()} → {timestamps.max()}")
    if symbols is not None:
        print(f"   Symbols: {symbols.nunique()}")
    
    # Temporal split
    split_idx = int(len(X) * train_ratio)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_long_train, y_long_test = y_long.iloc[:split_idx], y_long.iloc[split_idx:]
    y_short_train, y_short_test = y_short.iloc[:split_idx], y_short.iloc[split_idx:]
    ts_train, ts_test = timestamps.iloc[:split_idx], timestamps.iloc[split_idx:]
    
    print(f"\n🔀 Train/Test Split:")
    print(f"   Train: {len(X_train):,} samples ({train_ratio*100:.0f}%)")
    print(f"   Test: {len(X_test):,} samples ({(1-train_ratio)*100:.0f}%)")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Disable Optuna logging
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    
    # Store trial history
    trials_long = []
    trials_short = []
    
    # ===== TRAIN LONG MODEL =====
    print(f"\n{'='*50}")
    print(f"📈 Training LONG Model ({n_trials} trials)")
    print(f"{'='*50}")
    
    with tqdm(total=n_trials, desc="LONG", ncols=80) as pbar:
        objective_long, best_long = create_optuna_objective(
            X_train_scaled, y_long_train, X_test_scaled, y_long_test,
            'LONG', verbose, pbar
        )
        
        study_long = optuna.create_study(
            direction='maximize',
            sampler=optuna.samplers.TPESampler(seed=42)
        )
        study_long.optimize(objective_long, n_trials=n_trials, show_progress_bar=False)
    
    # Final LONG model
    best_params_long = study_long.best_params.copy()
    best_params_long.update({
        'objective': 'reg:squarederror',
        'eval_metric': 'rmse',
        'tree_method': 'hist',
        'verbosity': 0,
        'random_state': 42,
        'n_jobs': -1
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
    
    print(f"\n✅ LONG Model Results:")
    print(f"   Spearman: {metrics_long['ranking']['spearman_corr']:.4f}")
    print(f"   R²: {metrics_long['test_r2']:.4f}")
    print(f"   Top1% Positive: {metrics_long['ranking']['top1pct_positive']:.1f}%")
    
    # ===== TRAIN SHORT MODEL =====
    print(f"\n{'='*50}")
    print(f"📉 Training SHORT Model ({n_trials} trials)")
    print(f"{'='*50}")
    
    with tqdm(total=n_trials, desc="SHORT", ncols=80) as pbar:
        objective_short, best_short = create_optuna_objective(
            X_train_scaled, y_short_train, X_test_scaled, y_short_test,
            'SHORT', verbose, pbar
        )
        
        study_short = optuna.create_study(
            direction='maximize',
            sampler=optuna.samplers.TPESampler(seed=42)
        )
        study_short.optimize(objective_short, n_trials=n_trials, show_progress_bar=False)
    
    # Final SHORT model
    best_params_short = study_short.best_params.copy()
    best_params_short.update({
        'objective': 'reg:squarederror',
        'eval_metric': 'rmse',
        'tree_method': 'hist',
        'verbosity': 0,
        'random_state': 42,
        'n_jobs': -1
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
    
    print(f"\n✅ SHORT Model Results:")
    print(f"   Spearman: {metrics_short['ranking']['spearman_corr']:.4f}")
    print(f"   R²: {metrics_short['test_r2']:.4f}")
    print(f"   Top1% Positive: {metrics_short['ranking']['top1pct_positive']:.1f}%")
    
    # ===== SAVE MODELS =====
    print(f"\n{'='*50}")
    print(f"💾 Saving Models")
    print(f"{'='*50}")
    
    version = f"{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Save versioned
    with open(output_dir / f"model_long_{version}.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(output_dir / f"model_short_{version}.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(output_dir / f"scaler_{version}.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save as latest (overwrite)
    latest_suffix = f"{timeframe}_latest"
    with open(output_dir / f"model_long_{latest_suffix}.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(output_dir / f"model_short_{latest_suffix}.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(output_dir / f"scaler_{latest_suffix}.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    
    print(f"   ✅ model_long_{latest_suffix}.pkl")
    print(f"   ✅ model_short_{latest_suffix}.pkl")
    print(f"   ✅ scaler_{latest_suffix}.pkl")
    
    # Feature importance
    feature_importance_long = dict(zip(
        feature_names,
        [float(x) for x in model_long.feature_importances_]
    ))
    feature_importance_short = dict(zip(
        feature_names,
        [float(x) for x in model_short.feature_importances_]
    ))
    
    # Sort by importance
    feature_importance_long = dict(sorted(
        feature_importance_long.items(),
        key=lambda x: x[1],
        reverse=True
    ))
    feature_importance_short = dict(sorted(
        feature_importance_short.items(),
        key=lambda x: x[1],
        reverse=True
    ))
    
    # Training duration
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Build metadata
    metadata = {
        'version': version,
        'created_at': datetime.now().isoformat(),
        'timeframe': timeframe,
        'training_mode': 'local',
        'feature_names': feature_names,
        'n_features': len(feature_names),
        'n_trials': n_trials,
        'train_ratio': train_ratio,
        'n_train_samples': len(X_train),
        'n_test_samples': len(X_test),
        'total_samples': len(X),
        'training_duration_seconds': duration,
        'data_range': {
            'train_start': str(ts_train.iloc[0]),
            'train_end': str(ts_train.iloc[-1]),
            'test_start': str(ts_test.iloc[0]),
            'test_end': str(ts_test.iloc[-1]),
        },
        'best_params_long': {k: v for k, v in best_params_long.items()
                           if k not in ['objective', 'eval_metric', 'tree_method', 
                                       'verbosity', 'random_state', 'n_jobs']},
        'best_params_short': {k: v for k, v in best_params_short.items()
                            if k not in ['objective', 'eval_metric', 'tree_method',
                                        'verbosity', 'random_state', 'n_jobs']},
        'metrics_long': metrics_long,
        'metrics_short': metrics_short,
        'feature_importance_long': feature_importance_long,
        'feature_importance_short': feature_importance_short,
        'optuna_study_long': {
            'best_value': study_long.best_value,
            'n_trials': len(study_long.trials),
        },
        'optuna_study_short': {
            'best_value': study_short.best_value,
            'n_trials': len(study_short.trials),
        }
    }
    
    # Save metadata
    with open(output_dir / f"metadata_{version}.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    with open(output_dir / f"metadata_{latest_suffix}.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    
    print(f"   ✅ metadata_{latest_suffix}.json")
    
    # ===== FINAL SUMMARY =====
    print(f"\n{'='*60}")
    print(f"🎉 TRAINING COMPLETE!")
    print(f"{'='*60}")
    print(f"\n📊 Final Results:")
    print(f"   ┌─────────────┬──────────┬──────────┐")
    print(f"   │ Metric      │   LONG   │  SHORT   │")
    print(f"   ├─────────────┼──────────┼──────────┤")
    print(f"   │ Spearman    │  {metrics_long['ranking']['spearman_corr']:>6.4f}  │  {metrics_short['ranking']['spearman_corr']:>6.4f}  │")
    print(f"   │ R²          │  {metrics_long['test_r2']:>6.4f}  │  {metrics_short['test_r2']:>6.4f}  │")
    print(f"   │ Top1% Pos   │  {metrics_long['ranking']['top1pct_positive']:>5.1f}%  │  {metrics_short['ranking']['top1pct_positive']:>5.1f}%  │")
    print(f"   │ Top5% Pos   │  {metrics_long['ranking']['top5pct_positive']:>5.1f}%  │  {metrics_short['ranking']['top5pct_positive']:>5.1f}%  │")
    print(f"   └─────────────┴──────────┴──────────┘")
    
    print(f"\n📁 Output Files:")
    print(f"   {output_dir / f'model_long_{latest_suffix}.pkl'}")
    print(f"   {output_dir / f'model_short_{latest_suffix}.pkl'}")
    print(f"   {output_dir / f'metadata_{latest_suffix}.json'}")
    
    print(f"\n⏱️  Duration: {duration/60:.1f} minutes")
    
    # Top 5 features
    print(f"\n🔝 Top 5 Features (LONG):")
    for i, (feat, imp) in enumerate(list(feature_importance_long.items())[:5], 1):
        bar = "█" * int(imp * 50)
        print(f"   {i}. {feat:15s} {bar} {imp:.3f}")
    
    return metadata


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='🚀 Local ML Training (No Docker)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python train_local.py --timeframe 15m --trials 30
  python train_local.py --timeframe 1h --trials 20 --verbose
  python train_local.py --timeframe 15m --output-dir ./my_models
        """
    )
    parser.add_argument('--timeframe', '-t', required=True, 
                       choices=['15m', '1h'],
                       help='Timeframe to train (15m or 1h)')
    parser.add_argument('--trials', '-n', type=int, default=20,
                       help='Number of Optuna trials (default: 20)')
    parser.add_argument('--train-ratio', type=float, default=0.8,
                       help='Train/test split ratio (default: 0.8)')
    parser.add_argument('--output-dir', '-o', type=Path, default=None,
                       help='Output directory (default: shared/models)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed output')
    
    args = parser.parse_args()
    
    print_banner()
    
    try:
        metadata = train_model(
            timeframe=args.timeframe,
            n_trials=args.trials,
            train_ratio=args.train_ratio,
            output_dir=args.output_dir,
            verbose=args.verbose
        )
        
        if metadata:
            print("\n✅ Training completed successfully!")
            print("\n💡 Next Steps:")
            print("   1. Start the frontend: docker-compose up -d frontend")
            print("   2. Open http://localhost:8501")
            print("   3. Go to 'Train' tab to see model details")
            sys.exit(0)
        else:
            print("\n❌ Training failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Training interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
