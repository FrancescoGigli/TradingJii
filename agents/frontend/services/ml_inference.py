"""
🤖 ML Inference Service
========================

Loads trained XGBoost models and provides real-time inference
for score_long and score_short predictions.

Usage in frontend:
    from services.ml_inference import get_ml_inference_service
    
    service = get_ml_inference_service()
    score_long, score_short = service.predict(df_row)
"""

import os
import pickle
import json
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass

import pandas as pd
import numpy as np

from services.feature_alignment import (
    align_features_dataframe,
    align_features_dataframe_with_report,
    align_features_row,
    FeatureAlignmentReport,
)

from services.xgb_normalization import normalize_long_short_scores

# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE CALCULATION - Compute all 69 features needed by XGB model
# ═══════════════════════════════════════════════════════════════════════════════

def compute_ml_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all 69 features required by the XGBoost model.
    
    Takes raw OHLCV data and computes technical indicators and derived features.
    Uses ONLY past data (no lookahead bias).
    
    Args:
        df: DataFrame with columns [open, high, low, close, volume]
        
    Returns:
        DataFrame with all 69 features
    """
    features = df.copy()
    
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    open_price = df['open']
    
    # ═══════════════════════════════════════════════════════════════════
    # 1. Moving Averages (6-9)
    # ═══════════════════════════════════════════════════════════════════
    features['sma_20'] = close.rolling(20).mean()
    features['sma_50'] = close.rolling(50).mean()
    features['ema_12'] = close.ewm(span=12, adjust=False).mean()
    features['ema_26'] = close.ewm(span=26, adjust=False).mean()
    
    # ═══════════════════════════════════════════════════════════════════
    # 2. Bollinger Bands (10-14)
    # ═══════════════════════════════════════════════════════════════════
    bb_period = 20
    bb_std = 2
    bb_mid = close.rolling(bb_period).mean()
    bb_std_val = close.rolling(bb_period).std()
    features['bb_upper'] = bb_mid + (bb_std_val * bb_std)
    features['bb_mid'] = bb_mid
    features['bb_lower'] = bb_mid - (bb_std_val * bb_std)
    features['bb_width'] = (features['bb_upper'] - features['bb_lower']) / bb_mid
    bb_range = features['bb_upper'] - features['bb_lower']
    features['bb_position'] = (close - features['bb_lower']) / bb_range.replace(0, np.nan)
    
    # ═══════════════════════════════════════════════════════════════════
    # 3. RSI (15)
    # ═══════════════════════════════════════════════════════════════════
    delta = close.diff()
    gain = delta.where(delta > 0, 0).ewm(span=14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    features['rsi'] = 100 - (100 / (1 + rs))
    
    # ═══════════════════════════════════════════════════════════════════
    # 4. MACD (16-18)
    # ═══════════════════════════════════════════════════════════════════
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    features['macd'] = ema_fast - ema_slow
    features['macd_signal'] = features['macd'].ewm(span=9, adjust=False).mean()
    features['macd_hist'] = features['macd'] - features['macd_signal']
    
    # ═══════════════════════════════════════════════════════════════════
    # 5. Stochastic (19-20)
    # ═══════════════════════════════════════════════════════════════════
    stoch_period = 14
    low_min = low.rolling(stoch_period).min()
    high_max = high.rolling(stoch_period).max()
    stoch_range = high_max - low_min
    features['stoch_k'] = 100 * (close - low_min) / stoch_range.replace(0, np.nan)
    features['stoch_d'] = features['stoch_k'].rolling(3).mean()
    
    # ═══════════════════════════════════════════════════════════════════
    # 6. ATR (21-22)
    # ═══════════════════════════════════════════════════════════════════
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    features['atr'] = tr.ewm(span=14, adjust=False).mean()
    features['atr_pct'] = features['atr'] / close
    
    # ═══════════════════════════════════════════════════════════════════
    # 7. OBV and Volume (23-24)
    # ═══════════════════════════════════════════════════════════════════
    obv_sign = np.sign(close.diff())
    features['obv'] = (obv_sign * volume).cumsum()
    features['volume_sma'] = volume.rolling(20).mean()
    
    # ═══════════════════════════════════════════════════════════════════
    # 8. ADX (25-26)
    # ═══════════════════════════════════════════════════════════════════
    adx_period = 14
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)
    atr_adx = tr.ewm(span=adx_period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=adx_period, adjust=False).mean() / atr_adx)
    minus_di = 100 * (minus_dm.ewm(span=adx_period, adjust=False).mean() / atr_adx)
    di_sum = plus_di + minus_di
    dx = 100 * abs(plus_di - minus_di) / di_sum.replace(0, np.nan)
    features['adx_14'] = dx.ewm(span=adx_period, adjust=False).mean()
    features['adx_14_norm'] = features['adx_14'] / 100
    
    # ═══════════════════════════════════════════════════════════════════
    # 9. Returns (27-29)
    # ═══════════════════════════════════════════════════════════════════
    features['ret_5'] = np.log(close / close.shift(5))
    features['ret_10'] = np.log(close / close.shift(10))
    features['ret_20'] = np.log(close / close.shift(20))
    
    # ═══════════════════════════════════════════════════════════════════
    # 10. EMA Distances and Crosses (30-34)
    # ═══════════════════════════════════════════════════════════════════
    ema_20 = close.ewm(span=20, adjust=False).mean()
    ema_50 = close.ewm(span=50, adjust=False).mean()
    ema_200 = close.ewm(span=200, adjust=False).mean()
    features['ema_20_dist'] = (close - ema_20) / ema_20
    features['ema_50_dist'] = (close - ema_50) / ema_50
    features['ema_200_dist'] = (close - ema_200) / ema_200
    features['ema_20_50_cross'] = np.sign(ema_20 - ema_50)
    features['ema_50_200_cross'] = np.sign(ema_50 - ema_200)
    
    # ═══════════════════════════════════════════════════════════════════
    # 11. Normalized Indicators (35-36)
    # ═══════════════════════════════════════════════════════════════════
    features['rsi_14_norm'] = (features['rsi'] - 50) / 50  # -1 to 1
    macd_hist_std = features['macd_hist'].rolling(100).std().replace(0, np.nan)
    features['macd_hist_norm'] = features['macd_hist'] / macd_hist_std
    
    # ═══════════════════════════════════════════════════════════════════
    # 12. Trend and Momentum (37-40)
    # ═══════════════════════════════════════════════════════════════════
    features['trend_direction'] = np.sign(close - close.shift(20))
    features['momentum_10'] = close - close.shift(10)
    features['momentum_20'] = close - close.shift(20)
    
    # ═══════════════════════════════════════════════════════════════════
    # 13. Volatility Features (41-48)
    # ═══════════════════════════════════════════════════════════════════
    log_ret = np.log(close / close.shift(1))
    features['vol_5'] = log_ret.rolling(5).std()
    features['vol_10'] = log_ret.rolling(10).std()
    features['vol_20'] = log_ret.rolling(20).std()
    features['range_pct_5'] = (high.rolling(5).max() - low.rolling(5).min()) / close
    features['range_pct_10'] = (high.rolling(10).max() - low.rolling(10).min()) / close
    features['range_pct_20'] = (high.rolling(20).max() - low.rolling(20).min()) / close
    
    # Volatility percentile
    vol_20 = features['vol_20']
    def rolling_percentile(s, w):
        return s.rolling(w).apply(lambda x: (x[:-1] < x[-1]).sum() / max(len(x) - 1, 1), raw=True)
    features['vol_percentile'] = rolling_percentile(vol_20, 100)
    features['vol_ratio'] = volume / features['volume_sma']
    features['vol_change'] = features['vol_20'] / features['vol_20'].shift(10)
    
    # ═══════════════════════════════════════════════════════════════════
    # 14. OBV and VWAP (49-51)
    # ═══════════════════════════════════════════════════════════════════
    obv_sma = features['obv'].rolling(20).mean()
    features['obv_slope'] = (features['obv'] - obv_sma) / obv_sma.abs().replace(0, 1)
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).rolling(20).sum() / volume.rolling(20).sum()
    features['vwap_dist'] = (close - vwap) / vwap
    features['vol_stability'] = features['vol_5'] / features['vol_20'].replace(0, np.nan)
    
    # ═══════════════════════════════════════════════════════════════════
    # 15. Candle Features (52-58)
    # ═══════════════════════════════════════════════════════════════════
    body = abs(close - open_price)
    candle_range = high - low
    features['body_pct'] = body / candle_range.replace(0, np.nan)
    features['candle_direction'] = np.sign(close - open_price)
    features['upper_shadow_pct'] = (high - pd.concat([open_price, close], axis=1).max(axis=1)) / candle_range.replace(0, np.nan)
    features['lower_shadow_pct'] = (pd.concat([open_price, close], axis=1).min(axis=1) - low) / candle_range.replace(0, np.nan)
    features['gap_pct'] = (open_price - close.shift(1)) / close.shift(1)
    
    # Consecutive up/down
    direction = (close > close.shift(1)).astype(int)
    features['consecutive_up'] = direction.groupby((direction != direction.shift()).cumsum()).cumsum() * direction
    direction_down = (close < close.shift(1)).astype(int)
    features['consecutive_down'] = direction_down.groupby((direction_down != direction_down.shift()).cumsum()).cumsum() * direction_down
    
    # ═══════════════════════════════════════════════════════════════════
    # 16. Speed and Acceleration (59-62)
    # ═══════════════════════════════════════════════════════════════════
    features['speed_5'] = log_ret.rolling(5).mean()
    features['speed_20'] = log_ret.rolling(20).mean()
    features['accel_5'] = features['speed_5'].diff(5)
    features['accel_20'] = features['speed_20'].diff(20)
    
    # ═══════════════════════════════════════════════════════════════════
    # 17. Percentiles and Position (63-69)
    # ═══════════════════════════════════════════════════════════════════
    features['ret_percentile_50'] = rolling_percentile(log_ret, 50)
    features['ret_percentile_100'] = rolling_percentile(log_ret, 100)
    
    def price_position(window):
        h = high.rolling(window).max()
        l = low.rolling(window).min()
        return (close - l) / (h - l).replace(0, np.nan)
    
    features['price_position_20'] = price_position(20)
    features['price_position_50'] = price_position(50)
    features['price_position_100'] = price_position(100)
    features['dist_from_high_20'] = (close - high.rolling(20).max()) / close
    features['dist_from_low_20'] = (close - low.rolling(20).min()) / close
    
    return features

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Path to models (relative to frontend container)
SHARED_PATH = os.environ.get('SHARED_DATA_PATH', '/app/shared')
MODEL_DIR = Path(SHARED_PATH) / 'models'

# Fallback for local development
if not MODEL_DIR.exists():
    # Try relative path from frontend
    MODEL_DIR = Path(__file__).parent.parent.parent.parent / 'shared' / 'models'


@dataclass
class MLPrediction:
    """ML prediction result"""
    score_long: float
    score_short: float
    score_long_normalized: float  # Normalized to -100/+100 range
    score_short_normalized: float  # Normalized to -100/+100 range
    signal_long: str  # "BUY", "NEUTRAL", "AVOID"
    signal_short: str
    confidence_long: str  # "STRONG", "MODERATE", "WEAK"
    confidence_short: str
    model_version: str
    alignment: Optional[FeatureAlignmentReport] = None
    is_valid: bool = True
    error: Optional[str] = None


def normalize_xgb_score(score: float, model_type: str = 'long') -> float:
    """
    Normalize XGBoost score to -100/+100 range using Z-score normalization.
    
    The model has good RANKING ability (Spearman ~0.05, Top 1% = 60% positive)
    but low R² (~3%) so predictions cluster around mean.
    
    Uses calibrated statistics from actual model predictions:
    - LONG model: Mean=-0.002, Std=0.004, Range=[-0.005, +0.010]
    - SHORT model: Mean=-0.005, Std=0.001, Range=[-0.006, -0.002]
    
    Args:
        score: Raw XGB score (model output)
        model_type: 'long' or 'short'
    
    Returns:
        Normalized score in range -100 to +100
    """
    # Calibrated statistics from actual predictions (200 candles BTC 1h)
    if model_type == 'long':
        # LONG: Range [-0.005, +0.010], Mean=-0.002
        # Positive scores are GOOD for long
        mean = -0.002
        std = 0.004
    else:  # short
        # SHORT model always predicts negative due to training period
        # More negative = stronger SHORT signal
        mean = -0.005
        std = 0.001
    
    # Calculate z-score
    z = (score - mean) / std if std > 0 else 0
    
    # Map z-score to -100/+100 range
    # z = ±3 → ±100
    normalized = z * 33.33
    
    # Clamp to range
    return max(-100.0, min(100.0, normalized))


def normalize_xgb_score_batch(scores: 'pd.Series', model_type: str = 'long') -> 'pd.Series':
    """
    Normalize XGBoost scores using PERCENTILE ranking.
    
    This is the CORRECT approach because:
    - Model has good RANKING (Spearman ~0.05, Top 1% = 60% positive)
    - Model has poor absolute prediction (R² ~3%)
    
    Uses percentile of each score within the batch:
    - Top 1% → +100
    - Top 5% → +80
    - Top 10% → +60
    - Median → 0
    - Bottom 10% → -60
    - Bottom 5% → -80
    - Bottom 1% → -100
    
    Args:
        scores: Series of raw XGB scores
        model_type: 'long' or 'short'
    
    Returns:
        Series of normalized scores in range -100 to +100
    """
    import pandas as pd
    
    # Calculate percentile rank (0-100)
    percentile_rank = scores.rank(pct=True) * 100
    
    # Convert to -100/+100 range
    # 0 percentile → -100
    # 50 percentile → 0
    # 100 percentile → +100
    normalized = (percentile_rank - 50) * 2
    
    return normalized


def build_normalized_xgb_frame(
    df_with_predictions: pd.DataFrame,
    *,
    long_col: str = "pred_score_long",
    short_col: str = "pred_score_short",
) -> pd.DataFrame:
    """Build a normalized XGB score frame from batch model predictions.

    This is the canonical normalization used across the UI:
    - LONG and SHORT mapped independently to 0..100 with percentile ranking.
    - SHORT may be inverted if raw outputs are mostly negative.
    - NET score is computed as long_0_100 - short_0_100 in -100..+100.

    Args:
        df_with_predictions: DataFrame containing raw prediction columns.
        long_col: Column name for raw long scores.
        short_col: Column name for raw short scores.

    Returns:
        DataFrame indexed like df_with_predictions with columns:
        - score_long_raw
        - score_short_raw
        - score_long_0_100
        - score_short_0_100
        - net_score_-100_100
        - short_inverted
    """

    if long_col not in df_with_predictions.columns or short_col not in df_with_predictions.columns:
        raise KeyError(f"Missing prediction columns: {long_col}, {short_col}")

    raw_long = df_with_predictions[long_col].to_numpy(dtype=float)
    raw_short = df_with_predictions[short_col].to_numpy(dtype=float)

    normalized = normalize_long_short_scores(raw_long, raw_short)
    out = pd.DataFrame(index=df_with_predictions.index)
    out["score_long_raw"] = raw_long
    out["score_short_raw"] = raw_short
    out["score_long_0_100"] = normalized.long_0_100
    out["score_short_0_100"] = normalized.short_0_100
    out["net_score_-100_100"] = normalized.net_score_minus_100_100
    out["short_inverted"] = bool(normalized.short_inverted)
    return out


class MLInferenceService:
    """
    Service for ML model inference.
    Loads models once and provides fast predictions.
    """
    
    def __init__(self):
        self.model_long = None
        self.model_short = None
        self.scaler = None
        self.metadata = None
        self.feature_names = []
        self.last_alignment_report: Optional[FeatureAlignmentReport] = None
        self.is_loaded = False
        self.error_message = None
        
        # Try to load models
        self._load_models()
    
    def _load_models(self):
        """Load trained models from disk"""
        try:
            model_long_path = MODEL_DIR / 'model_long_latest.pkl'
            model_short_path = MODEL_DIR / 'model_short_latest.pkl'
            scaler_path = MODEL_DIR / 'scaler_latest.pkl'
            metadata_path = MODEL_DIR / 'metadata_latest.json'
            
            if not model_long_path.exists():
                self.error_message = f"Model not found: {model_long_path}"
                return
            
            # Load models
            with open(model_long_path, 'rb') as f:
                self.model_long = pickle.load(f)
            
            with open(model_short_path, 'rb') as f:
                self.model_short = pickle.load(f)
            
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)
            
            self.feature_names = self.metadata.get('feature_names', [])
            self.is_loaded = True
            
        except Exception as e:
            self.error_message = f"Error loading models: {str(e)}"
            self.is_loaded = False
    
    @property
    def is_available(self) -> bool:
        """Check if models are loaded and ready"""
        return self.is_loaded
    
    @property
    def model_version(self) -> str:
        """Get model version string"""
        if self.metadata:
            return self.metadata.get('version', 'unknown')
        return 'not_loaded'
    
    def predict(self, df_row: pd.Series) -> MLPrediction:
        """
        Make prediction for a single row (candle).
        
        Args:
            df_row: pandas Series with feature values (from OHLCV + indicators)
            
        Returns:
            MLPrediction with score_long, score_short, and signals
        """
        if not self.is_loaded:
            return MLPrediction(
                score_long=0.0,
                score_short=0.0,
                score_long_normalized=0.0,
                score_short_normalized=0.0,
                signal_long="N/A",
                signal_short="N/A",
                confidence_long="N/A",
                confidence_short="N/A",
                model_version="not_loaded",
                alignment=None,
                is_valid=False,
                error=self.error_message
            )
        
        try:
            # Build an aligned DataFrame to avoid sklearn warnings about missing
            # feature names and to enforce the correct feature order.
            X_df = align_features_row(df_row, self.feature_names, fill_value=0.0)
            X_scaled = self.scaler.transform(X_df)
            
            # Predict
            score_long = float(self.model_long.predict(X_scaled)[0])
            score_short = float(self.model_short.predict(X_scaled)[0])
            
            # Determine signals
            signal_long, conf_long = self._interpret_score(score_long)
            signal_short, conf_short = self._interpret_score(score_short)
            
            # Calculate normalized scores (same range as Signal Calculator: -100 to +100)
            score_long_norm = normalize_xgb_score(score_long)
            score_short_norm = normalize_xgb_score(score_short)

            # Best-effort alignment diagnostics (row alignment always fills missing features)
            # We treat the input row as a 1-row DataFrame for reporting.
            _, report = align_features_dataframe_with_report(
                pd.DataFrame([df_row.to_dict()]),
                self.feature_names,
                fill_value=0.0,
                forward_fill=False,
            )
            self.last_alignment_report = report
            
            return MLPrediction(
                score_long=score_long,
                score_short=score_short,
                score_long_normalized=score_long_norm,
                score_short_normalized=score_short_norm,
                signal_long=signal_long,
                signal_short=signal_short,
                confidence_long=conf_long,
                confidence_short=conf_short,
                model_version=self.model_version,
                alignment=report,
                is_valid=True,
                error=None
            )
            
        except Exception as e:
            return MLPrediction(
                score_long=0.0,
                score_short=0.0,
                score_long_normalized=0.0,
                score_short_normalized=0.0,
                signal_long="ERROR",
                signal_short="ERROR",
                confidence_long="N/A",
                confidence_short="N/A",
                model_version=self.model_version,
                alignment=self.last_alignment_report,
                is_valid=False,
                error=str(e)
            )
    
    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Make predictions for multiple rows.
        
        Args:
            df: DataFrame with features
            
        Returns:
            DataFrame with added pred_score_long, pred_score_short columns
        """
        if not self.is_loaded:
            df = df.copy()
            df['pred_score_long'] = 0.0
            df['pred_score_short'] = 0.0
            return df
        
        try:
            # Align to the expected feature set to avoid sklearn warnings and
            # ensure consistent ordering.
            X_df, report = align_features_dataframe_with_report(
                df,
                self.feature_names,
                fill_value=0.0,
                forward_fill=True,
            )
            self.last_alignment_report = report
            X_scaled = self.scaler.transform(X_df)
            
            # Predict
            df = df.copy()
            df['pred_score_long'] = self.model_long.predict(X_scaled)
            df['pred_score_short'] = self.model_short.predict(X_scaled)
            
            return df
            
        except Exception as e:
            df = df.copy()
            df['pred_score_long'] = 0.0
            df['pred_score_short'] = 0.0
            return df

    def get_alignment_report(self) -> Optional[FeatureAlignmentReport]:
        """Return the last feature alignment diagnostics (if any)."""
        return self.last_alignment_report
    
    def _interpret_score(self, score: float) -> Tuple[str, str]:
        """
        Interpret score into signal and confidence.
        
        Based on training data distribution:
        - Top 1%: score > 0.015 (strong)
        - Top 5%: score > 0.003 (moderate)
        - Top 10%: score > 0 (weak)
        """
        if score > 0.015:
            return "BUY", "STRONG"
        elif score > 0.005:
            return "BUY", "MODERATE"
        elif score > 0.001:
            return "BUY", "WEAK"
        elif score > -0.001:
            return "NEUTRAL", "NEUTRAL"
        elif score > -0.005:
            return "AVOID", "WEAK"
        else:
            return "AVOID", "MODERATE"
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get model metrics from metadata"""
        if not self.metadata:
            return {}
        
        return {
            'long': self.metadata.get('metrics_long', {}),
            'short': self.metadata.get('metrics_short', {}),
            'version': self.model_version,
            'n_features': self.metadata.get('n_features', 0)
        }
    
    def get_metadata(self) -> Optional[Dict[str, Any]]:
        """
        Get full model metadata including training date ranges.
        
        Returns:
            dict with:
                - version: model version string
                - created_at: timestamp
                - data_range: {train_start, train_end, test_start, test_end}
                - symbols: list of symbols used in training
                - timeframes: list of timeframes used
                - metrics_long, metrics_short: model performance
                - n_features: number of features
        """
        return self.metadata


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_ml_inference_service = None


def get_ml_inference_service() -> MLInferenceService:
    """Get singleton instance of ML inference service"""
    global _ml_inference_service
    if _ml_inference_service is None:
        _ml_inference_service = MLInferenceService()
    return _ml_inference_service
