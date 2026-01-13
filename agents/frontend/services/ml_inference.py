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
    is_valid: bool = True
    error: Optional[str] = None


def normalize_xgb_score(score: float) -> float:
    """
    Normalize XGBoost score to -100/+100 range (same as Signal Calculator).
    
    XGB score ranges typically from -0.02 to +0.02:
    - Top 1% (score > 0.015): maps to +80 to +100
    - Top 5% (score > 0.005): maps to +40 to +80
    - Top 10% (score > 0.001): maps to +10 to +40
    - Neutral (-0.001 to +0.001): maps to -10 to +10
    - Bottom 10% (score < -0.001): maps to -10 to -40
    - Bottom 5% (score < -0.005): maps to -40 to -80
    - Bottom 1% (score < -0.015): maps to -80 to -100
    
    Args:
        score: Raw XGB score (typically -0.02 to +0.02)
    
    Returns:
        Normalized score in range -100 to +100
    """
    if score >= 0.020:
        return 100.0
    elif score >= 0.015:
        # 0.015 to 0.020 → 80 to 100
        return 80.0 + (score - 0.015) / 0.005 * 20.0
    elif score >= 0.005:
        # 0.005 to 0.015 → 40 to 80
        return 40.0 + (score - 0.005) / 0.010 * 40.0
    elif score >= 0.001:
        # 0.001 to 0.005 → 10 to 40
        return 10.0 + (score - 0.001) / 0.004 * 30.0
    elif score >= -0.001:
        # -0.001 to 0.001 → -10 to 10
        return score / 0.001 * 10.0
    elif score >= -0.005:
        # -0.005 to -0.001 → -40 to -10
        return -10.0 + (score + 0.001) / 0.004 * 30.0
    elif score >= -0.015:
        # -0.015 to -0.005 → -80 to -40
        return -40.0 + (score + 0.005) / 0.010 * 40.0
    elif score >= -0.020:
        # -0.020 to -0.015 → -100 to -80
        return -80.0 + (score + 0.015) / 0.005 * 20.0
    else:
        return -100.0


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
                is_valid=False,
                error=self.error_message
            )
        
        try:
            # Extract features in correct order
            features = []
            missing_features = []
            
            for feat in self.feature_names:
                if feat in df_row.index:
                    val = df_row[feat]
                    # Handle NaN
                    if pd.isna(val):
                        features.append(0.0)
                    else:
                        features.append(float(val))
                else:
                    features.append(0.0)
                    missing_features.append(feat)
            
            # Convert to numpy array
            X = np.array(features).reshape(1, -1)
            
            # Scale
            X_scaled = self.scaler.transform(X)
            
            # Predict
            score_long = float(self.model_long.predict(X_scaled)[0])
            score_short = float(self.model_short.predict(X_scaled)[0])
            
            # Determine signals
            signal_long, conf_long = self._interpret_score(score_long)
            signal_short, conf_short = self._interpret_score(score_short)
            
            # Calculate normalized scores (same range as Signal Calculator: -100 to +100)
            score_long_norm = normalize_xgb_score(score_long)
            score_short_norm = normalize_xgb_score(score_short)
            
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
            # Extract features
            available_features = [f for f in self.feature_names if f in df.columns]
            X = df[available_features].fillna(0).values
            
            # Pad missing features with zeros
            if len(available_features) < len(self.feature_names):
                # Create full feature matrix
                X_full = np.zeros((len(df), len(self.feature_names)))
                for i, feat in enumerate(self.feature_names):
                    if feat in df.columns:
                        X_full[:, i] = df[feat].fillna(0).values
                X = X_full
            
            # Scale
            X_scaled = self.scaler.transform(X)
            
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
