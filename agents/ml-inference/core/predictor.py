"""
🤖 ML Inference Agent - Predictor (XGBoost Inference)
"""

import pickle
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import xgboost as xgb

from config import MODELS_PATH, SCORE_MULTIPLIER

logger = logging.getLogger(__name__)


class MLPredictor:
    """XGBoost model predictor for ML inference"""
    
    def __init__(self):
        self.model_long = None
        self.model_short = None
        self.feature_names = None
        self.model_version = None
        self._loaded = False
    
    def load_models(self, version: str = "latest") -> bool:
        """Load XGBoost models from disk"""
        try:
            models_dir = Path(MODELS_PATH)
            
            # Load models (file naming convention from train_optuna.py)
            model_long_path = models_dir / f"model_long_{version}.pkl"
            model_short_path = models_dir / f"model_short_{version}.pkl"
            metadata_path = models_dir / f"metadata_{version}.json"
            
            if not all(p.exists() for p in [model_long_path, model_short_path, metadata_path]):
                logger.error(f"❌ Model files not found for version: {version}")
                return False
            
            with open(model_long_path, 'rb') as f:
                self.model_long = pickle.load(f)
            
            with open(model_short_path, 'rb') as f:
                self.model_short = pickle.load(f)
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            self.feature_names = metadata.get('feature_names', [])
            self.model_version = version
            self._loaded = True
            
            logger.info(f"✅ Loaded models version: {version}")
            logger.info(f"   Features: {len(self.feature_names)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load models: {e}")
            return False
    
    def is_loaded(self) -> bool:
        return self._loaded
    
    def calculate_features(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Calculate technical indicators (features) from OHLCV data"""
        if len(df) < 50:
            return None
        
        df = df.copy()
        
        # === MOVING AVERAGES ===
        for period in [7, 14, 21, 50]:
            df[f'sma_{period}'] = df['close'].rolling(period).mean()
            df[f'ema_{period}'] = df['close'].ewm(span=period).mean()
        
        # === RSI ===
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi_14_norm'] = (df['rsi'] - 50) / 50
        
        # === MACD ===
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        df['macd_hist_norm'] = df['macd_hist'] / (df['close'] * 0.01)
        
        # === BOLLINGER BANDS ===
        sma20 = df['close'].rolling(20).mean()
        std20 = df['close'].rolling(20).std()
        df['bb_upper'] = sma20 + 2 * std20
        df['bb_lower'] = sma20 - 2 * std20
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / sma20
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-10)
        
        # === ATR ===
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr_14'] = tr.rolling(14).mean()
        df['atr_pct'] = df['atr_14'] / df['close']
        
        # === VOLUME ===
        df['volume_sma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / (df['volume_sma'] + 1e-10)
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).cumsum()
        
        # === RETURNS ===
        for period in [1, 3, 5, 10, 20]:
            df[f'ret_{period}'] = df['close'].pct_change(period)
        
        # === MOMENTUM ===
        df['momentum_10'] = df['close'] / df['close'].shift(10) - 1
        df['momentum_20'] = df['close'] / df['close'].shift(20) - 1
        
        # === STOCHASTIC ===
        low14 = df['low'].rolling(14).min()
        high14 = df['high'].rolling(14).max()
        df['stoch_k'] = 100 * (df['close'] - low14) / (high14 - low14 + 1e-10)
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
        
        # === ADX (simplified) ===
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        atr14 = tr.rolling(14).mean()
        plus_di = 100 * plus_dm.rolling(14).mean() / (atr14 + 1e-10)
        minus_di = 100 * minus_dm.rolling(14).mean() / (atr14 + 1e-10)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        df['adx'] = dx.rolling(14).mean()
        
        # === PRICE POSITION ===
        df['dist_sma_50'] = (df['close'] - df['sma_50']) / df['sma_50']
        df['high_low_range'] = (df['high'] - df['low']) / df['close']
        
        # === VOLATILITY ===
        df['vol_20'] = df['ret_1'].rolling(20).std()
        df['vol_ratio'] = df['vol_20'] / df['vol_20'].rolling(50).mean()
        
        return df
    
    def predict(self, df: pd.DataFrame) -> Optional[Dict]:
        """Make prediction for the latest candle"""
        if not self._loaded:
            logger.error("Models not loaded")
            return None
        
        # Calculate features
        df_features = self.calculate_features(df)
        if df_features is None:
            return None
        
        # Get last row features
        last_row = df_features.iloc[-1:]
        
        # Select only needed features
        available_features = [f for f in self.feature_names if f in df_features.columns]
        if len(available_features) < len(self.feature_names) * 0.8:
            logger.warning(f"Missing too many features: {len(available_features)}/{len(self.feature_names)}")
        
        # Handle missing features
        X = pd.DataFrame(index=last_row.index)
        for f in self.feature_names:
            if f in df_features.columns:
                X[f] = last_row[f].values
            else:
                X[f] = 0.0
        
        # Fill NaN
        X = X.fillna(0)
        
        # Predict
        score_long = float(self.model_long.predict(X)[0])
        score_short = float(self.model_short.predict(X)[0])
        
        # Normalize to -100..+100
        confidence_long = max(-100, min(100, score_long * SCORE_MULTIPLIER))
        confidence_short = max(-100, min(100, score_short * SCORE_MULTIPLIER))
        
        # Interpret signals
        signal_long = self._interpret_score(score_long)
        signal_short = self._interpret_score(score_short)
        
        return {
            'score_long': score_long,
            'score_short': score_short,
            'confidence_long': confidence_long,
            'confidence_short': confidence_short,
            'signal_long': signal_long,
            'signal_short': signal_short,
            'timestamp': df_features.iloc[-1]['timestamp'],
            'model_version': self.model_version
        }
    
    def _interpret_score(self, score: float) -> str:
        """Interpret raw score into signal"""
        if score > 0.005:
            return "BUY"
        elif score > 0:
            return "NEUTRAL"
        else:
            return "AVOID"
    
    def predict_batch(self, symbols_data: Dict[str, pd.DataFrame]) -> List[Dict]:
        """Predict for multiple symbols at once"""
        results = []
        
        for symbol, df in symbols_data.items():
            try:
                pred = self.predict(df)
                if pred:
                    pred['symbol'] = symbol
                    results.append(pred)
            except Exception as e:
                logger.error(f"Error predicting {symbol}: {e}")
        
        return results
