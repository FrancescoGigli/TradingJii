"""
🔮 Models - Inference Logic

Real-time inference functionality:
- Load models by timeframe
- Fetch real-time data from database
- Compute missing indicators
- Run inference and create charts
"""

import pandas as pd
import numpy as np
import json
import pickle
import sqlite3
from pathlib import Path
import os

from services.feature_alignment import align_features_dataframe
from services.xgb_normalization import normalize_long_short_scores

# For plotting
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def get_db_path():
    """Get database path"""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    return Path(shared_path) / "data_cache" / "trading_data.db"


def get_model_dir() -> Path:
    """Get models directory path"""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    model_dir = Path(shared_path) / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def load_model_for_timeframe(timeframe: str):
    """Load model, scaler and metadata for a specific timeframe"""
    model_dir = get_model_dir()
    
    try:
        with open(model_dir / f"model_long_{timeframe}_latest.pkl", 'rb') as f:
            model_long = pickle.load(f)
        with open(model_dir / f"model_short_{timeframe}_latest.pkl", 'rb') as f:
            model_short = pickle.load(f)
        with open(model_dir / f"scaler_{timeframe}_latest.pkl", 'rb') as f:
            scaler = pickle.load(f)
        with open(model_dir / f"metadata_{timeframe}_latest.json", 'r') as f:
            metadata = json.load(f)
        return model_long, model_short, scaler, metadata
    except Exception as e:
        return None, None, None, None


def get_realtime_symbols() -> list:
    """Get list of symbols from realtime_ohlcv table"""
    db_path = get_db_path()
    if not db_path.exists():
        return []
    
    try:
        conn = sqlite3.connect(str(db_path), timeout=30)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM realtime_ohlcv ORDER BY symbol")
        symbols = [row[0] for row in cursor.fetchall()]
        conn.close()
        return symbols
    except:
        return []


def fetch_realtime_data(symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
    """Fetch real-time OHLCV data with indicators from database"""
    db_path = get_db_path()
    
    if not db_path.exists():
        return pd.DataFrame()
    
    conn = sqlite3.connect(str(db_path), timeout=30)
    
    try:
        # Check available columns
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(realtime_ohlcv)")
        columns = [row[1] for row in cursor.fetchall()]
        
        indicator_cols = ['sma_20', 'sma_50', 'ema_12', 'ema_26', 
                         'bb_upper', 'bb_mid', 'bb_lower',
                         'macd', 'macd_signal', 'macd_hist',
                         'rsi', 'stoch_k', 'stoch_d',
                         'atr', 'volume_sma', 'obv']
        
        available_indicators = [c for c in indicator_cols if c in columns]
        indicator_select = ', '.join(available_indicators) if available_indicators else ''
        
        if indicator_select:
            query = f"""
                SELECT timestamp, symbol, open, high, low, close, volume, {indicator_select}
                FROM realtime_ohlcv WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC LIMIT ?
            """
        else:
            query = """
                SELECT timestamp, symbol, open, high, low, close, volume
                FROM realtime_ohlcv WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC LIMIT ?
            """
        
        df = pd.read_sql_query(query, conn, params=[symbol, timeframe, limit])
        
        if len(df) == 0:
            # Fallback to training_data
            query = query.replace('realtime_ohlcv', 'training_data')
            df = pd.read_sql_query(query, conn, params=[symbol, timeframe, limit])
        
        if len(df) > 0:
            df = df.sort_values('timestamp').reset_index(drop=True)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        
        return df
        
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()


def compute_missing_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute basic indicators if missing from data"""
    df = df.copy()
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    
    if 'sma_20' not in df.columns:
        df['sma_20'] = close.rolling(20).mean()
    if 'sma_50' not in df.columns:
        df['sma_50'] = close.rolling(50).mean()
    if 'ema_12' not in df.columns:
        df['ema_12'] = close.ewm(span=12, adjust=False).mean()
    if 'ema_26' not in df.columns:
        df['ema_26'] = close.ewm(span=26, adjust=False).mean()
    
    if 'bb_mid' not in df.columns:
        df['bb_mid'] = close.rolling(20).mean()
        std = close.rolling(20).std()
        df['bb_upper'] = df['bb_mid'] + 2 * std
        df['bb_lower'] = df['bb_mid'] - 2 * std
    
    if 'macd' not in df.columns:
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
    
    if 'rsi' not in df.columns:
        delta = close.diff()
        gain = delta.where(delta > 0, 0).ewm(span=14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(span=14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
    
    if 'stoch_k' not in df.columns:
        low_14 = low.rolling(14).min()
        high_14 = high.rolling(14).max()
        df['stoch_k'] = 100 * (close - low_14) / (high_14 - low_14)
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
    
    if 'atr' not in df.columns:
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = tr.ewm(span=14, adjust=False).mean()
    
    if 'volume_sma' not in df.columns:
        df['volume_sma'] = volume.rolling(20).mean()
    
    if 'obv' not in df.columns:
        sign = np.sign(close.diff())
        df['obv'] = (sign * volume).cumsum()
    
    return df


def run_inference(df: pd.DataFrame, model_long, model_short, scaler, feature_names: list) -> pd.DataFrame:
    """Run inference on dataframe"""
    df = df.copy()
    
    # Align to expected feature set to avoid sklearn "invalid feature names"
    # warning and to enforce correct ordering.
    X_df = align_features_dataframe(
        df,
        feature_names,
        fill_value=0.0,
        forward_fill=False,
    )
    X_scaled = scaler.transform(X_df)
    
    df['pred_long'] = model_long.predict(X_scaled)
    df['pred_short'] = model_short.predict(X_scaled)

    normalized = normalize_long_short_scores(
        df['pred_long'].to_numpy(),
        df['pred_short'].to_numpy(),
    )

    # Canonical normalization used across Train/Test:
    # - per-side 0..100 percentile rank
    # - net -100..100 for direct comparison with Signal Calculator
    df['pred_long_0_100'] = normalized.long_0_100
    df['pred_short_0_100'] = normalized.short_0_100
    df['pred_net_-100_100'] = normalized.net_score_minus_100_100
    df['short_inverted'] = bool(normalized.short_inverted)
    
    return df


def create_inference_chart(df: pd.DataFrame, symbol: str, timeframe: str):
    """Create candlestick chart with inference overlay"""
    if not PLOTLY_AVAILABLE:
        return None
    
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
        row_heights=[0.5, 0.25, 0.25],
        subplot_titles=[
            f"📈 {symbol} ({timeframe})",
            "🔮 XGB Net Score (-100..100)",
            "🔮 SHORT Score (0..100)",
        ]
    )
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name='Price', increasing_line_color='#26a69a', decreasing_line_color='#ef5350'
    ), row=1, col=1)
    
    if 'sma_20' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['sma_20'], name='SMA20', 
                                 line=dict(color='orange', width=1)), row=1, col=1)
    if 'sma_50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['sma_50'], name='SMA50',
                                 line=dict(color='blue', width=1)), row=1, col=1)
    
    # LONG predictions
    if 'pred_net_-100_100' in df.columns:
        colors = ['#26a69a' if v > 0 else '#ef5350' for v in df['pred_net_-100_100']]
        fig.add_trace(go.Bar(x=df.index, y=df['pred_net_-100_100'], name='NET',
                            marker_color=colors, opacity=0.7), row=2, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="white", row=2, col=1)
    
    # SHORT predictions (0..100)
    if 'pred_short_0_100' in df.columns:
        colors = ['#ef5350' if v > 50 else '#26a69a' for v in df['pred_short_0_100']]
        fig.add_trace(go.Bar(x=df.index, y=df['pred_short_0_100'], name='SHORT (0..100)',
                            marker_color=colors, opacity=0.7), row=3, col=1)
        fig.add_hline(y=50, line_dash="dash", line_color="white", row=3, col=1)
    
    fig.update_layout(
        height=800, template='plotly_dark', showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        xaxis_rangeslider_visible=False, margin=dict(l=50, r=50, t=80, b=50)
    )
    
    return fig


__all__ = [
    'get_db_path', 'get_model_dir', 'load_model_for_timeframe',
    'get_realtime_symbols', 'fetch_realtime_data', 'compute_missing_indicators',
    'run_inference', 'create_inference_chart', 'PLOTLY_AVAILABLE'
]
