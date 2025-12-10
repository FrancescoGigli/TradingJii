"""
Feature Engineering Module

Temporal feature creation for XGBoost training.
Converts sequences of candles into structured features that capture:
- Current market state
- Momentum patterns across time
- Critical indicator statistics
"""

from __future__ import annotations

import logging
import numpy as np

import config
from config import N_FEATURES_FINAL

_LOG = logging.getLogger(__name__)


def create_temporal_features(sequence):
    """
    ENHANCED B+ HYBRID: Momentum + Selective Statistics for ALL intermediate candles
    
    REVOLUTIONARY UPGRADE:
    - Uses ALL intermediate candles (was wasting 92% of data!)
    - Momentum patterns across full sequence 
    - Statistical analysis for critical trading features
    - Maintains N_FEATURES_FINAL = 66 compatibility
    
    Args:
        sequence (np.ndarray): Sequence of shape (timesteps, 33_features)
        
    Returns:
        np.ndarray: Enhanced temporal features (66 total)
    """
    try:
        features = []
        
        # CRITICAL FEATURES indices for enhanced statistics
        CRITICAL_FEATURES = {
            'close': 3,      # Price (most important)
            'volume': 4,     # Volume (breakout confirmation)  
            'rsi_fast': 13,  # RSI (momentum oscillator)
            'atr': 14,       # ATR (volatility measure)
            'macd': 8,       # MACD (trend strength)
            'ema20': 7       # EMA20 (trend reference)
        }
        
        # 1. CURRENT STATE (33 features) - Latest candle
        features.extend(sequence[-1])
        _LOG.debug(f"Current state features: {len(sequence[-1])}")
        
        # 2. MOMENTUM PATTERNS (27 features) - Using ALL intermediate candles
        momentum_features = []
        
        # Select most important features for momentum analysis (reduce from 33 to 27)
        important_feature_indices = [0, 1, 2, 3, 4, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]  # Skip less critical swing features
        
        for col_idx in important_feature_indices:
            if col_idx < sequence.shape[1]:
                col_data = sequence[:, col_idx]
                
                # Advanced momentum analysis using ALL timesteps
                if len(col_data) > 1:
                    # Linear trend strength across full sequence
                    time_index = np.arange(len(col_data))
                    correlation = np.corrcoef(time_index, col_data)[0,1]
                    
                    # Handle NaN correlation (constant values)
                    momentum_features.append(correlation if np.isfinite(correlation) else 0.0)
                else:
                    momentum_features.append(0.0)
        
        features.extend(momentum_features)
        _LOG.debug(f"Momentum features: {len(momentum_features)}")
        
        # 3. CRITICAL FEATURE STATISTICS (6 features) - Deep analysis of key indicators
        critical_stats = []
        
        for feature_name, col_idx in CRITICAL_FEATURES.items():
            if col_idx < sequence.shape[1]:
                col_data = sequence[:, col_idx]
                
                if len(col_data) > 1:
                    # Volatility measure (how much feature varied during period)
                    volatility = np.std(col_data) / (np.mean(np.abs(col_data)) + 1e-8)
                    critical_stats.append(volatility)
                else:
                    critical_stats.append(0.0)
            else:
                critical_stats.append(0.0)
        
        features.extend(critical_stats)
        _LOG.debug(f"Critical stats features: {len(critical_stats)}")
        
        # TOTAL CALCULATION: 33 + 27 + 6 = 66 features (perfect compatibility!)
        
        # Clean and validate all features
        features = np.array(features, dtype=np.float64)
        features = np.nan_to_num(features, nan=0.0, posinf=1e6, neginf=-1e6)
        
        # ENHANCED VALIDATION with detailed logging
        final_features = features.flatten()
        actual_count = len(final_features)
        
        _LOG.debug(f"🧠 Feature breakdown: Current={len(sequence[-1])}, Momentum={len(momentum_features)}, Critical={len(critical_stats)}, Total={actual_count}")
        
        if actual_count != N_FEATURES_FINAL:
            _LOG.warning(f"⚠️ Feature count adjustment: Expected {N_FEATURES_FINAL}, got {actual_count}")
            
            if actual_count < N_FEATURES_FINAL:
                # Pad with zeros if too few
                padding = np.zeros(N_FEATURES_FINAL - actual_count)
                final_features = np.concatenate([final_features, padding])
                _LOG.info(f"   ✅ Padded to {len(final_features)} features")
            else:
                # Truncate if too many (keep most important)
                final_features = final_features[:N_FEATURES_FINAL]
                _LOG.info(f"   ✅ Truncated to {len(final_features)} features")
        else:
            _LOG.debug(f"✅ Perfect feature count: {actual_count}")
        
        return final_features
        
    except Exception as e:
        _LOG.error(f"❌ Error in enhanced temporal features: {e}")
        # Emergency fallback: original simple approach
        return create_temporal_features_fallback(sequence)


def create_temporal_features_fallback(sequence):
    """Emergency fallback to original approach if enhanced version fails"""
    try:
        features = []
        features.extend(sequence[-1])  # Current: 33
        
        if len(sequence) > 1:
            price_change = (sequence[-1] - sequence[0]) / (np.abs(sequence[0]) + 1e-8)
            features.extend(price_change)  # Trend: 33
        else:
            features.extend(np.zeros(sequence.shape[1]))
            
        features = np.array(features, dtype=np.float64)
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
        
        return features.flatten()[:N_FEATURES_FINAL]
        
    except Exception as e:
        _LOG.error(f"❌ Even fallback failed: {e}")
        # Last resort: zeros
        return np.zeros(N_FEATURES_FINAL)
