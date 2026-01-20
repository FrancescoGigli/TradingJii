#!/usr/bin/env python3
"""
🔮 ML Inference Script - Make Predictions
==========================================

Load trained models and make predictions on new/live data.
Shows top trading opportunities ranked by predicted score.

Usage:
    python inference.py                      # Use latest data from DB
    python inference.py --symbol BTCUSDT     # Filter by symbol
    python inference.py --top 20             # Show top 20 predictions
    python inference.py --after "2026-01-07" # Data after specific date

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

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DB_PATH = PROJECT_ROOT / "shared" / "data_cache" / "trading_data.db"
MODEL_DIR = PROJECT_ROOT / "shared" / "models"


def print_banner():
    """Print startup banner"""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║            🔮 ML INFERENCE - Trading Signal Generator                ║
║                                                                      ║
║  Predicts:  score_long, score_short (trading opportunity quality)    ║
║  Model:     XGBoost Regressor (Optuna-tuned)                         ║
╚══════════════════════════════════════════════════════════════════════╝
    """)


def load_models(model_dir: Path):
    """Load trained models, scaler, and metadata"""
    print(f"\n📦 Loading models from: {model_dir}")
    
    # Try loading latest models
    model_long_path = model_dir / "model_long_latest.pkl"
    model_short_path = model_dir / "model_short_latest.pkl"
    scaler_path = model_dir / "scaler_latest.pkl"
    metadata_path = model_dir / "metadata_latest.json"
    
    if not model_long_path.exists():
        print(f"❌ Model not found: {model_long_path}")
        print("   Run train_optuna.py first to train models!")
        sys.exit(1)
    
    with open(model_long_path, 'rb') as f:
        model_long = pickle.load(f)
    print(f"   ✅ Loaded model_long")
    
    with open(model_short_path, 'rb') as f:
        model_short = pickle.load(f)
    print(f"   ✅ Loaded model_short")
    
    with open(scaler_path, 'rb') as f:
        scaler = pickle.load(f)
    print(f"   ✅ Loaded scaler")
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    print(f"   ✅ Loaded metadata (version: {metadata['version']})")
    
    return model_long, model_short, scaler, metadata


def load_inference_data(db_path: Path, symbol: str = None, timeframe: str = None, 
                        after_date: str = None) -> pd.DataFrame:
    """
    Load data for inference from SQLite database.
    Can filter by symbol, timeframe, or date.
    """
    print(f"\n📊 Loading inference data from: {db_path}")
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        sys.exit(1)
    
    # Connect with timeout and WAL mode for better concurrency
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(historical_ohlcv)")
        historical_cols = [row[1] for row in cursor.fetchall()]
        
        # Build query to get OHLCV + indicators
        query = f'''
            SELECT 
                timestamp, symbol, timeframe,
                {', '.join([c for c in historical_cols if c not in ('id', 'fetched_at', 'interpolated')])}
            FROM historical_ohlcv
        '''
        
        conditions = []
        params = []
        
        if symbol:
            conditions.append('symbol LIKE ?')
            params.append(f'%{symbol}%')
        
        if timeframe:
            conditions.append('timeframe = ?')
            params.append(timeframe)
        
        if after_date:
            conditions.append('timestamp > ?')
            params.append(after_date)
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += ' ORDER BY symbol, timeframe, timestamp DESC'
        
        df = pd.read_sql_query(query, conn, params=params if params else None)
        
        print(f"   ✅ Loaded {len(df):,} rows")
        
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            print(f"   📅 Date range: {df['timestamp'].min()} → {df['timestamp'].max()}")
            print(f"   📊 Symbols: {df['symbol'].nunique()}")
            
        return df
        
    finally:
        conn.close()


def prepare_features(df: pd.DataFrame, feature_names: list) -> tuple:
    """
    Prepare features for inference.
    Returns X matrix and metadata for each row.
    """
    print("\n🔧 Preparing features...")
    
    # Check which features are available
    available_features = [c for c in feature_names if c in df.columns]
    missing_features = [c for c in feature_names if c not in df.columns]
    
    if missing_features:
        print(f"   ⚠️ Missing {len(missing_features)} features: {missing_features[:5]}...")
    
    print(f"   📊 Using {len(available_features)} features")
    
    # Filter rows with complete features (no NaN)
    X = df[available_features].copy()
    valid_mask = ~X.isna().any(axis=1)
    
    n_invalid = (~valid_mask).sum()
    if n_invalid > 0:
        print(f"   🧹 Removing {n_invalid} rows with NaN values")
    
    df_valid = df[valid_mask].copy()
    X_valid = X[valid_mask].copy()
    
    print(f"   ✅ Valid rows for inference: {len(X_valid):,}")
    
    return X_valid, df_valid, available_features


def run_inference(model_long, model_short, scaler, X: pd.DataFrame) -> tuple:
    """
    Run inference on prepared features.
    Returns predictions for both long and short models.
    """
    print("\n🔮 Running inference...")
    
    # Scale features
    X_scaled = scaler.transform(X)
    
    # Predict
    pred_long = model_long.predict(X_scaled)
    pred_short = model_short.predict(X_scaled)
    
    print(f"   ✅ Generated {len(pred_long):,} predictions")
    
    return pred_long, pred_short


def display_results(df: pd.DataFrame, pred_long: np.ndarray, pred_short: np.ndarray, 
                    top_n: int = 20):
    """
    Display top trading opportunities.
    """
    # Add predictions to dataframe
    results = df[['timestamp', 'symbol', 'timeframe', 'close']].copy()
    results['pred_score_long'] = pred_long
    results['pred_score_short'] = pred_short
    
    # Get latest prediction per symbol/timeframe
    latest = results.sort_values('timestamp', ascending=False).groupby(
        ['symbol', 'timeframe']
    ).first().reset_index()
    
    print(f"\n" + "="*80)
    print(f"   🏆 TOP {top_n} LONG OPPORTUNITIES (by predicted score)")
    print("="*80)
    
    top_long = latest.nlargest(top_n, 'pred_score_long')
    
    print(f"\n   {'Symbol':<15} {'TF':<5} {'Price':>12} {'Score_Long':>12} {'Score_Short':>12}")
    print(f"   {'-'*15} {'-'*5} {'-'*12} {'-'*12} {'-'*12}")
    
    for _, row in top_long.iterrows():
        symbol = row['symbol']
        tf = row['timeframe']
        price = row['close']
        score_l = row['pred_score_long']
        score_s = row['pred_score_short']
        
        # Color coding based on score
        if score_l > 0:
            indicator = "📈"
        else:
            indicator = "  "
        
        print(f"   {indicator} {symbol:<13} {tf:<5} {price:>12,.2f} {score_l:>12.6f} {score_s:>12.6f}")
    
    print(f"\n" + "="*80)
    print(f"   📉 TOP {top_n} SHORT OPPORTUNITIES (by predicted score)")
    print("="*80)
    
    top_short = latest.nlargest(top_n, 'pred_score_short')
    
    print(f"\n   {'Symbol':<15} {'TF':<5} {'Price':>12} {'Score_Long':>12} {'Score_Short':>12}")
    print(f"   {'-'*15} {'-'*5} {'-'*12} {'-'*12} {'-'*12}")
    
    for _, row in top_short.iterrows():
        symbol = row['symbol']
        tf = row['timeframe']
        price = row['close']
        score_l = row['pred_score_long']
        score_s = row['pred_score_short']
        
        if score_s > 0:
            indicator = "📉"
        else:
            indicator = "  "
        
        print(f"   {indicator} {symbol:<13} {tf:<5} {price:>12,.2f} {score_l:>12.6f} {score_s:>12.6f}")
    
    # Statistics
    print(f"\n" + "="*80)
    print(f"   📊 STATISTICS")
    print("="*80)
    
    print(f"\n   Score Long:")
    print(f"      Min:    {pred_long.min():.6f}")
    print(f"      Max:    {pred_long.max():.6f}")
    print(f"      Mean:   {pred_long.mean():.6f}")
    print(f"      Std:    {pred_long.std():.6f}")
    print(f"      >0:     {(pred_long > 0).sum():,} ({(pred_long > 0).mean()*100:.1f}%)")
    
    print(f"\n   Score Short:")
    print(f"      Min:    {pred_short.min():.6f}")
    print(f"      Max:    {pred_short.max():.6f}")
    print(f"      Mean:   {pred_short.mean():.6f}")
    print(f"      Std:    {pred_short.std():.6f}")
    print(f"      >0:     {(pred_short > 0).sum():,} ({(pred_short > 0).mean()*100:.1f}%)")
    
    return results


def save_predictions(results: pd.DataFrame, output_path: Path = None):
    """Save predictions to CSV"""
    if output_path is None:
        output_path = MODEL_DIR / f"predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    results.to_csv(output_path, index=False)
    print(f"\n💾 Predictions saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='ML Inference - Make Predictions')
    parser.add_argument('--symbol', type=str, default=None, help='Filter by symbol (e.g., BTCUSDT)')
    parser.add_argument('--timeframe', type=str, default=None, help='Filter by timeframe (e.g., 15m)')
    parser.add_argument('--after', type=str, default=None, 
                        help='Only use data after this date (e.g., 2026-01-07)')
    parser.add_argument('--top', type=int, default=20, help='Show top N predictions')
    parser.add_argument('--save', action='store_true', help='Save predictions to CSV')
    parser.add_argument('--db-path', type=str, default=None, help='Custom database path')
    parser.add_argument('--model-dir', type=str, default=None, help='Custom model directory')
    args = parser.parse_args()
    
    print_banner()
    
    # Paths
    db_path = Path(args.db_path) if args.db_path else DB_PATH
    model_dir = Path(args.model_dir) if args.model_dir else MODEL_DIR
    
    # Load models
    model_long, model_short, scaler, metadata = load_models(model_dir)
    feature_names = metadata['feature_names']
    
    # Load data
    df = load_inference_data(db_path, args.symbol, args.timeframe, args.after)
    
    if len(df) == 0:
        print("❌ No data found for inference!")
        sys.exit(1)
    
    # Prepare features
    X, df_valid, available_features = prepare_features(df, feature_names)
    
    if len(X) == 0:
        print("❌ No valid rows for inference (all have NaN)!")
        sys.exit(1)
    
    # Run inference
    pred_long, pred_short = run_inference(model_long, model_short, scaler, X)
    
    # Display results
    results = display_results(df_valid, pred_long, pred_short, args.top)
    
    # Save if requested
    if args.save:
        save_predictions(results)
    
    print(f"\n" + "="*80)
    print(f"   ✅ INFERENCE COMPLETE")
    print(f"   📊 Total predictions: {len(results):,}")
    print(f"   🔮 Model version: {metadata['version']}")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
