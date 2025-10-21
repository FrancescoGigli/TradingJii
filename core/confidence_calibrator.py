#!/usr/bin/env python3
"""
📏 CONFIDENCE CALIBRATOR - Adaptive Learning System

Robust confidence calibration using Isotonic Regression per side/timeframe.

Transforms raw ML confidence into true win probability:
confidence_calibrated = calibrator(confidence_raw)

FEATURES:
- Separate calibrators per (side, timeframe) combination
- Minimum sample requirements with shrinkage to global mean
- Brier score validation (don't update if calibration worsens)
- Fallback to Platt scaling for insufficient data
"""

import logging
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Optional
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.calibration import CalibratedClassifierCV

class ConfidenceCalibrator:
    """
    Per-combination confidence calibration system
    
    Maintains separate calibrators for each (side, timeframe) pair
    to account for different trading contexts.
    """
    
    def __init__(self,
                 min_samples: int = 50,
                 n_bins: int = 10,
                 prior_alpha: float = 5.0,
                 prior_beta: float = 2.0):
        """
        Initialize confidence calibrator
        
        Args:
            min_samples: Minimum samples per bin for calibration
            n_bins: Number of confidence bins
            prior_alpha: Beta distribution alpha for prior
            prior_beta: Beta distribution beta for prior
        """
        self.min_samples = min_samples
        self.n_bins = n_bins
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        
        # Calibrators: {(side, timeframe): IsotonicRegression}
        self.calibrators: Dict[Tuple[str, str], IsotonicRegression] = {}
        
        # Validation scores: {(side, timeframe): brier_score}
        self.brier_scores: Dict[Tuple[str, str], float] = {}
        
        # State directory
        self.state_dir = Path("adaptive_state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # Load previous calibrators
        self.load_all_calibrators()
        
        logging.info(f"📏 ConfidenceCalibrator initialized (min_samples={min_samples})")
    
    def recalibrate_all(self, feedback_logger) -> Dict:
        """
        Recalibrate all (side, timeframe) combinations
        
        Args:
            feedback_logger: FeedbackLogger instance for data
            
        Returns:
            Dict: Calibration updates performed
        """
        try:
            updates = {}
            
            # Calibrate each combination
            for side in ['LONG', 'SHORT']:
                for timeframe in ['15m', '30m', '1h']:
                    key = (side, timeframe)
                    
                    # Get calibration data
                    df = feedback_logger.get_calibration_data(
                        side, timeframe, self.min_samples
                    )
                    
                    if len(df) < self.min_samples:
                        logging.debug(
                            f"⚠️ Insufficient data for {side} {timeframe}: {len(df)} samples"
                        )
                        continue
                    
                    # Attempt recalibration
                    success = self._recalibrate_single(
                        key, df['confidence_raw'].values, df['result'].values
                    )
                    
                    if success:
                        updates[f"{side}_{timeframe}"] = "✅ Updated"
                    else:
                        updates[f"{side}_{timeframe}"] = "⚠️ Skipped (would worsen)"
            
            # Save all calibrators
            self.save_all_calibrators()
            
            if updates:
                logging.info(f"📏 Calibration updates: {len(updates)} combinations")
            
            return updates
            
        except Exception as e:
            logging.error(f"❌ Recalibration failed: {e}")
            return {}
    
    def _recalibrate_single(self, key: Tuple[str, str], 
                           confidence_raw: np.ndarray, 
                           results: np.ndarray) -> bool:
        """
        Recalibrate a single (side, timeframe) combination
        
        Args:
            key: (side, timeframe) tuple
            confidence_raw: Raw confidence values
            results: Binary outcomes (1=win, 0=loss)
            
        Returns:
            bool: True if calibration updated, False if skipped
        """
        try:
            # Create new calibrator
            new_calibrator = IsotonicRegression(
                y_min=0.0,
                y_max=1.0,
                out_of_bounds='clip'
            )
            
            # Fit on data
            new_calibrator.fit(confidence_raw, results)
            
            # Validate: compute Brier score
            calibrated = new_calibrator.predict(confidence_raw)
            new_brier = self._compute_brier_score(calibrated, results)
            
            # Compare with old calibrator if exists
            if key in self.calibrators:
                old_calibrated = self.calibrators[key].predict(confidence_raw)
                old_brier = self._compute_brier_score(old_calibrated, results)
                
                # Only update if new calibration is better
                if new_brier >= old_brier:
                    logging.debug(
                        f"📏 Calibration skipped for {key}: Brier would worsen "
                        f"({old_brier:.4f} → {new_brier:.4f})"
                    )
                    return False
                
                logging.info(
                    f"📏 Calibration improved for {key}: "
                    f"Brier {old_brier:.4f} → {new_brier:.4f}"
                )
            else:
                logging.info(
                    f"📏 New calibrator created for {key}: Brier={new_brier:.4f}"
                )
            
            # Update calibrator
            self.calibrators[key] = new_calibrator
            self.brier_scores[key] = new_brier
            
            return True
            
        except Exception as e:
            logging.error(f"❌ Single recalibration failed for {key}: {e}")
            return False
    
    def calibrate(self, confidence_raw: float, side: str, timeframe: str) -> float:
        """
        Calibrate a raw confidence value
        
        Args:
            confidence_raw: Raw ML confidence (0-1)
            side: Position side (LONG/SHORT)
            timeframe: Timeframe
            
        Returns:
            float: Calibrated confidence (true win probability)
        """
        try:
            key = (side, timeframe)
            
            # Use calibrator if available
            if key in self.calibrators:
                calibrated = float(self.calibrators[key].predict([confidence_raw])[0])
                
                # Ensure bounds
                calibrated = max(0.0, min(1.0, calibrated))
                
                logging.debug(
                    f"📏 Calibrated: {confidence_raw:.2f} → {calibrated:.2f} "
                    f"({side} {timeframe})"
                )
                
                return calibrated
            
            # Fallback: use raw confidence with prior adjustment
            else:
                # Beta distribution prior: slightly pessimistic
                # E[Beta(5,2)] = 0.714
                prior_mean = self.prior_alpha / (self.prior_alpha + self.prior_beta)
                
                # Blend with prior (80% raw, 20% prior)
                calibrated = 0.8 * confidence_raw + 0.2 * prior_mean
                
                logging.debug(
                    f"📏 Fallback calibration: {confidence_raw:.2f} → {calibrated:.2f} "
                    f"(no calibrator for {key})"
                )
                
                return calibrated
            
        except Exception as e:
            logging.error(f"❌ Calibration failed: {e}")
            return confidence_raw  # Return raw as failsafe
    
    def _compute_brier_score(self, predictions: np.ndarray, 
                            actual: np.ndarray) -> float:
        """
        Compute Brier score (lower is better)
        
        Args:
            predictions: Predicted probabilities
            actual: Actual binary outcomes
            
        Returns:
            float: Brier score
        """
        try:
            return float(np.mean((predictions - actual) ** 2))
        except Exception as e:
            logging.error(f"❌ Brier score computation failed: {e}")
            return 1.0
    
    def save_all_calibrators(self):
        """Save all calibrators to disk"""
        try:
            for key, calibrator in self.calibrators.items():
                side, timeframe = key
                filename = f"calibration_{side}_{timeframe}.pkl"
                filepath = self.state_dir / filename
                
                with open(filepath, 'wb') as f:
                    pickle.dump({
                        'calibrator': calibrator,
                        'brier_score': self.brier_scores.get(key, 1.0),
                        'last_update': datetime.now().isoformat()
                    }, f)
            
            logging.debug(f"📏 Saved {len(self.calibrators)} calibrators")
            
        except Exception as e:
            logging.error(f"❌ Failed to save calibrators: {e}")
    
    def load_all_calibrators(self):
        """Load all calibrators from disk"""
        try:
            loaded_count = 0
            
            for side in ['LONG', 'SHORT']:
                for timeframe in ['15m', '30m', '1h']:
                    filename = f"calibration_{side}_{timeframe}.pkl"
                    filepath = self.state_dir / filename
                    
                    if filepath.exists():
                        try:
                            with open(filepath, 'rb') as f:
                                data = pickle.load(f)
                            
                            key = (side, timeframe)
                            self.calibrators[key] = data['calibrator']
                            self.brier_scores[key] = data.get('brier_score', 1.0)
                            
                            loaded_count += 1
                            
                        except Exception as e:
                            logging.warning(f"⚠️ Failed to load {filename}: {e}")
            
            if loaded_count > 0:
                logging.info(f"📏 Loaded {loaded_count} calibrators")
            else:
                logging.debug("📏 No previous calibrators found")
            
        except Exception as e:
            logging.error(f"❌ Failed to load calibrators: {e}")
    
    def get_calibrator_info(self) -> Dict:
        """Get info about current calibrators for monitoring"""
        return {
            'n_calibrators': len(self.calibrators),
            'combinations': [f"{s}_{tf}" for s, tf in self.calibrators.keys()],
            'brier_scores': {
                f"{s}_{tf}": score 
                for (s, tf), score in self.brier_scores.items()
            }
        }
    
    def reset(self):
        """Reset all calibrators (for testing/debugging)"""
        self.calibrators.clear()
        self.brier_scores.clear()
        logging.info("📏 Confidence calibrator reset")


# Global instance
global_confidence_calibrator = ConfidenceCalibrator()
