"""
🎯 Signal Calculator - Confidence Score Generation

Calculates a confidence score from -100 (strong SHORT) to +100 (strong LONG)
based on RSI, MACD, and Bollinger Bands indicators.

Each indicator contributes up to ±33.33 points to the total score.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict
from dataclasses import dataclass

import sys
import os

# Add parent directory to path for imports when running as module
_parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from indicators import calculate_rsi, calculate_macd, calculate_bollinger_bands
from ..core.config import BACKTEST_CONFIG


@dataclass
class SignalComponents:
    """Container for individual signal components"""
    rsi_score: pd.Series
    macd_score: pd.Series
    bb_score: pd.Series
    total_score: pd.Series
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert to DataFrame for easy visualization"""
        return pd.DataFrame({
            'rsi_score': self.rsi_score,
            'macd_score': self.macd_score,
            'bb_score': self.bb_score,
            'confidence': self.total_score
        })


class SignalCalculator:
    """
    Calculates confidence scores from technical indicators.
    
    Score ranges from -100 (very strong SHORT) to +100 (very strong LONG).
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or BACKTEST_CONFIG
        self.weights = self.config['weights']
        
    def calculate(self, df: pd.DataFrame) -> SignalComponents:
        """
        Calculate confidence score for each row in the DataFrame.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            SignalComponents with individual and total scores
        """
        # Calculate individual indicator scores
        rsi_score = self._rsi_to_score(df)
        macd_score = self._macd_to_score(df)
        bb_score = self._bollinger_to_score(df)
        
        # Weighted sum (each normalized to contribute proportionally)
        total_score = (
            rsi_score * self.weights['rsi'] * 3 +      # Scale back to ±33.33
            macd_score * self.weights['macd'] * 3 +
            bb_score * self.weights['bollinger'] * 3
        )
        
        # Clip to -100 to +100
        total_score = total_score.clip(-100, 100)
        
        return SignalComponents(
            rsi_score=rsi_score,
            macd_score=macd_score,
            bb_score=bb_score,
            total_score=total_score
        )
    
    def _rsi_to_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Convert RSI to score (-33.33 to +33.33).
        
        RSI < 30 (oversold) → Positive score (LONG confidence)
        RSI > 70 (overbought) → Negative score (SHORT confidence)
        RSI 30-70 → Scaled linearly
        """
        rsi_config = self.config['rsi']
        rsi = calculate_rsi(df, rsi_config['period'])
        
        score = pd.Series(0.0, index=df.index)
        
        # Oversold zone (RSI < 30): LONG signal
        # RSI = 0 → +33.33, RSI = 30 → 0
        oversold_mask = rsi < rsi_config['oversold']
        score[oversold_mask] = 33.33 * (1 - rsi[oversold_mask] / rsi_config['oversold'])
        
        # Overbought zone (RSI > 70): SHORT signal
        # RSI = 70 → 0, RSI = 100 → -33.33
        overbought_mask = rsi > rsi_config['overbought']
        score[overbought_mask] = -33.33 * (rsi[overbought_mask] - rsi_config['overbought']) / (100 - rsi_config['overbought'])
        
        # Neutral zone (30-70): Linear scale
        # RSI = 50 → 0, RSI = 30 → +11.1, RSI = 70 → -11.1
        neutral_mask = ~oversold_mask & ~overbought_mask
        midpoint = (rsi_config['oversold'] + rsi_config['overbought']) / 2  # 50
        score[neutral_mask] = -33.33 * (rsi[neutral_mask] - midpoint) / (rsi_config['overbought'] - rsi_config['oversold'])
        
        return score
    
    def _macd_to_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Convert MACD to score (-33.33 to +33.33).
        
        MACD > Signal (bullish momentum) → Positive score
        MACD < Signal (bearish momentum) → Negative score
        
        Strength is based on the percentage difference.
        """
        macd_config = self.config['macd']
        macd_line, signal_line, _ = calculate_macd(
            df, 
            macd_config['fast'], 
            macd_config['slow'], 
            macd_config['signal']
        )
        
        # Difference as percentage of price
        diff = macd_line - signal_line
        price = df['close']
        diff_pct = (diff / price) * 100
        
        # Scale: diff_pct of ±max_diff_pct = ±33.33
        max_diff = macd_config['max_diff_pct']
        score = (diff_pct / max_diff) * 33.33
        
        # Clip to ±33.33
        return score.clip(-33.33, 33.33)
    
    def _bollinger_to_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Convert Bollinger Bands position to score (-33.33 to +33.33).
        
        Price near Lower Band (oversold) → Positive score (LONG)
        Price near Upper Band (overbought) → Negative score (SHORT)
        """
        bb_config = self.config['bollinger']
        upper, sma, lower = calculate_bollinger_bands(
            df, 
            bb_config['period'], 
            bb_config['std_dev']
        )
        
        price = df['close']
        
        # Position: 0 = at lower band, 1 = at upper band
        band_width = upper - lower
        # Avoid division by zero
        band_width = band_width.replace(0, np.nan)
        position = (price - lower) / band_width
        
        # Convert to score: 0 → +33.33, 0.5 → 0, 1 → -33.33
        score = 33.33 * (0.5 - position) * 2
        
        # Fill NaN with 0
        return score.fillna(0).clip(-33.33, 33.33)


def calculate_confidence_score(df: pd.DataFrame, config: Dict = None) -> pd.Series:
    """
    Convenience function to calculate confidence score.
    
    Args:
        df: DataFrame with OHLCV data
        config: Optional configuration dict
        
    Returns:
        Series with confidence scores (-100 to +100)
    """
    calculator = SignalCalculator(config)
    result = calculator.calculate(df)
    return result.total_score


def get_signal_breakdown(df: pd.DataFrame, index: int = -1) -> Dict:
    """
    Get detailed breakdown of signal components for a specific candle.
    
    Args:
        df: DataFrame with OHLCV data
        index: Row index (-1 for last candle)
        
    Returns:
        Dictionary with signal breakdown
    """
    calculator = SignalCalculator()
    components = calculator.calculate(df)
    
    return {
        'rsi_score': round(components.rsi_score.iloc[index], 2),
        'macd_score': round(components.macd_score.iloc[index], 2),
        'bb_score': round(components.bb_score.iloc[index], 2),
        'total_confidence': round(components.total_score.iloc[index], 2),
    }
