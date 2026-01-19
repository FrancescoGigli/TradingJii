"""
📊 Technical Indicators Module for Data-Fetcher

Calculates technical indicators for real-time OHLCV data.
Same indicators as historical-data but optimized for smaller datasets.
"""

import pandas as pd
import numpy as np
from typing import Optional

# List of indicator columns
INDICATOR_COLUMNS = [
    'sma_20', 'sma_50', 'ema_12', 'ema_26',
    'bb_upper', 'bb_mid', 'bb_lower',
    'macd', 'macd_signal', 'macd_hist',
    'rsi', 'stoch_k', 'stoch_d', 'atr',
    'volume_sma', 'obv'
]


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate all technical indicators for OHLCV data.
    
    Args:
        df: DataFrame with OHLCV columns (open, high, low, close, volume)
            Index should be datetime
    
    Returns:
        DataFrame with OHLCV + all indicator columns
    """
    if df is None or df.empty:
        return df
    
    # Make a copy to avoid modifying original
    df = df.copy()
    
    # Ensure we have required columns
    required = ['open', 'high', 'low', 'close', 'volume']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    
    # Calculate indicators
    df = calculate_sma(df)
    df = calculate_ema(df)
    df = calculate_bollinger_bands(df)
    df = calculate_macd(df)
    df = calculate_rsi(df)
    df = calculate_stochastic(df)
    df = calculate_atr(df)
    df = calculate_volume_indicators(df)
    
    return df


def calculate_sma(df: pd.DataFrame, periods: list = [20, 50]) -> pd.DataFrame:
    """Calculate Simple Moving Averages"""
    for period in periods:
        df[f'sma_{period}'] = df['close'].rolling(window=period).mean()
    return df


def calculate_ema(df: pd.DataFrame, periods: list = [12, 26]) -> pd.DataFrame:
    """Calculate Exponential Moving Averages"""
    for period in periods:
        df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
    return df


def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """Calculate Bollinger Bands"""
    df['bb_mid'] = df['close'].rolling(window=period).mean()
    rolling_std = df['close'].rolling(window=period).std()
    df['bb_upper'] = df['bb_mid'] + (rolling_std * std_dev)
    df['bb_lower'] = df['bb_mid'] - (rolling_std * std_dev)
    return df


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Calculate MACD"""
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd'] = ema_fast - ema_slow
    df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    return df


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calculate RSI (Relative Strength Index)"""
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    # Avoid division by zero
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df


def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    """Calculate Stochastic Oscillator"""
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    
    # Avoid division by zero
    range_val = high_max - low_min
    range_val = range_val.replace(0, np.nan)
    
    df['stoch_k'] = 100 * ((df['close'] - low_min) / range_val)
    df['stoch_d'] = df['stoch_k'].rolling(window=d_period).mean()
    
    return df


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calculate ATR (Average True Range)"""
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = true_range.rolling(window=period).mean()
    
    return df


def calculate_volume_indicators(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Calculate volume-based indicators"""
    # Volume SMA
    df['volume_sma'] = df['volume'].rolling(window=period).mean()
    
    # OBV (On Balance Volume)
    obv = [0]
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['close'].iloc[i-1]:
            obv.append(obv[-1] + df['volume'].iloc[i])
        elif df['close'].iloc[i] < df['close'].iloc[i-1]:
            obv.append(obv[-1] - df['volume'].iloc[i])
        else:
            obv.append(obv[-1])
    df['obv'] = obv
    
    return df
