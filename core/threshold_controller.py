#!/usr/bin/env python3
"""
🎚️ THRESHOLD CONTROLLER - Adaptive Learning System

Multi-level adaptive threshold system (τ) to maintain optimal win rate.

HIERARCHY:
τ_effective = max(τ_global, τ_side, τ_tf, τ_cluster)

TARGETS:
- Global: 70-80% win rate
- Side-specific: 65-82% per side
- Timeframe-specific: 68-80% per TF
- Cluster-specific: Penalty-driven adjustments

FEATURES:
- Automatic threshold adjustment every 200 trades
- Minimum sample requirements per bucket
- State persistence across restarts
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple

class ThresholdController:
    """
    Multi-level adaptive threshold controller
    
    Maintains separate thresholds for global, side, timeframe, and cluster
    to optimize performance across different trading contexts.
    """
    
    def __init__(self,
                 tau_global_init: float = 0.70,
                 tau_side_init: Optional[Dict[str, float]] = None,
                 tau_tf_init: Optional[Dict[str, float]] = None,
                 tau_min: float = 0.60,
                 tau_max: float = 0.85,
                 min_trades_for_update: int = 200,
                 min_trades_per_bucket: int = 50):
        """
        Initialize threshold controller
        
        Args:
            tau_global_init: Initial global threshold
            tau_side_init: Initial side-specific thresholds
            tau_tf_init: Initial timeframe-specific thresholds
            tau_min: Minimum allowed threshold
            tau_max: Maximum allowed threshold
            min_trades_for_update: Minimum trades before updating
            min_trades_per_bucket: Minimum trades per bucket for update
        """
        # Threshold bounds
        self.tau_min = tau_min
        self.tau_max = tau_max
        
        # Update parameters
        self.min_trades_for_update = min_trades_for_update
        self.min_trades_per_bucket = min_trades_per_bucket
        
        # Thresholds (will be loaded from state or use defaults)
        self.tau_global = tau_global_init
        self.tau_side = tau_side_init or {'LONG': 0.70, 'SHORT': 0.72}
        self.tau_tf = tau_tf_init or {'15m': 0.70, '30m': 0.71, '1h': 0.71}
        self.tau_cluster: Dict[str, float] = {}
        
        # Update tracking
        self.trades_since_update = 0
        self.last_update_time = datetime.now()
        
        # State file
        self.state_file = Path("adaptive_state/threshold_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load previous state
        self.load_state()
        
        logging.info(f"🎚️ ThresholdController initialized: τ_global={self.tau_global:.2f}")
    
    def update(self, feedback_logger):
        """
        Update all thresholds based on recent performance
        
        Args:
            feedback_logger: FeedbackLogger instance for statistics
        """
        try:
            from core.feedback_logger import TradeStatistics
            
            logging.info("🎚️ UPDATING THRESHOLDS...")
            
            changes = {}
            
            # 1. Update global threshold
            old_global = self.tau_global
            self._update_global_threshold(feedback_logger)
            if self.tau_global != old_global:
                changes['tau_global'] = f"{old_global:.2f} → {self.tau_global:.2f}"
            
            # 2. Update side-specific thresholds
            side_changes = self._update_side_thresholds(feedback_logger)
            if side_changes:
                changes['tau_side'] = side_changes
            
            # 3. Update timeframe-specific thresholds
            tf_changes = self._update_timeframe_thresholds(feedback_logger)
            if tf_changes:
                changes['tau_tf'] = tf_changes
            
            # 4. Update cluster thresholds (penalty-driven)
            cluster_changes = self._update_cluster_thresholds()
            if cluster_changes:
                changes['tau_cluster'] = cluster_changes
            
            # Reset update counter
            self.trades_since_update = 0
            self.last_update_time = datetime.now()
            
            # Save state
            self.save_state()
            
            # Log changes
            if changes:
                logging.info("🎚️ Threshold updates:")
                for key, value in changes.items():
                    logging.info(f"   {key}: {value}")
            else:
                logging.info("🎚️ No threshold changes needed")
            
            return changes
            
        except Exception as e:
            logging.error(f"❌ Threshold update failed: {e}")
            return {}
    
    def _update_global_threshold(self, feedback_logger):
        """Update global threshold targeting 70-80% win rate"""
        try:
            # Get recent statistics
            stats = feedback_logger.get_statistics(
                window=self.min_trades_for_update
            )
            
            if stats.total_trades < self.min_trades_for_update:
                logging.debug(f"⚠️ Insufficient trades for global update: {stats.total_trades}")
                return
            
            win_rate = stats.win_rate
            
            # Target: 70-80% win rate
            if win_rate < 0.70:
                # Too many losses - raise threshold (be more selective)
                self.tau_global += 0.02
                logging.info(f"🎚️ Global τ raised: WR={win_rate:.1%} < 70%")
            elif win_rate > 0.80:
                # Too many wins - lower threshold (be more aggressive)
                self.tau_global -= 0.01
                logging.info(f"🎚️ Global τ lowered: WR={win_rate:.1%} > 80%")
            
            # Apply bounds
            self.tau_global = max(self.tau_min, min(self.tau_max, self.tau_global))
            
        except Exception as e:
            logging.error(f"❌ Global threshold update failed: {e}")
    
    def _update_side_thresholds(self, feedback_logger) -> Dict:
        """Update side-specific thresholds"""
        try:
            changes = {}
            
            for side in ['LONG', 'SHORT']:
                # Get side-specific statistics
                stats = feedback_logger.get_statistics(
                    window=self.min_trades_for_update,
                    filters={'side': side}
                )
                
                if stats.total_trades < self.min_trades_per_bucket:
                    logging.debug(f"⚠️ Insufficient trades for {side} update: {stats.total_trades}")
                    continue
                
                old_tau = self.tau_side.get(side, self.tau_global)
                win_rate = stats.win_rate
                
                # Target: 65-82% per side
                if win_rate < 0.65:
                    self.tau_side[side] = old_tau + 0.03
                    changes[side] = f"{old_tau:.2f} → {self.tau_side[side]:.2f} (WR={win_rate:.1%})"
                elif win_rate > 0.82:
                    self.tau_side[side] = old_tau - 0.02
                    changes[side] = f"{old_tau:.2f} → {self.tau_side[side]:.2f} (WR={win_rate:.1%})"
                
                # Apply bounds
                self.tau_side[side] = max(self.tau_min, min(self.tau_max, self.tau_side[side]))
            
            return changes
            
        except Exception as e:
            logging.error(f"❌ Side threshold update failed: {e}")
            return {}
    
    def _update_timeframe_thresholds(self, feedback_logger) -> Dict:
        """Update timeframe-specific thresholds"""
        try:
            changes = {}
            
            for tf in ['15m', '30m', '1h']:
                # Get timeframe-specific statistics
                stats = feedback_logger.get_statistics(
                    window=self.min_trades_for_update,
                    filters={'timeframe': tf}
                )
                
                if stats.total_trades < self.min_trades_per_bucket:
                    logging.debug(f"⚠️ Insufficient trades for {tf} update: {stats.total_trades}")
                    continue
                
                old_tau = self.tau_tf.get(tf, self.tau_global)
                win_rate = stats.win_rate
                
                # Target: 68-80% per timeframe
                if win_rate < 0.68:
                    self.tau_tf[tf] = old_tau + 0.02
                    changes[tf] = f"{old_tau:.2f} → {self.tau_tf[tf]:.2f} (WR={win_rate:.1%})"
                elif win_rate > 0.80:
                    self.tau_tf[tf] = old_tau - 0.01
                    changes[tf] = f"{old_tau:.2f} → {self.tau_tf[tf]:.2f} (WR={win_rate:.1%})"
                
                # Apply bounds
                self.tau_tf[tf] = max(self.tau_min, min(self.tau_max, self.tau_tf[tf]))
            
            return changes
            
        except Exception as e:
            logging.error(f"❌ Timeframe threshold update failed: {e}")
            return {}
    
    def _update_cluster_thresholds(self) -> Dict:
        """Update cluster thresholds based on penalty scores"""
        try:
            from core.penalty_calculator import global_penalty_calculator
            
            changes = {}
            
            # Get all clusters with penalties
            for cluster, penalty in global_penalty_calculator.cluster_penalty_ewma.items():
                old_tau = self.tau_cluster.get(cluster, self.tau_global)
                
                # High penalty -> raise threshold
                if penalty > 1.5:
                    self.tau_cluster[cluster] = min(self.tau_max, old_tau + 0.05)
                    changes[cluster] = f"{old_tau:.2f} → {self.tau_cluster[cluster]:.2f} (penalty={penalty:.2f})"
                
                # Low penalty -> lower threshold
                elif penalty < 0.8:
                    self.tau_cluster[cluster] = max(self.tau_global, old_tau - 0.02)
                    if self.tau_cluster[cluster] != old_tau:
                        changes[cluster] = f"{old_tau:.2f} → {self.tau_cluster[cluster]:.2f} (penalty={penalty:.2f})"
            
            return changes
            
        except Exception as e:
            logging.error(f"❌ Cluster threshold update failed: {e}")
            return {}
    
    def get_effective_threshold(self, side: str, timeframe: str, cluster: str = 'DEFAULT') -> float:
        """
        Get effective threshold for a signal (max of all applicable thresholds)
        
        Args:
            side: Position side (LONG/SHORT)
            timeframe: Timeframe
            cluster: Symbol cluster
            
        Returns:
            float: Effective threshold to apply
        """
        try:
            thresholds = [
                self.tau_global,
                self.tau_side.get(side, self.tau_global),
                self.tau_tf.get(timeframe, self.tau_global),
                self.tau_cluster.get(cluster, self.tau_global)
            ]
            
            effective = max(thresholds)
            
            logging.debug(
                f"🎚️ Effective τ for {side} {timeframe} {cluster}: {effective:.2f} "
                f"(global={self.tau_global:.2f}, side={self.tau_side.get(side, 0):.2f}, "
                f"tf={self.tau_tf.get(timeframe, 0):.2f}, cluster={self.tau_cluster.get(cluster, 0):.2f})"
            )
            
            return effective
            
        except Exception as e:
            logging.error(f"❌ Failed to get effective threshold: {e}")
            return self.tau_global
    
    def get_global_threshold(self) -> float:
        """Get current global threshold"""
        return self.tau_global
    
    def increment_trade_count(self):
        """Increment trade counter (called after each trade)"""
        self.trades_since_update += 1
    
    def should_update(self) -> bool:
        """Check if thresholds should be updated"""
        # Update every min_trades_for_update trades or every 12 hours
        time_since_update = (datetime.now() - self.last_update_time).total_seconds()
        
        return (
            self.trades_since_update >= self.min_trades_for_update or
            time_since_update >= 12 * 3600
        )
    
    def save_state(self):
        """Save threshold state to file"""
        try:
            state = {
                'tau_global': self.tau_global,
                'tau_side': self.tau_side,
                'tau_tf': self.tau_tf,
                'tau_cluster': self.tau_cluster,
                'trades_since_update': self.trades_since_update,
                'last_update_time': self.last_update_time.isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            logging.debug("🎚️ Threshold state saved")
            
        except Exception as e:
            logging.error(f"❌ Failed to save threshold state: {e}")
    
    def load_state(self):
        """Load threshold state from file"""
        try:
            if not self.state_file.exists():
                logging.debug("🎚️ No previous threshold state found")
                return
            
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            self.tau_global = state.get('tau_global', self.tau_global)
            self.tau_side = state.get('tau_side', self.tau_side)
            self.tau_tf = state.get('tau_tf', self.tau_tf)
            self.tau_cluster = state.get('tau_cluster', {})
            self.trades_since_update = state.get('trades_since_update', 0)
            
            last_update_str = state.get('last_update_time')
            if last_update_str:
                self.last_update_time = datetime.fromisoformat(last_update_str)
            
            logging.info(
                f"🎚️ Threshold state loaded: τ_global={self.tau_global:.2f}, "
                f"{self.trades_since_update} trades since last update"
            )
            
        except Exception as e:
            logging.error(f"❌ Failed to load threshold state: {e}")
    
    def get_all_thresholds(self) -> Dict:
        """Get all current thresholds for monitoring"""
        return {
            'tau_global': self.tau_global,
            'tau_side': self.tau_side.copy(),
            'tau_tf': self.tau_tf.copy(),
            'tau_cluster': self.tau_cluster.copy(),
            'trades_since_update': self.trades_since_update
        }
    
    def reset(self):
        """Reset to initial thresholds (for testing/debugging)"""
        self.tau_global = 0.70
        self.tau_side = {'LONG': 0.70, 'SHORT': 0.72}
        self.tau_tf = {'15m': 0.70, '30m': 0.71, '1h': 0.71}
        self.tau_cluster = {}
        self.trades_since_update = 0
        logging.info("🎚️ Threshold controller reset")


# Global instance
global_threshold_controller = ThresholdController()
