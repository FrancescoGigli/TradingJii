#!/usr/bin/env python3
"""
🚀 FULL TRAINING PIPELINE
Esegue automaticamente tutti gli step del training:
1. Data: Scarica OHLCV + calcola indicatori → training_data
2. Labeling: Genera labels con trailing stop → training_labels  
3. Training: Addestra XGBoost → shared/models/

Uso:
    python run_full_training_pipeline.py

Opzioni:
    --symbols 10       Numero di symbols (default: 100)
    --timeframe 15m    Timeframe (15m o 1h)
    --days 30          Giorni di dati (default: 365)
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import sys
import os

# Add paths
sys.path.insert(0, str(Path(__file__).parent / 'agents' / 'frontend'))
sys.path.insert(0, str(Path(__file__).parent / 'agents' / 'historical-data'))

DB_PATH = Path(__file__).parent / 'shared' / 'crypto_data.db'


def get_connection():
    """Get database connection"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def create_tables():
    """Create all required tables"""
    conn = get_connection()
    cur = conn.cursor()
    
    print("📋 Creating tables...")
    
    # training_data table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS training_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            sma_20 REAL, sma_50 REAL, ema_12 REAL, ema_26 REAL,
            bb_upper REAL, bb_middle REAL, bb_lower REAL,
            rsi REAL, macd REAL, macd_signal REAL, macd_hist REAL,
            atr REAL, adx REAL, cci REAL, willr REAL, obv REAL,
            UNIQUE(symbol, timeframe, timestamp)
        )
    ''')
    
    # training_labels table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS training_labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            score_long REAL, score_short REAL,
            realized_return_long REAL, realized_return_short REAL,
            mfe_long REAL, mfe_short REAL,
            mae_long REAL, mae_short REAL,
            bars_held_long INTEGER, bars_held_short INTEGER,
            exit_type_long TEXT, exit_type_short TEXT,
            UNIQUE(symbol, timeframe, timestamp)
        )
    ''')
    
    # Create indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_td_sym_tf ON training_data(symbol, timeframe)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_tl_sym_tf ON training_labels(symbol, timeframe)')
    
    conn.commit()
    conn.close()
    print("   ✅ Tables created")


def fetch_ohlcv_data(symbol: str, timeframe: str, days: int = 365) -> pd.DataFrame:
    """Fetch OHLCV data from Bybit API"""
    try:
        import ccxt
    except ImportError:
        print("❌ ccxt not installed. Run: pip install ccxt")
        return pd.DataFrame()
    
    exchange = ccxt.bybit({
        'enableRateLimit': True,
        'options': {'defaultType': 'linear'}
    })
    
    since = exchange.milliseconds() - (days * 24 * 60 * 60 * 1000)
    
    all_ohlcv = []
    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since, limit=1000)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            if len(ohlcv) < 1000:
                break
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            break
    
    if not all_ohlcv:
        return pd.DataFrame()
    
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate 16 technical indicators"""
    try:
        import ta
    except ImportError:
        print("❌ ta not installed. Run: pip install ta")
        return df
    
    # SMA
    df['sma_20'] = ta.trend.sma_indicator(df['close'], window=20)
    df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
    
    # EMA
    df['ema_12'] = ta.trend.ema_indicator(df['close'], window=12)
    df['ema_26'] = ta.trend.ema_indicator(df['close'], window=26)
    
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df['close'], window=20)
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_middle'] = bb.bollinger_mavg()
    df['bb_lower'] = bb.bollinger_lband()
    
    # RSI
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    
    # MACD
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_hist'] = macd.macd_diff()
    
    # ATR
    df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
    
    # ADX
    df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=14)
    
    # CCI
    df['cci'] = ta.trend.cci(df['high'], df['low'], df['close'], window=20)
    
    # Williams %R
    df['willr'] = ta.momentum.williams_r(df['high'], df['low'], df['close'], lbp=14)
    
    # OBV
    df['obv'] = ta.volume.on_balance_volume(df['close'], df['volume'])
    
    # Drop NaN rows from warmup
    df = df.dropna()
    
    return df


def save_training_data(df: pd.DataFrame, symbol: str, timeframe: str):
    """Save data to training_data table"""
    conn = get_connection()
    cur = conn.cursor()
    
    # Delete existing
    cur.execute('DELETE FROM training_data WHERE symbol=? AND timeframe=?', (symbol, timeframe))
    
    for _, row in df.iterrows():
        cur.execute('''
            INSERT INTO training_data 
            (timestamp, symbol, timeframe, open, high, low, close, volume,
             sma_20, sma_50, ema_12, ema_26, bb_upper, bb_middle, bb_lower,
             rsi, macd, macd_signal, macd_hist, atr, adx, cci, willr, obv)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(row['timestamp']), symbol, timeframe,
            row['open'], row['high'], row['low'], row['close'], row['volume'],
            row['sma_20'], row['sma_50'], row['ema_12'], row['ema_26'],
            row['bb_upper'], row['bb_middle'], row['bb_lower'],
            row['rsi'], row['macd'], row['macd_signal'], row['macd_hist'],
            row['atr'], row['adx'], row['cci'], row['willr'], row['obv']
        ))
    
    conn.commit()
    conn.close()


def generate_labels(symbol: str, timeframe: str, trailing_pct: float = 0.015, max_bars: int = 48):
    """Generate trailing stop labels"""
    conn = get_connection()
    
    df = pd.read_sql_query('''
        SELECT * FROM training_data 
        WHERE symbol=? AND timeframe=?
        ORDER BY timestamp
    ''', conn, params=(symbol, timeframe))
    
    if len(df) == 0:
        conn.close()
        return 0
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Calculate labels for each row
    labels = []
    for i in range(len(df) - max_bars):
        row = df.iloc[i]
        future = df.iloc[i+1:i+1+max_bars]
        
        entry_price = row['close']
        
        # LONG simulation
        best_price_long = entry_price
        trailing_stop_long = entry_price * (1 - trailing_pct)
        exit_price_long = entry_price
        bars_held_long = max_bars
        exit_type_long = 'time'
        mfe_long = 0
        mae_long = 0
        
        for j, (_, f) in enumerate(future.iterrows()):
            mfe_long = max(mfe_long, (f['high'] - entry_price) / entry_price)
            mae_long = min(mae_long, (f['low'] - entry_price) / entry_price)
            
            if f['high'] > best_price_long:
                best_price_long = f['high']
                trailing_stop_long = best_price_long * (1 - trailing_pct)
            
            if f['low'] <= trailing_stop_long:
                exit_price_long = trailing_stop_long
                bars_held_long = j + 1
                exit_type_long = 'trailing'
                break
        else:
            exit_price_long = future.iloc[-1]['close']
        
        return_long = (exit_price_long - entry_price) / entry_price
        
        # SHORT simulation
        best_price_short = entry_price
        trailing_stop_short = entry_price * (1 + trailing_pct)
        exit_price_short = entry_price
        bars_held_short = max_bars
        exit_type_short = 'time'
        mfe_short = 0
        mae_short = 0
        
        for j, (_, f) in enumerate(future.iterrows()):
            mfe_short = max(mfe_short, (entry_price - f['low']) / entry_price)
            mae_short = min(mae_short, (entry_price - f['high']) / entry_price)
            
            if f['low'] < best_price_short:
                best_price_short = f['low']
                trailing_stop_short = best_price_short * (1 + trailing_pct)
            
            if f['high'] >= trailing_stop_short:
                exit_price_short = trailing_stop_short
                bars_held_short = j + 1
                exit_type_short = 'trailing'
                break
        else:
            exit_price_short = future.iloc[-1]['close']
        
        return_short = (entry_price - exit_price_short) / entry_price
        
        # Calculate scores
        time_penalty = 0.001
        cost = 0.001
        score_long = return_long - time_penalty * np.log(1 + bars_held_long) - cost
        score_short = return_short - time_penalty * np.log(1 + bars_held_short) - cost
        
        labels.append({
            'timestamp': row['timestamp'],
            'open': row['open'], 'high': row['high'], 'low': row['low'], 
            'close': row['close'], 'volume': row['volume'],
            'score_long': score_long, 'score_short': score_short,
            'realized_return_long': return_long, 'realized_return_short': return_short,
            'mfe_long': mfe_long, 'mfe_short': mfe_short,
            'mae_long': mae_long, 'mae_short': mae_short,
            'bars_held_long': bars_held_long, 'bars_held_short': bars_held_short,
            'exit_type_long': exit_type_long, 'exit_type_short': exit_type_short
        })
    
    # Save labels
    cur = conn.cursor()
    cur.execute('DELETE FROM training_labels WHERE symbol=? AND timeframe=?', (symbol, timeframe))
    
    for label in labels:
        cur.execute('''
            INSERT INTO training_labels 
            (timestamp, symbol, timeframe, open, high, low, close, volume,
             score_long, score_short, realized_return_long, realized_return_short,
             mfe_long, mfe_short, mae_long, mae_short,
             bars_held_long, bars_held_short, exit_type_long, exit_type_short)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(label['timestamp']), symbol, timeframe,
            label['open'], label['high'], label['low'], label['close'], label['volume'],
            label['score_long'], label['score_short'],
            label['realized_return_long'], label['realized_return_short'],
            label['mfe_long'], label['mfe_short'], label['mae_long'], label['mae_short'],
            label['bars_held_long'], label['bars_held_short'],
            label['exit_type_long'], label['exit_type_short']
        ))
    
    conn.commit()
    conn.close()
    
    return len(labels)


def train_model(timeframe: str = '15m'):
    """Train XGBoost model"""
    try:
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import r2_score
        from scipy.stats import spearmanr
        from xgboost import XGBRegressor
        import pickle
        import json
    except ImportError:
        print("❌ Missing packages. Run: pip install scikit-learn xgboost scipy")
        return False
    
    conn = get_connection()
    
    # Load data with JOIN
    df = pd.read_sql_query('''
        SELECT 
            td.timestamp, td.symbol, td.timeframe,
            td.open, td.high, td.low, td.close, td.volume,
            td.sma_20, td.sma_50, td.ema_12, td.ema_26,
            td.bb_upper, td.bb_middle, td.bb_lower,
            td.rsi, td.macd, td.macd_signal, td.macd_hist,
            td.atr, td.adx, td.cci, td.willr, td.obv,
            tl.score_long, tl.score_short
        FROM training_data td
        INNER JOIN training_labels tl ON 
            td.symbol = tl.symbol AND 
            td.timeframe = tl.timeframe AND 
            td.timestamp = tl.timestamp
        WHERE td.timeframe = ?
        ORDER BY td.symbol, td.timestamp
    ''', conn, params=(timeframe,))
    
    conn.close()
    
    if len(df) < 100:
        print(f"❌ Not enough data: {len(df)} samples")
        return False
    
    print(f"   📊 Training data: {len(df):,} samples")
    
    # Feature columns
    feature_cols = [
        'open', 'high', 'low', 'close', 'volume',
        'sma_20', 'sma_50', 'ema_12', 'ema_26',
        'bb_upper', 'bb_middle', 'bb_lower',
        'rsi', 'macd', 'macd_signal', 'macd_hist',
        'atr', 'adx', 'cci', 'willr', 'obv'
    ]
    
    X = df[feature_cols].copy()
    y_long = df['score_long'].copy()
    y_short = df['score_short'].copy()
    
    # Remove NaN
    valid = ~(X.isna().any(axis=1) | y_long.isna() | y_short.isna())
    X, y_long, y_short = X[valid], y_long[valid], y_short[valid]
    
    # Train/test split
    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_long_train, y_long_test = y_long.iloc[:split], y_long.iloc[split:]
    y_short_train, y_short_test = y_short.iloc[:split], y_short.iloc[split:]
    
    # Scale
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train models
    params = {
        'n_estimators': 500,
        'max_depth': 6,
        'learning_rate': 0.05,
        'min_child_weight': 10,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'objective': 'reg:squarederror',
        'random_state': 42,
        'verbosity': 0
    }
    
    print("   🔄 Training LONG model...")
    model_long = XGBRegressor(**params)
    model_long.fit(X_train_scaled, y_long_train)
    pred_long = model_long.predict(X_test_scaled)
    r2_long = r2_score(y_long_test, pred_long)
    spear_long, _ = spearmanr(pred_long, y_long_test)
    
    print("   🔄 Training SHORT model...")
    model_short = XGBRegressor(**params)
    model_short.fit(X_train_scaled, y_short_train)
    pred_short = model_short.predict(X_test_scaled)
    r2_short = r2_score(y_short_test, pred_short)
    spear_short, _ = spearmanr(pred_short, y_short_test)
    
    # Save models
    model_dir = Path(__file__).parent / 'shared' / 'models'
    model_dir.mkdir(parents=True, exist_ok=True)
    
    version = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    with open(model_dir / f'model_long_{version}.pkl', 'wb') as f:
        pickle.dump(model_long, f)
    with open(model_dir / f'model_short_{version}.pkl', 'wb') as f:
        pickle.dump(model_short, f)
    with open(model_dir / f'scaler_{version}.pkl', 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save as latest
    with open(model_dir / 'model_long_latest.pkl', 'wb') as f:
        pickle.dump(model_long, f)
    with open(model_dir / 'model_short_latest.pkl', 'wb') as f:
        pickle.dump(model_short, f)
    with open(model_dir / 'scaler_latest.pkl', 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save metadata
    metadata = {
        'version': version,
        'timeframe': timeframe,
        'n_features': len(feature_cols),
        'feature_names': feature_cols,
        'n_train_samples': len(X_train),
        'n_test_samples': len(X_test),
        'metrics_long': {'test_r2': r2_long, 'ranking': {'spearman_corr': spear_long}},
        'metrics_short': {'test_r2': r2_short, 'ranking': {'spearman_corr': spear_short}}
    }
    
    with open(model_dir / f'metadata_{version}.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    with open(model_dir / 'metadata_latest.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n   ✅ Models saved to {model_dir}")
    print(f"   📊 LONG:  R²={r2_long:.4f}, Spearman={spear_long:.4f}")
    print(f"   📊 SHORT: R²={r2_short:.4f}, Spearman={spear_short:.4f}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Full Training Pipeline')
    parser.add_argument('--symbols', type=int, default=10, help='Number of symbols')
    parser.add_argument('--timeframe', default='15m', choices=['15m', '1h'])
    parser.add_argument('--days', type=int, default=365, help='Days of data')
    args = parser.parse_args()
    
    print("="*60)
    print("🚀 FULL TRAINING PIPELINE")
    print("="*60)
    print(f"   Symbols: {args.symbols}")
    print(f"   Timeframe: {args.timeframe}")
    print(f"   Days: {args.days}")
    print("="*60)
    
    # Step 0: Create tables
    create_tables()
    
    # Get top symbols
    try:
        import ccxt
        exchange = ccxt.bybit({'options': {'defaultType': 'linear'}})
        markets = exchange.load_markets()
        tickers = exchange.fetch_tickers()
        
        # Filter USDT perpetuals with volume
        symbols = []
        for sym, ticker in tickers.items():
            if '/USDT:USDT' in sym and ticker.get('quoteVolume', 0) > 1000000:
                symbols.append((sym, ticker['quoteVolume']))
        
        symbols = sorted(symbols, key=lambda x: x[1], reverse=True)[:args.symbols]
        symbols = [s[0] for s in symbols]
    except Exception as e:
        print(f"⚠️ Error getting symbols: {e}")
        symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']
    
    print(f"\n📥 STEP 1: DATA ({len(symbols)} symbols)")
    print("-"*60)
    
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] {symbol.replace('/USDT:USDT', '')}")
        
        # Fetch data
        df = fetch_ohlcv_data(symbol, args.timeframe, args.days)
        if len(df) == 0:
            print(f"   ⚠️ No data")
            continue
        
        # Calculate indicators
        df = calculate_indicators(df)
        
        # Save
        save_training_data(df, symbol, args.timeframe)
        print(f"   ✅ {len(df):,} candles")
    
    print(f"\n🏷️ STEP 2: LABELING")
    print("-"*60)
    
    trailing_pct = 0.015 if args.timeframe == '15m' else 0.025
    max_bars = 48 if args.timeframe == '15m' else 24
    
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] {symbol.replace('/USDT:USDT', '')}")
        n_labels = generate_labels(symbol, args.timeframe, trailing_pct, max_bars)
        print(f"   ✅ {n_labels:,} labels")
    
    print(f"\n🤖 STEP 3: TRAINING")
    print("-"*60)
    
    success = train_model(args.timeframe)
    
    print("\n" + "="*60)
    if success:
        print("✅ PIPELINE COMPLETE!")
    else:
        print("❌ PIPELINE FAILED")
    print("="*60)


if __name__ == '__main__':
    main()
