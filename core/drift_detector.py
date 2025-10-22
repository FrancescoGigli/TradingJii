#!/usr/bin/env python3
"""
📉 DRIFT DETECTOR - Adaptive Learning System

Page-Hinkley test for detecting distribution drift in trading performance.

Monitors:
- ROE per-trade (returns drift)
- Calibration error (model drift)
- Penalty scores (quality drift)

FEATURES:
- Non-parametric drift detection
- Automatic prudent mode activation
- State persistence across restarts
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

class PageHinkleyDetector:
    """
    Page-Hinkley test for change detection
    
    Detects when a time series deviates significantly from its baseline,
    triggering alerts for distribution drift.
    """
    
    def __init__(self, lambda_param: float = 0.5, delta: float = 0.02):
        """
        Initialize Page-Hinkley detector
        
        Args:
            lambda_param: Drift sensitivity (lower = more sensitive)
            delta: Alarm threshold (lower = more sensitive)
        """
        self.lambda_param = lambda_param
        self.delta = delta
        
        # Internal state
        self.sum = 0.0
        self.min_sum = 0.0
        self.drift_count = 0
        
        # History
        self.last_drift_time: Optional[datetime] = None
        
    def update(self, x: float) -> bool:
        """
        Update detector with new observation
        
        Args:
            x: New observation value
            
        Returns:
            bool: True if drift detected
        """
        try:
            # Page-Hinkley cumulative sum
            self.sum += (x - self.lambda_param)
            self.min_sum = min(self.min_sum, self.sum)
            
            # Compute drift magnitude
            drift_magnitude = self.sum - self.min_sum
            
            # Check if drift exceeds threshold
            if drift_magnitude > self.delta:
                self.drift_count += 1
                self.last_drift_time = datetime.now()
                self.reset()
                
                logging.warning(
                    f"📉 DRIFT DETECTED: magnitude={drift_magnitude:.4f} > {self.delta}"
                )
                
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"❌ Page-Hinkley update failed: {e}")
            return False
    
    def reset(self):
        """Reset detector state after drift"""
        self.sum = 0.0
        self.min_sum = 0.0
    
    def get_state(self) -> Dict:
        """Get current detector state"""
        return {
            'sum': self.sum,
            'min_sum': self.min_sum,
            'drift_count': self.drift_count,
            'last_drift_time': self.last_drift_time.isoformat() if self.last_drift_time else None
        }
    
    def set_state(self, state: Dict):
        """Restore detector state"""
        self.sum = state.get('sum', 0.0)
        self.min_sum = state.get('min_sum', 0.0)
        self.drift_count = state.get('drift_count', 0)
        
        last_drift_str = state.get('last_drift_time')
        if last_drift_str:
            self.last_drift_time = datetime.fromisoformat(last_drift_str)


class DriftDetector:
    """
    Multi-metric drift detection system
    
    Monitors multiple performance metrics for distribution changes
    and triggers prudent mode when drift is detected.
    """
    
    def __init__(self,
                 lambda_param: float = 0.5,
                 delta: float = 0.02,
                 prudent_cycles: int = 40):  # UPDATED: Default 40 (was 100)
        """
        Initialize drift detector
        
        Args:
            lambda_param: Drift sensitivity
            delta: Alarm threshold
            prudent_cycles: Cycles to stay in prudent mode after drift (default: 40 = ~10 hours)
        """
        self.lambda_param = lambda_param
        self.delta = delta
        self.prudent_cycles = prudent_cycles
        
        # Create detectors for different metrics
        self.roe_detector = PageHinkleyDetector(lambda_param, delta)
        self.calibration_detector = PageHinkleyDetector(lambda_param, delta * 0.5)  # More sensitive
        self.penalty_detector = PageHinkleyDetector(lambda_param, delta)
        
        # Prudent mode tracking
        self.prudent_mode_active = False
        self.prudent_cycles_remaining = 0
        self.drift_history = []
        
        # State file
        self.state_file = Path("adaptive_state/drift_detector_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load previous state
        self.load_state()
        
        logging.info(f"📉 DriftDetector initialized (λ={lambda_param}, δ={delta})")
    
    def update_roe(self, roe_pct: float) -> bool:
        """
        Update with new ROE observation
        
        Args:
            roe_pct: Trade ROE percentage
            
        Returns:
            bool: True if drift detected
        """
        try:
            drift_detected = self.roe_detector.update(roe_pct / 100)  # Normalize to [-1, 1]
            
            if drift_detected:
                self._handle_drift("ROE")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"❌ ROE drift update failed: {e}")
            return False
    
    def update_calibration_error(self, conf_cal: float, result: int) -> bool:
        """
        Update with calibration error
        
        Args:
            conf_cal: Calibrated confidence
            result: Actual result (1=win, 0=loss)
            
        Returns:
            bool: True if drift detected
        """
        try:
            # Calibration error = |predicted_prob - actual|
            error = abs(conf_cal - result)
            
            drift_detected = self.calibration_detector.update(error)
            
            if drift_detected:
                self._handle_drift("CALIBRATION")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"❌ Calibration drift update failed: {e}")
            return False
    
    def update_penalty(self, penalty: float) -> bool:
        """
        Update with penalty score
        
        Args:
            penalty: Computed penalty score
            
        Returns:
            bool: True if drift detected
        """
        try:
            drift_detected = self.penalty_detector.update(penalty)
            
            if drift_detected:
                self._handle_drift("PENALTY")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"❌ Penalty drift update failed: {e}")
            return False
    
    def _handle_drift(self, metric: str):
        """Handle drift detection"""
        try:
            # Activate prudent mode
            self.prudent_mode_active = True
            self.prudent_cycles_remaining = self.prudent_cycles
            
            # Log drift event
            drift_event = {
                'metric': metric,
                'timestamp': datetime.now().isoformat(),
                'prudent_cycles': self.prudent_cycles
            }
            
            self.drift_history.append(drift_event)
            
            # Keep only recent history (last 50 events)
            if len(self.drift_history) > 50:
                self.drift_history = self.drift_history[-50:]
            
            logging.warning(
                f"🌊 DRIFT DETECTED in {metric} - PRUDENT MODE activated for {self.prudent_cycles} cycles"
            )
            
            # Save state
            self.save_state()
            
        except Exception as e:
            logging.error(f"❌ Drift handling failed: {e}")
    
    def decrement_prudent_mode(self):
        """
        Decrement prudent mode counter (called each trading cycle)
        """
        try:
            if self.prudent_mode_active and self.prudent_cycles_remaining > 0:
                self.prudent_cycles_remaining -= 1
                
                if self.prudent_cycles_remaining == 0:
                    self.prudent_mode_active = False
                    logging.info("✅ PRUDENT MODE deactivated - returning to normal")
                    self.save_state()
        
        except Exception as e:
            logging.error(f"❌ Prudent mode decrement failed: {e}")
    
    def is_prudent_mode_active(self) -> bool:
        """Check if prudent mode is currently active"""
        return self.prudent_mode_active
    
    def get_prudent_adjustments(self) -> Dict:
        """
        Get parameter adjustments for prudent mode
        
        Returns:
            Dict: Adjustments to apply {'tau_adjustment': float, 'kelly_multiplier': float}
        """
        if self.prudent_mode_active:
            return {
                'tau_adjustment': 0.05,  # Raise threshold by 5%
                'kelly_multiplier': 0.5   # Halve Kelly fractions
            }
        else:
            return {
                'tau_adjustment': 0.0,
                'kelly_multiplier': 1.0
            }
    
    def check_all_metrics(self) -> bool:
        """
        Check if any detector has triggered (for periodic checks)
        
        Returns:
            bool: True if drift detected in any metric
        """
        return self.prudent_mode_active
    
    def get_drift_summary(self) -> Dict:
        """Get drift detection summary for monitoring"""
        return {
            'prudent_mode_active': self.prudent_mode_active,
            'prudent_cycles_remaining': self.prudent_cycles_remaining,
            'total_drifts_detected': sum(d.drift_count for d in [
                self.roe_detector, 
                self.calibration_detector, 
                self.penalty_detector
            ]),
            'recent_drift_events': len(self.drift_history),
            'last_drift': self.drift_history[-1] if self.drift_history else None
        }
    
    def save_state(self):
        """Save detector state to file"""
        try:
            state = {
                'roe_detector': self.roe_detector.get_state(),
                'calibration_detector': self.calibration_detector.get_state(),
                'penalty_detector': self.penalty_detector.get_state(),
                'prudent_mode_active': self.prudent_mode_active,
                'prudent_cycles_remaining': self.prudent_cycles_remaining,
                'drift_history': self.drift_history,
                'last_update': datetime.now().isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            logging.debug("📉 Drift detector state saved")
            
        except Exception as e:
            logging.error(f"❌ Failed to save drift detector state: {e}")
    
    def load_state(self):
        """Load detector state from file"""
        try:
            if not self.state_file.exists():
                logging.debug("📉 No previous drift detector state found")
                return
            
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            # Restore detectors
            self.roe_detector.set_state(state.get('roe_detector', {}))
            self.calibration_detector.set_state(state.get('calibration_detector', {}))
            self.penalty_detector.set_state(state.get('penalty_detector', {}))
            
            # Restore prudent mode
            self.prudent_mode_active = state.get('prudent_mode_active', False)
            self.prudent_cycles_remaining = state.get('prudent_cycles_remaining', 0)
            self.drift_history = state.get('drift_history', [])
            
            logging.info(
                f"📉 Drift detector state loaded: "
                f"prudent_mode={self.prudent_mode_active}, "
                f"drifts={len(self.drift_history)}"
            )
            
        except Exception as e:
            logging.error(f"❌ Failed to load drift detector state: {e}")
    
    def reset(self):
        """Reset all detectors (for testing/debugging)"""
        self.roe_detector.reset()
        self.calibration_detector.reset()
        self.penalty_detector.reset()
        self.prudent_mode_active = False
        self.prudent_cycles_remaining = 0
        self.drift_history.clear()
        logging.info("📉 Drift detector reset")


# Global instance with config-based parameters
try:
    from config import (
        ADAPTIVE_DRIFT_LAMBDA,
        ADAPTIVE_DRIFT_DELTA,
        ADAPTIVE_DRIFT_PRUDENT_CYCLES
    )
    global_drift_detector = DriftDetector(
        lambda_param=ADAPTIVE_DRIFT_LAMBDA,
        delta=ADAPTIVE_DRIFT_DELTA,
        prudent_cycles=ADAPTIVE_DRIFT_PRUDENT_CYCLES
    )
    logging.info(f"📉 DriftDetector initialized from config: prudent_cycles={ADAPTIVE_DRIFT_PRUDENT_CYCLES}")
except ImportError:
    # Fallback if config not available
    global_drift_detector = DriftDetector()
    logging.warning("⚠️ DriftDetector using default parameters (config not found)")
