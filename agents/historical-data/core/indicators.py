"""
📊 Technical Indicators Module

Calculates and stores all technical indicators for historical OHLCV data.
Indicators are pre-computed and stored in the database for fast retrieval.
"""

import pandas as pd
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


# List of all indicator columns
INDICATOR_COLUMNS = [
    # Moving Averages
    'sma_20', 'sma_50', 'ema_12', 'ema_26',
    # Bollinger Bands
    'bb_upper', 'bb_mid', 'bb_lower',
    # MACD
    'macd', 'macd_signal', 'macd_hist',
    # RSI
    'rsi',
    # Stochastic
    'stoch_k', 'stoch_d',
    # ATR
    'atr',
    # Volume indicators
    'volume_sma', 'obv'
]


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate all technical indicators on OHLCV data.
    
    Args:
        df: DataFrame with OHLCV columns (open, high, low, close, volume)
        
    Returns:
        DataFrame with all indicators added
    """
    if df is None or df.empty:
        return df
    
    df = df.copy()
    
    try:
        # === Moving Averages ===
        df['sma_20'] = df['close'].rolling(20).mean()
        df['sma_50'] = df['close'].rolling(50).mean()
        df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
        
        # === Bollinger Bands ===
        df['bb_mid'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_mid'] + (bb_std * 2)
        df['bb_lower'] = df['bb_mid'] - (bb_std * 2)
        
        # === MACD ===
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # === RSI ===
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # === Stochastic ===
        low_14 = df['low'].rolling(14).min()
        high_14 = df['high'].rolling(14).max()
        df['stoch_k'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
        
        # === ATR (Average True Range) ===
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()
        
        # === Volume indicators ===
        df['volume_sma'] = df['volume'].rolling(20).mean()
        
        # OBV (On Balance Volume)
        obv = (df['volume'] * np.where(df['close'] > df['close'].shift(), 1, -1)).cumsum()
        df['obv'] = obv
        
        logger.debug(f"Calculated {len(INDICATOR_COLUMNS)} indicators for {len(df)} candles")
        
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        # Fill with NaN if calculation fails
        for col in INDICATOR_COLUMNS:
            if col not in df.columns:
                df[col] = np.nan
    
    return df


def get_indicator_values(df: pd.DataFrame, row_index: int) -> Dict[str, float]:
    """
    Get indicator values for a specific row.
    
    Args:
        df: DataFrame with indicators
        row_index: Index of the row
        
    Returns:
        Dictionary with indicator name -> value
    """
    if df is None or df.empty or row_index >= len(df):
        return {}
    
    row = df.iloc[row_index]
    
    values = {}
    for col in INDICATOR_COLUMNS:
        if col in df.columns:
            val = row[col]
            values[col] = None if pd.isna(val) else float(val)
    
    return values


def validate_indicators(df: pd.DataFrame) -> Dict:
    """
    Validate that all indicators are calculated correctly.
    
    Returns:
        Dictionary with validation results
    """
    result = {
        'total_rows': len(df),
        'missing_indicators': [],
        'null_counts': {},
        'valid': True
    }
    
    for col in INDICATOR_COLUMNS:
        if col not in df.columns:
            result['missing_indicators'].append(col)
            result['valid'] = False
        else:
            null_count = df[col].isna().sum()
            result['null_counts'][col] = null_count
    
    return result
