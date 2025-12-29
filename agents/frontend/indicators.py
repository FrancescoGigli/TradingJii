"""
Technical indicators calculations for the Crypto Dashboard
"""

import pandas as pd
import numpy as np


def calculate_rsi(df, period=14):
    """Calculate RSI (Relative Strength Index)"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_macd(df, fast=12, slow=26, signal=9):
    """Calculate MACD (Moving Average Convergence Divergence)"""
    ema_fast = df['close'].ewm(span=fast).mean()
    ema_slow = df['close'].ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(df, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    sma = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


def calculate_atr(df, period=14):
    """Calculate ATR (Average True Range)"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_vwap(df):
    """Calculate VWAP (Volume Weighted Average Price)"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    return (typical_price * df['volume']).cumsum() / df['volume'].cumsum()


def calculate_ema(df, period):
    """Calculate EMA (Exponential Moving Average)"""
    return df['close'].ewm(span=period).mean()


def calculate_sma(df, period):
    """Calculate SMA (Simple Moving Average)"""
    return df['close'].rolling(window=period).mean()
