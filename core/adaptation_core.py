#!/usr/bin/env python3
"""
🧠 ADAPTATION CORE - Adaptive Learning System

Main orchestrator for the adaptive learning meta-layer.
Integrates all adaptive components and provides unified API.

ARCHITECTURE:
1. Loop: Trade outcomes → Database → Analysis
2. Parameter Adaptation: Thresholds, calibration, Kelly → State files
3. Real-time Application: Filter signals, size positions, log decisions

FEATURES:
- Background async processing (non-blocking)
- Automatic adaptation every 200 trades or 12h
- State persistence across restarts
- Graceful degradation on errors
"""

import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional
from termcolor import colored

# Import all adaptive components
from core.feedback_logger import global_feedback_logger
from core.penalty_calculator import global_penalty_calculator
from core.threshold_controller import global_threshold_controller
from core.confidence_calibrator import global_confidence_calibrator
from core.drift_detector import global_drift_detector
from core.risk_optimizer import global_risk_optimizer


class AdaptationCore:
    """
    Main orchestrator for adaptive learning system
    
    Coordinates all adaptive components and provides high-level API
    for integration with trading engine.
    """
    
    def __init__(self):
        """Initialize adaptation core"""
        # Component references
        self.feedback_logger = global_feedback_logger
        self.penalty_calculator = global_penalty_calculator
        self.threshold_controller = global_threshold_controller
        self.confidence_calibrator = global_confidence_calibrator
        self.drift_detector = global_drift_detector
        self.risk_optimizer = global_risk_optimizer
        
        # Adaptation lock (prevent concurrent adaptations)
        self.adaptation_lock = asyncio.Lock()
        
        # Tracking
        self.trades_since_last_adaptation = 0
        self.last_adaptation_time = time.time()
        
        # Enabled flag
        self.enabled = True
        
        logging.info("🧠 AdaptationCore initialized")
    
    async def initialize(self):
        """
        Initialize adaptive system at bot startup
        
        Loads all previous state and displays current configuration.
        """
        try:
            logging.info(colored("🧠 ADAPTIVE LEARNING SYSTEM: Initializing...", "cyan", attrs=["bold"]))
            
            # All components auto-load their state in __init__
            # Just display current state
            
            state = self.get_current_state()
            
            logging.info(colored("🧠 ADAPTIVE SYSTEM READY", "green", attrs=["bold"]))
            logging.info(f"   📊 Global Threshold (τ): {state['tau_global']:.2f}")
            logging.info(f"   💰 Kelly Factor: {state['kelly_factor']:.2f}×")
            logging.info(f"   📈 Total Trades Learned: {state['total_trades']}")
            logging.info(f"   🎯 Calibrators Active: {state['n_calibrators']}")
            
            if state.get('prudent_mode_active'):
                logging.warning(
                    f"   🌊 PRUDENT MODE ACTIVE: "
                    f"{state['prudent_cycles_remaining']} cycles remaining"
                )
            
            # Cleanup old data
            self.feedback_logger.cleanup_old_data()
            
            return True
            
        except Exception as e:
            logging.error(f"❌ Adaptive system initialization failed: {e}")
            return False
    
    async def log_trade_outcome_async(self, trade_info: Dict):
        """
        Log trade outcome in background (non-blocking)
        
        Args:
            trade_info: Trade data dictionary
        """
        try:
            # Ensure required fields have defaults
            trade_info.setdefault('cluster', 'DEFAULT')
            trade_info.setdefault('timeframe', '15m')
            
            # 1. Compute penalty score
            penalty = self.penalty_calculator.compute(trade_info)
            trade_info['penalty_score'] = penalty
            
            # 2. Log to database
            trade_id = self.feedback_logger.log_trade_outcome(trade_info)
            
            if trade_id < 0:
                logging.warning("⚠️ Trade logging failed")
                return
            
            # 3. Update penalty EWMA
            self.penalty_calculator.update_ewma(
                trade_info['symbol'],
                trade_info['cluster'],
                penalty
            )
            
            # 4. Update drift detectors
            self.drift_detector.update_roe(trade_info['roe_pct'])
            
            if 'confidence_calibrated' in trade_info:
                self.drift_detector.update_calibration_error(
                    trade_info['confidence_calibrated'],
                    trade_info['result']
                )
            
            self.drift_detector.update_penalty(penalty)
            
            # 5. Update risk optimizer
            self.risk_optimizer.record_trade_outcome(trade_info['pnl_usd'])
            
            # 6. Increment counters
            self.trades_since_last_adaptation += 1
            self.threshold_controller.increment_trade_count()
            
            # 7. Check if should trigger adaptation
            if self._should_run_adaptation():
                # Create background task for adaptation
                asyncio.create_task(self.run_adaptation_cycle())
            
            logging.debug(f"🧠 Trade outcome logged: ID={trade_id}")
            
        except Exception as e:
            logging.error(f"❌ Trade outcome logging failed: {e}")
    
    def _should_run_adaptation(self) -> bool:
        """Check if adaptation cycle should run"""
        from config import ADAPTIVE_MIN_TRADES_FOR_UPDATE, ADAPTIVE_UPDATE_INTERVAL_HOURS
        
        # Check trades threshold
        if self.trades_since_last_adaptation >= ADAPTIVE_MIN_TRADES_FOR_UPDATE:
            return True
        
        # Check time threshold
        time_since_last = time.time() - self.last_adaptation_time
        if time_since_last >= ADAPTIVE_UPDATE_INTERVAL_HOURS * 3600:
            return True
        
        return False
    
    async def run_adaptation_cycle(self):
        """
        Main adaptation cycle - updates all parameters
        
        Runs in background, triggered automatically after sufficient trades.
        """
        async with self.adaptation_lock:
            try:
                start_time = time.time()
                
                logging.info(colored("🧠 ADAPTIVE CYCLE STARTED", "magenta", attrs=["bold"]))
                
                changes = {}
                
                # 1. Update thresholds
                logging.info("   🎚️ Updating thresholds...")
                threshold_changes = self.threshold_controller.update(self.feedback_logger)
                if threshold_changes:
                    changes['thresholds'] = threshold_changes
                
                # 2. Recalibrate confidence
                logging.info("   📏 Recalibrating confidence...")
                calibration_changes = self.confidence_calibrator.recalibrate_all(
                    self.feedback_logger
                )
                if calibration_changes:
                    changes['calibration'] = f"{len(calibration_changes)} combinations"
                
                # 3. Update Kelly parameters
                logging.info("   💰 Updating Kelly parameters...")
                kelly_changes = self.risk_optimizer.update_parameters(self.feedback_logger)
                if kelly_changes:
                    changes['kelly'] = f"{len(kelly_changes)} buckets"
                
                # 4. Update cooldowns
                logging.info("   🚫 Managing cooldowns...")
                active_cooldowns = self.penalty_calculator.update_cooldowns()
                if active_cooldowns:
                    changes['cooldowns'] = f"{len(active_cooldowns)} active"
                
                # 5. Check drift and prudent mode
                self.drift_detector.decrement_prudent_mode()
                if self.drift_detector.is_prudent_mode_active():
                    changes['prudent_mode'] = f"{self.drift_detector.prudent_cycles_remaining} cycles"
                
                # 6. Reset counters
                self.trades_since_last_adaptation = 0
                self.last_adaptation_time = time.time()
                
                elapsed = time.time() - start_time
                
                # Log summary
                logging.info(colored("🧠 ADAPTIVE CYCLE COMPLETED", "green", attrs=["bold"]))
                logging.info(f"   ⏱️ Duration: {elapsed:.1f}s")
                
                if changes:
                    for key, value in changes.items():
                        logging.info(f"   📊 {key}: {value}")
                else:
                    logging.info("   ℹ️ No parameter changes needed")
                
                return changes
                
            except Exception as e:
                logging.error(f"❌ Adaptation cycle failed: {e}")
                import traceback
                logging.error(traceback.format_exc())
                return {}
    
    def apply_adaptive_filtering(self, signals: List[Dict]) -> List[Dict]:
        """
        Apply adaptive filtering to signals
        
        1. Calibrate confidence
        2. Check cooldowns
        3. Apply multi-level thresholds
        
        Args:
            signals: List of signal dictionaries
            
        Returns:
            List[Dict]: Filtered signals with calibrated confidence
        """
        try:
            if not self.enabled:
                return signals
            
            filtered = []
            stats = {'total': len(signals), 'calibrated': 0, 'cooled': 0, 'filtered': 0}
            
            for signal in signals:
                # 1. Calibrate confidence
                conf_raw = signal.get('confidence', 0.7)
                side = signal.get('signal_name', 'BUY').upper()
                side = 'LONG' if side in ['BUY', 'LONG'] else 'SHORT'
                timeframe = signal.get('timeframe', '15m')
                
                conf_cal = self.confidence_calibrator.calibrate(conf_raw, side, timeframe)
                signal['confidence_calibrated'] = conf_cal
                signal['confidence_raw'] = conf_raw
                signal['confidence'] = conf_cal  # UPDATE: Use calibrated value for display
                stats['calibrated'] += 1
                
                # 2. Check cooldown
                symbol = signal.get('symbol', '')
                cluster = signal.get('cluster', 'DEFAULT')
                
                # DEBUG: Log cooldown check
                is_cooled = self.penalty_calculator.is_in_cooldown(symbol, cluster)
                
                if is_cooled:
                    stats['cooled'] += 1
                    logging.warning(f"🚫 {symbol} in cooldown - skipped (cluster={cluster})")
                    continue
                
                # 3. Apply multi-level threshold
                tau_eff = self.threshold_controller.get_effective_threshold(
                    side, timeframe, cluster
                )
                
                # Apply prudent mode adjustment
                if self.drift_detector.is_prudent_mode_active():
                    adjustments = self.drift_detector.get_prudent_adjustments()
                    tau_eff += adjustments['tau_adjustment']
                
                # Filter by threshold
                if conf_cal >= tau_eff:
                    filtered.append(signal)
                else:
                    stats['filtered'] += 1
                    logging.debug(
                        f"🎚️ {symbol} filtered: conf={conf_cal:.2f} < τ={tau_eff:.2f}"
                    )
            
            logging.info(
                f"🧠 Adaptive filter: {stats['total']} → {len(filtered)} signals "
                f"(calibrated={stats['calibrated']}, cooled={stats['cooled']}, "
                f"filtered={stats['filtered']})"
            )
            
            return filtered
            
        except Exception as e:
            logging.error(f"❌ Adaptive filtering failed: {e}")
            # Fallback: return original signals
            return signals
    
    def calculate_adaptive_margins(self, signals: List[Dict], 
                                  available_balance: float,
                                  risk_calculator) -> List[float]:
        """
        Calculate Kelly-optimal position margins
        
        Args:
            signals: Filtered signals (with calibrated confidence)
            available_balance: Available balance for trading
            risk_calculator: RiskCalculator instance for fallback
            
        Returns:
            List[float]: Margin amounts for each signal
        """
        try:
            if not self.enabled:
                # Fallback to standard risk calculator
                return risk_calculator.calculate_portfolio_based_margins(
                    signals, available_balance
                )
            
            margins = []
            
            # Apply prudent mode multiplier
            kelly_multiplier = 1.0
            if self.drift_detector.is_prudent_mode_active():
                adjustments = self.drift_detector.get_prudent_adjustments()
                kelly_multiplier = adjustments['kelly_multiplier']
            
            for signal in signals:
                # Get Kelly fraction
                conf_cal = signal.get('confidence_calibrated', signal.get('confidence', 0.7))
                symbol = signal.get('symbol', '')
                
                kelly_fraction = self.risk_optimizer.calculate_kelly_fraction(
                    conf_cal, symbol, available_balance
                )
                
                # Apply prudent mode adjustment
                kelly_fraction *= kelly_multiplier
                
                # Calculate margin
                margin = kelly_fraction * available_balance
                
                # Apply bounds
                from config import POSITION_SIZE_MIN_ABSOLUTE, POSITION_SIZE_MAX_ABSOLUTE
                margin = max(POSITION_SIZE_MIN_ABSOLUTE, 
                           min(POSITION_SIZE_MAX_ABSOLUTE, margin))
                
                margins.append(margin)
            
            total_margin = sum(margins)
            utilization = (total_margin / available_balance * 100) if available_balance > 0 else 0
            
            logging.info(
                f"💰 Kelly-based margins: {len(margins)} positions, "
                f"${total_margin:.2f} total ({utilization:.1f}% utilization)"
            )
            
            return margins
            
        except Exception as e:
            logging.error(f"❌ Kelly margin calculation failed: {e}")
            # Fallback to standard calculator
            return risk_calculator.calculate_portfolio_based_margins(
                signals, available_balance
            )
    
    def get_current_state(self) -> Dict:
        """Get current adaptive system state for monitoring"""
        try:
            thresholds = self.threshold_controller.get_all_thresholds()
            kelly_info = self.risk_optimizer.get_kelly_info()
            drift_summary = self.drift_detector.get_drift_summary()
            calibrator_info = self.confidence_calibrator.get_calibrator_info()
            
            # Get active cooldowns
            cooldowns = []
            for symbol in list(self.penalty_calculator.symbol_cooldowns.keys())[:5]:
                cooldowns.append(symbol)
            
            return {
                # Thresholds
                'tau_global': thresholds['tau_global'],
                'tau_side': thresholds['tau_side'],
                'tau_tf': thresholds['tau_tf'],
                'trades_since_update': thresholds['trades_since_update'],
                
                # KellydK
                'kelly_factor': kelly_info['k_factor'],
                'kelly_max_fraction': kelly_info['f_max'],
                'kelly_buckets': kelly_info['n_buckets'],
                'daily_cap_active': kelly_info['cap_active'],
                
                # Drift
                'prudent_mode_active': drift_summary['prudent_mode_active'],
                'prudent_cycles_remaining': drift_summary['prudent_cycles_remaining'],
                'total_drifts': drift_summary['total_drifts_detected'],
                
                # Calibration
                'n_calibrators': calibrator_info['n_calibrators'],
                
                # Performance
                'total_trades': self.feedback_logger.count_total_trades(),
                'trades_since_adaptation': self.trades_since_last_adaptation,
                
                # Cooldowns
                'active_cooldowns': cooldowns,
                
                # Meta
                'last_adaptation': datetime.fromtimestamp(self.last_adaptation_time).isoformat(),
                'enabled': self.enabled
            }
            
        except Exception as e:
            logging.error(f"❌ Failed to get adaptive state: {e}")
            return {'enabled': False, 'error': str(e)}
    
    def get_recent_performance(self, window: int = 100) -> Dict:
        """Get recent performance statistics"""
        try:
            stats = self.feedback_logger.get_statistics(window=window)
            
            return {
                'total_trades': stats.total_trades,
                'win_rate': stats.win_rate,
                'avg_roe': stats.avg_roe,
                'avg_win': stats.avg_win,
                'avg_loss': stats.avg_loss,
                'profit_factor': stats.profit_factor,
                'reward_risk_ratio': stats.reward_risk_ratio
            }
            
        except Exception as e:
            logging.error(f"❌ Failed to get recent performance: {e}")
            return {}
    
    def disable(self):
        """Disable adaptive system (fallback to static parameters)"""
        self.enabled = False
        logging.warning("⚠️ Adaptive Learning System DISABLED")
    
    def enable(self):
        """Enable adaptive system"""
        self.enabled = True
        logging.info("✅ Adaptive Learning System ENABLED")


# Global instance
global_adaptation_core = AdaptationCore()
