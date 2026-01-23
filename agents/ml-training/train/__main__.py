#!/usr/bin/env python3
"""
🚀 ML Training Entry Point

Usage:
    python -m agents.ml_training.train
    python -m agents.ml_training.train --symbol BTC --timeframe 15m
"""

import sys
import argparse
from pathlib import Path
from xgboost import XGBRegressor

from .config import DB_PATH, MODEL_OUTPUT_DIR, TRAIN_RATIO, XGBOOST_PARAMS
from .data_loader import load_dataset, prepare_dataset
from .metrics import temporal_split, calculate_ranking_metrics, print_ranking_metrics
from .trainer import train_model, save_models


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           🚀 ML TRAINING PIPELINE - SCORE PREDICTION             ║
╚══════════════════════════════════════════════════════════════════╝
    """)


def main():
    """Main training pipeline"""
    parser = argparse.ArgumentParser(description='ML Training Pipeline')
    parser.add_argument('--symbol', type=str, default=None)
    parser.add_argument('--timeframe', type=str, default=None)
    parser.add_argument('--db-path', type=str, default=None)
    parser.add_argument('--output-dir', type=str, default=None)
    args = parser.parse_args()
    
    print_banner()
    
    db_path = Path(args.db_path) if args.db_path else DB_PATH
    output_dir = Path(args.output_dir) if args.output_dir else MODEL_OUTPUT_DIR
    
    df = load_dataset(db_path, args.symbol, args.timeframe)
    if len(df) == 0:
        print("❌ No data found!")
        sys.exit(1)
    
    X, y_long, y_short, timestamps, feature_names = prepare_dataset(df)
    
    print(f"\n🔀 Temporal split: {int(TRAIN_RATIO*100)}%/{int((1-TRAIN_RATIO)*100)}%")
    X_train, X_test, y_long_train, y_long_test, ts_train, ts_test = temporal_split(X, y_long, timestamps, TRAIN_RATIO)
    _, _, y_short_train, y_short_test, _, _ = temporal_split(X, y_short, timestamps, TRAIN_RATIO)
    
    print(f"   Train: {ts_train.iloc[0]} → {ts_train.iloc[-1]}")
    print(f"   Test:  {ts_test.iloc[0]} → {ts_test.iloc[-1]}")
    
    # Train models
    model_long, scaler, metrics_long, _ = train_model(X_train, y_long_train, X_test, y_long_test, "LONG")
    
    # SHORT model (reuse scaler)
    X_train_scaled = scaler.transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    model_short = XGBRegressor(**XGBOOST_PARAMS)
    model_short.fit(X_train_scaled, y_short_train, eval_set=[(X_test_scaled, y_short_test)], verbose=False)
    
    from sklearn.metrics import mean_squared_error, r2_score
    import numpy as np
    y_pred_short = model_short.predict(X_test_scaled)
    metrics_short = {
        'test_rmse': np.sqrt(mean_squared_error(y_short_test, y_pred_short)),
        'test_r2': r2_score(y_short_test, y_pred_short),
    }
    
    # Ranking metrics
    y_pred_long = model_long.predict(X_test_scaled)
    ranking_long = calculate_ranking_metrics(y_long_test, y_pred_long)
    ranking_short = calculate_ranking_metrics(y_short_test, y_pred_short)
    print_ranking_metrics(ranking_long, "LONG")
    print_ranking_metrics(ranking_short, "SHORT")
    
    metrics_long['ranking'] = ranking_long
    metrics_short['ranking'] = ranking_short
    
    # Save
    version = save_models(
        model_long, model_short, scaler, feature_names, metrics_long, metrics_short, output_dir,
        ts_train.iloc[0], ts_train.iloc[-1], ts_test.iloc[0], ts_test.iloc[-1],
        df['symbol'].unique().tolist(), df['timeframe'].unique().tolist()
    )
    
    print(f"\n✅ TRAINING COMPLETE (v{version}) | {len(X):,} samples | {len(feature_names)} features")


if __name__ == '__main__':
    main()
