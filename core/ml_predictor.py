"""
Robust ML Predictor module that fixes the critical model loading failures.

FIXES:
- NoneType scaler.transform() errors
- Proper model validation before usage
- Fallback mechanisms for failed predictions  
- Centralized model management
"""

import logging
import os
import joblib
import numpy as np
from typing import Dict, Tuple, Optional, Any
from dataclasses import dataclass

from config import (
    get_xgb_model_file, get_xgb_scaler_file, EXPECTED_COLUMNS,
    NEUTRAL_UPPER_THRESHOLD, NEUTRAL_LOWER_THRESHOLD, N_FEATURES_FINAL
)
from core.confidence_calibrator import global_calibrator


@dataclass
class ModelPrediction:
    """Structured prediction result"""
    symbol: str
    timeframe: str
    prediction: Optional[int]  # 0=SELL, 1=BUY, 2=NEUTRAL, None=FAILED
    confidence: float
    error: Optional[str] = None


class RobustMLPredictor:
    """
    Robust ML Predictor that handles model loading failures gracefully
    """
    
    def __init__(self, timeframes: list, preloaded_models=None, preloaded_scalers=None):
        self.timeframes = timeframes
        self.models = {}
        self.scalers = {}
        self.model_status = {}
        
        # If models are already loaded, use them directly (for parallel workers)
        if preloaded_models is not None and preloaded_scalers is not None:
            self.models = preloaded_models
            self.scalers = preloaded_scalers
            self.model_status = {tf: True for tf in timeframes if tf in preloaded_models}
            logging.debug(f"✅ Using preloaded models for {len(self.model_status)} timeframes")
        else:
            # Load from disk only if not preloaded
            self._load_all_models()
    
    def _load_all_models(self):
        """Load all models with comprehensive validation"""
        logging.debug("🔄 Loading ML models from disk...")  # Changed to debug to avoid spam
        
        for tf in self.timeframes:
            success = self._load_model_for_timeframe(tf)
            self.model_status[tf] = success
            
        # Check if we have at least one working model
        working_models = sum(1 for status in self.model_status.values() if status)
        total_models = len(self.model_status)
        
        if working_models == 0:
            raise RuntimeError("❌ CRITICAL: No ML models loaded successfully. Bot cannot operate.")
        elif working_models < total_models:
            logging.warning(f"⚠️ Only {working_models}/{total_models} models loaded successfully")
        else:
            logging.debug(f"✅ All {working_models} ML models loaded from disk")  # Changed to debug
    
    def _load_model_for_timeframe(self, timeframe: str) -> bool:
        """Load model and scaler for a specific timeframe with validation"""
        try:
            model_file = get_xgb_model_file(timeframe)
            scaler_file = get_xgb_scaler_file(timeframe)
            
            # Check file existence
            if not os.path.exists(model_file):
                logging.error(f"❌ Model file not found for {timeframe}: {model_file}")
                return False
                
            if not os.path.exists(scaler_file):
                logging.error(f"❌ Scaler file not found for {timeframe}: {scaler_file}")
                return False
            
            # Load model and scaler
            model = joblib.load(model_file)
            scaler = joblib.load(scaler_file)
            
            # Validate model and scaler
            if model is None:
                logging.error(f"❌ Model loaded as None for {timeframe}")
                return False
                
            if scaler is None:
                logging.error(f"❌ Scaler loaded as None for {timeframe}")
                return False
                
            # Test prediction capability with dummy data
            try:
                dummy_features = self._create_dummy_features()
                dummy_scaled = scaler.transform(dummy_features.reshape(1, -1))
                dummy_pred = model.predict_proba(dummy_scaled)
                
                if dummy_pred is None or len(dummy_pred) == 0:
                    logging.error(f"❌ Model prediction test failed for {timeframe}")
                    return False
                    
            except Exception as test_error:
                logging.error(f"❌ Model validation test failed for {timeframe}: {test_error}")
                return False
            
            # If we get here, model is valid
            self.models[timeframe] = model
            self.scalers[timeframe] = scaler
            logging.debug(f"✅ Model loaded and validated for {timeframe}")  # Changed to debug
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to load model for {timeframe}: {e}")
            return False
    
    def _create_dummy_features(self) -> np.ndarray:
        """Create dummy features for model validation testing"""
        # CRITICAL FIX: Use unified constant to prevent feature count mismatch
        # Must match create_temporal_features() output exactly
        return np.random.random(N_FEATURES_FINAL)
    
    def predict_for_symbol(self, symbol: str, dataframes: Dict[str, Any], time_steps: int) -> Tuple[Optional[float], Optional[int], Dict[str, int]]:
        """
        Make robust predictions for a symbol across all timeframes
        
        Returns:
            ensemble_confidence, final_signal, individual_predictions
        """
        predictions = {}
        confidences = {}
        
        # Get predictions from all available models
        for tf, df in dataframes.items():
            if tf not in self.model_status or not self.model_status[tf]:
                logging.warning(f"⚠️ Skipping {symbol}[{tf}]: Model not available")
                continue
                
            try:
                pred_result = self._predict_single_timeframe(symbol, tf, df, time_steps)
                
                if pred_result.prediction is not None:
                    predictions[tf] = pred_result.prediction
                    confidences[tf] = pred_result.confidence
                else:
                    logging.warning(f"⚠️ Prediction failed for {symbol}[{tf}]: {pred_result.error}")
                    
            except Exception as e:
                logging.error(f"❌ Unexpected error predicting {symbol}[{tf}]: {e}")
                continue
        
        # If no predictions succeeded, return failure
        if not predictions:
            logging.error(f"❌ All predictions failed for {symbol}")
            return None, None, {}
        
        # Ensemble voting from successful predictions
        ensemble_confidence, final_signal = self._ensemble_vote(predictions, confidences)
        
        return ensemble_confidence, final_signal, predictions
    
    def _predict_single_timeframe(self, symbol: str, timeframe: str, df: Any, time_steps: int) -> ModelPrediction:
        """Make prediction for single timeframe with comprehensive error handling"""
        
        try:
            # CRITICAL FIX: Use uniform time window for ensemble coherence
            from config import get_timesteps_for_timeframe
            timesteps_needed = get_timesteps_for_timeframe(timeframe)
            
            # Validate inputs with correct timesteps
            if df is None or len(df) < timesteps_needed:
                return ModelPrediction(
                    symbol=symbol, 
                    timeframe=timeframe, 
                    prediction=None,
                    confidence=0.0,
                    error=f"Insufficient data: {len(df) if df is not None else 0} < {timesteps_needed} for 6h window"
                )
            
            # Verify expected columns
            if not set(df.columns) >= set(EXPECTED_COLUMNS):
                missing_cols = set(EXPECTED_COLUMNS) - set(df.columns)
                return ModelPrediction(
                    symbol=symbol,
                    timeframe=timeframe,
                    prediction=None,
                    confidence=0.0,
                    error=f"Missing columns: {missing_cols}"
                )
            
            # Prepare data - using simplified approach for now
            df_ordered = df[EXPECTED_COLUMNS]
            data = df_ordered.values
            
            # Clean data
            data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
            
            if len(data) < timesteps_needed:
                return ModelPrediction(
                    symbol=symbol,
                    timeframe=timeframe,
                    prediction=None,
                    confidence=0.0,
                    error=f"Data length {len(data)} < timesteps_needed {timesteps_needed}"
                )
            
            # FIXED: Get sequence with correct timesteps for uniform time window
            sequence = data[-timesteps_needed:]
            
            # Log ensemble fix
            logging.debug(f"{symbol} [{timeframe}]: Using {timesteps_needed} timesteps = 6h window for ensemble coherence")
            
            # Create temporal features (simplified version)
            temporal_features = self._create_temporal_features_safe(sequence)
            
            # Get model and scaler (already validated)
            model = self.models[timeframe]
            scaler = self.scalers[timeframe]
            
            # Scale features
            X_scaled = scaler.transform(temporal_features.reshape(1, -1))
            
            # Predict
            probs = model.predict_proba(X_scaled)[0]
            prediction = np.argmax(probs)
            confidence = np.max(probs)
            
            return ModelPrediction(
                symbol=symbol,
                timeframe=timeframe,
                prediction=int(prediction),
                confidence=float(confidence)
            )
            
        except Exception as e:
            return ModelPrediction(
                symbol=symbol,
                timeframe=timeframe,
                prediction=None,
                confidence=0.0,
                error=str(e)
            )
    
    def _create_temporal_features_safe(self, sequence: np.ndarray) -> np.ndarray:
        """
        ENHANCED B+ HYBRID: MUST MATCH EXACTLY trainer.py create_temporal_features()
        
        REVOLUTIONARY UPGRADE:
        - Uses ALL intermediate candles (was wasting 92% of data!)
        - Momentum patterns across full sequence 
        - Statistical analysis for critical trading features
        - Perfect sync with training logic
        """
        try:
            # Import the exact same function from trainer to ensure perfect sync
            from trainer import create_temporal_features
            return create_temporal_features(sequence)
            
        except Exception as e:
            logging.error(f"❌ Error using enhanced temporal features: {e}")
            # Emergency fallback: basic approach
            return self._create_temporal_features_basic_fallback(sequence)
    
    def _create_temporal_features_basic_fallback(self, sequence: np.ndarray) -> np.ndarray:
        """Fallback temporal features if enhanced version fails"""
        try:
            features = []
            
            # 1. CURRENT STATE (33 features)
            features.extend(sequence[-1])
            
            # 2. BASIC TREND (33 features)  
            if len(sequence) > 1:
                price_change = (sequence[-1] - sequence[0]) / (np.abs(sequence[0]) + 1e-8)
                features.extend(price_change)
            else:
                features.extend(np.zeros(sequence.shape[1]))
            
            # Clean and pad/truncate to exact count
            features = np.array(features, dtype=np.float64)
            features = np.nan_to_num(features, nan=0.0, posinf=1e6, neginf=-1e6)
            
            final_features = features.flatten()
            
            # Ensure exact feature count
            if len(final_features) < N_FEATURES_FINAL:
                padding = np.zeros(N_FEATURES_FINAL - len(final_features))
                final_features = np.concatenate([final_features, padding])
            elif len(final_features) > N_FEATURES_FINAL:
                final_features = final_features[:N_FEATURES_FINAL]
            
            return final_features
            
        except Exception as e:
            logging.error(f"❌ Even fallback failed in ml_predictor: {e}")
            # Last resort: zeros
            return np.zeros(N_FEATURES_FINAL)
    
    def _ensemble_vote(self, predictions: Dict[str, int], confidences: Dict[str, float]) -> Tuple[float, int]:
        """
        ENHANCED: Weighted ensemble voting with 2/3 timeframe fallback
        
        CRITICAL FIX V2:
        - Rebalances weights when models are missing
        - Applies disagreement penalty for 2-timeframe splits
        - Higher timeframes get more weight (more reliable, less noise)
        """
        if not predictions:
            return 0.0, 2  # No predictions -> NEUTRAL
        
        # Import timeframe weights
        from config import TIMEFRAME_WEIGHTS
        
        # Check how many timeframes we have
        n_available = len(predictions)
        n_expected = 3  # Typically 15m, 30m, 1h
        
        # Warn if models are missing
        if n_available < n_expected:
            missing = n_expected - n_available
            logging.warning(
                f"⚠️ Ensemble with {n_available}/{n_expected} timeframes - "
                f"{missing} model(s) unavailable, predictions may be less reliable"
            )
        
        # 1. REBALANCE WEIGHTS for available timeframes
        available_tfs = list(predictions.keys())
        original_total_weight = sum(TIMEFRAME_WEIGHTS.get(tf, 1.0) for tf in TIMEFRAME_WEIGHTS.keys())
        available_total_weight = sum(TIMEFRAME_WEIGHTS.get(tf, 1.0) for tf in available_tfs)
        
        # Normalization factor to maintain total weight
        weight_multiplier = original_total_weight / available_total_weight if available_total_weight > 0 else 1.0
        
        # Weighted voting with rebalanced timeframe importance
        weighted_votes = {}
        total_weight = 0.0
        
        for tf, pred in predictions.items():
            confidence = confidences.get(tf, 0.5)
            tf_weight = TIMEFRAME_WEIGHTS.get(tf, 1.0) * weight_multiplier
            
            # Combined weight: confidence × rebalanced timeframe importance
            combined_weight = confidence * tf_weight
            
            # Accumulate weighted votes
            weighted_votes[pred] = weighted_votes.get(pred, 0.0) + combined_weight
            total_weight += combined_weight
            
            logging.debug(
                f"Ensemble vote: {tf} → {pred} "
                f"(conf: {confidence:.3f}, tf_weight: {tf_weight:.3f}, combined: {combined_weight:.3f})"
            )
        
        # Get weighted majority vote
        majority_vote = max(weighted_votes.items(), key=lambda x: x[1])[0]
        majority_weight = weighted_votes[majority_vote]
        
        # Calculate base ensemble confidence (weighted)
        ensemble_confidence = majority_weight / total_weight if total_weight > 0 else 0.0
        
        # 2. DISAGREEMENT PENALTY for 2-timeframe splits
        if n_available == 2:
            unique_predictions = set(predictions.values())
            if len(unique_predictions) == 2:  # Complete disagreement
                disagreement_penalty = 0.85  # Reduce confidence by 15%
                ensemble_confidence *= disagreement_penalty
                logging.debug(
                    f"⚠️ 2-timeframe disagreement detected - "
                    f"applying {disagreement_penalty:.0%} penalty"
                )
        
        # 3. STRONG CONSENSUS BONUS (only if all available agree)
        if n_available >= 2:
            unique_predictions = set(predictions.values())
            if len(unique_predictions) == 1:  # Perfect agreement
                if n_available == 3:
                    consensus_bonus = 1.05  # +5% for 3/3 agreement
                    ensemble_confidence = min(1.0, ensemble_confidence * consensus_bonus)
                    logging.debug("🎯 Strong consensus (3/3) - applying +5% bonus")
                elif n_available == 2:
                    # No bonus for 2/2 (could be coincidence)
                    logging.debug("✓ Agreement (2/2) - no bonus applied")
        
        # 4. CALIBRATE CONFIDENCE (convert raw to realistic win rate)
        raw_confidence = ensemble_confidence
        ensemble_confidence = global_calibrator.calibrate_xgb_confidence(raw_confidence)
        
        # Log ensemble decision with calibration info
        vote_breakdown = {k: f"{v:.3f}" for k, v in weighted_votes.items()}
        signal_names = {0: 'SELL', 1: 'BUY', 2: 'NEUTRAL'}
        
        if global_calibrator.is_calibrated:
            logging.debug(
                f"Ensemble decision: {signal_names[majority_vote]} "
                f"(raw: {raw_confidence:.3f} → calibrated: {ensemble_confidence:.3f}, "
                f"votes: {vote_breakdown}, models: {n_available}/{n_expected})"
            )
        else:
            logging.debug(
                f"Ensemble decision: {signal_names[majority_vote]} "
                f"(conf: {ensemble_confidence:.3f}, votes: {vote_breakdown}, "
                f"models: {n_available}/{n_expected})"
            )
        
        return ensemble_confidence, majority_vote
    
    def get_model_status(self) -> Dict[str, bool]:
        """Get status of all models"""
        return self.model_status.copy()
    
    def is_operational(self) -> bool:
        """Check if predictor has at least one working model"""
        return any(self.model_status.values())


# Backward compatibility function for existing code
def predict_signal_ensemble(dataframes, xgb_models, xgb_scalers, symbol, time_steps):
    """
    Backward compatibility wrapper - but with robust error handling
    """
    try:
        # Check if models/scalers are actually loaded
        working_timeframes = []
        for tf in dataframes.keys():
            if (tf in xgb_models and tf in xgb_scalers and 
                xgb_models[tf] is not None and xgb_scalers[tf] is not None):
                working_timeframes.append(tf)
        
        if not working_timeframes:
            logging.error(f"❌ No working models available for {symbol}")
            return None, None, {}
        
        # Use only working timeframes
        filtered_dataframes = {tf: dataframes[tf] for tf in working_timeframes}
        
        # Create predictor instance with preloaded models (no disk loading!)
        filtered_models = {tf: xgb_models[tf] for tf in working_timeframes}
        filtered_scalers = {tf: xgb_scalers[tf] for tf in working_timeframes}
        
        predictor = RobustMLPredictor(
            timeframes=working_timeframes,
            preloaded_models=filtered_models,
            preloaded_scalers=filtered_scalers
        )
        
        # Make prediction
        return predictor.predict_for_symbol(symbol, filtered_dataframes, time_steps)
        
    except Exception as e:
        logging.error(f"❌ Robust prediction failed for {symbol}: {e}")
        return None, None, {}
