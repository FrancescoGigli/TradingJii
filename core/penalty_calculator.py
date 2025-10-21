#!/usr/bin/env python3
"""
⚖️ PENALTY CALCULATOR - Adaptive Learning System

Weighted error scoring system that penalizes mistakes based on:
- High confidence errors (costly mistakes)
- Stop loss hits (capital protection failures)
- Fast exits (poor entry timing)
- Large adverse excursions (price action analysis)

FEATURES:
- EWMA tracking per symbol and cluster
- Automatic cooldown management
- Penalty-driven threshold adjustment
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

class PenaltyCalculator:
    """
    Error weighting and cooldown system
    
    Tracks penalty scores to identify underperforming symbols/clusters
    and applies cooldowns to prevent repeated mistakes.
    """
    
    def __init__(self, 
                 w_conf: float = 1.0,
                 w_sl: float = 1.5,
                 w_fast: float = 0.5,
                 w_mae: float = 0.3,
                 cooldown_threshold: float = 1.2,
                 cooldown_cycles: int = 3,
                 ewma_alpha: float = 0.15):
        """
        Initialize penalty calculator
        
        Args:
            w_conf: Weight for confidence errors
            w_sl: Weight for stop loss hits
            w_fast: Weight for fast exits
            w_mae: Weight for adverse excursions
            cooldown_threshold: Penalty EWMA threshold for cooldown
            cooldown_cycles: Number of cycles to cooldown
            ewma_alpha: EWMA decay factor
        """
        # Penalty weights
        self.w_conf = w_conf
        self.w_sl = w_sl
        self.w_fast = w_fast
        self.w_mae = w_mae
        
        # Cooldown parameters
        self.cooldown_threshold = cooldown_threshold
        self.cooldown_cycles = cooldown_cycles
        
        # EWMA tracking
        self.ewma_alpha = ewma_alpha
        self.symbol_penalty_ewma: Dict[str, float] = {}
        self.cluster_penalty_ewma: Dict[str, float] = {}
        
        # Cooldown management
        self.symbol_cooldowns: Dict[str, int] = {}  # symbol -> cycles_remaining
        self.cluster_cooldowns: Dict[str, int] = {}
        
        # State file
        self.state_file = Path("adaptive_state/penalty_ewma.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load previous state
        self.load_state()
        
        logging.info("⚖️ PenaltyCalculator initialized")
    
    def compute(self, trade_info: Dict) -> float:
        """
        Compute penalty score for a trade
        
        Formula:
        penalty = w_conf * (conf_cal)^2 + 
                  w_sl * I(stop_hit) + 
                  w_fast * I(duration<300s) +
                  w_mae * (mae_bp / 100)
        
        Args:
            trade_info: Trade data dictionary
            
        Returns:
            float: Penalty score (higher = worse)
        """
        try:
            penalty = 0.0
            
            # 1. Confidence penalty (squared for high confidence errors)
            conf_cal = trade_info.get('confidence_calibrated', 
                                     trade_info.get('confidence_raw', 0.7))
            
            # Only penalize if trade was a loss
            if trade_info.get('result', 0) == 0:
                penalty += self.w_conf * (conf_cal ** 2)
            
            # 2. Stop loss penalty
            if trade_info.get('stop_hit', 0) == 1:
                penalty += self.w_sl
            
            # 3. Fast exit penalty (< 5 minutes)
            duration_s = trade_info.get('duration_seconds', 600)
            if duration_s < 300:  # 5 minutes
                penalty += self.w_fast
            
            # 4. Max adverse excursion penalty
            mae_bp = abs(trade_info.get('mae_bp', 0))
            penalty += self.w_mae * (mae_bp / 100)
            
            logging.debug(f"⚖️ Penalty computed: {penalty:.2f} for {trade_info.get('symbol')}")
            
            return penalty
            
        except Exception as e:
            logging.error(f"❌ Penalty computation failed: {e}")
            return 0.0
    
    def update_ewma(self, symbol: str, cluster: str, penalty: float):
        """
        Update EWMA trackers for symbol and cluster
        
        Args:
            symbol: Trading symbol
            cluster: Symbol cluster (L1, MEME, etc.)
            penalty: Computed penalty score
        """
        try:
            # Update symbol EWMA
            if symbol not in self.symbol_penalty_ewma:
                self.symbol_penalty_ewma[symbol] = penalty
            else:
                old_ewma = self.symbol_penalty_ewma[symbol]
                self.symbol_penalty_ewma[symbol] = (
                    self.ewma_alpha * penalty + 
                    (1 - self.ewma_alpha) * old_ewma
                )
            
            # Update cluster EWMA
            if cluster not in self.cluster_penalty_ewma:
                self.cluster_penalty_ewma[cluster] = penalty
            else:
                old_ewma = self.cluster_penalty_ewma[cluster]
                self.cluster_penalty_ewma[cluster] = (
                    self.ewma_alpha * penalty + 
                    (1 - self.ewma_alpha) * old_ewma
                )
            
            # Check for cooldown triggers
            self._check_cooldown_triggers(symbol, cluster)
            
            logging.debug(
                f"⚖️ EWMA updated: {symbol}={self.symbol_penalty_ewma[symbol]:.2f}, "
                f"{cluster}={self.cluster_penalty_ewma[cluster]:.2f}"
            )
            
        except Exception as e:
            logging.error(f"❌ EWMA update failed: {e}")
    
    def _check_cooldown_triggers(self, symbol: str, cluster: str):
        """Check if cooldowns should be triggered"""
        try:
            # Symbol cooldown trigger
            if symbol in self.symbol_penalty_ewma:
                if self.symbol_penalty_ewma[symbol] > self.cooldown_threshold:
                    if symbol not in self.symbol_cooldowns or self.symbol_cooldowns[symbol] == 0:
                        self.symbol_cooldowns[symbol] = self.cooldown_cycles
                        logging.warning(
                            f"🚫 COOLDOWN TRIGGERED: {symbol} "
                            f"(penalty={self.symbol_penalty_ewma[symbol]:.2f} > {self.cooldown_threshold})"
                        )
            
            # Cluster cooldown trigger (optional, more conservative)
            if cluster in self.cluster_penalty_ewma:
                if self.cluster_penalty_ewma[cluster] > self.cooldown_threshold * 1.25:
                    if cluster not in self.cluster_cooldowns or self.cluster_cooldowns[cluster] == 0:
                        self.cluster_cooldowns[cluster] = self.cooldown_cycles
                        logging.warning(
                            f"🚫 COOLDOWN TRIGGERED: Cluster {cluster} "
                            f"(penalty={self.cluster_penalty_ewma[cluster]:.2f})"
                        )
        
        except Exception as e:
            logging.error(f"❌ Cooldown trigger check failed: {e}")
    
    def is_in_cooldown(self, symbol: str, cluster: str = None) -> bool:
        """
        Check if symbol or cluster is in cooldown
        
        Args:
            symbol: Trading symbol
            cluster: Optional cluster to check
            
        Returns:
            bool: True if should skip (in cooldown)
        """
        try:
            # Check symbol cooldown
            if symbol in self.symbol_cooldowns:
                if self.symbol_cooldowns[symbol] > 0:
                    return True
            
            # Check cluster cooldown
            if cluster and cluster in self.cluster_cooldowns:
                if self.cluster_cooldowns[cluster] > 0:
                    return True
            
            return False
            
        except Exception as e:
            logging.error(f"❌ Cooldown check failed: {e}")
            return False
    
    def decrement_cooldowns(self):
        """
        Decrement all active cooldowns (called each trading cycle)
        """
        try:
            # Decrement symbol cooldowns
            for symbol in list(self.symbol_cooldowns.keys()):
                if self.symbol_cooldowns[symbol] > 0:
                    self.symbol_cooldowns[symbol] -= 1
                    
                    if self.symbol_cooldowns[symbol] == 0:
                        logging.info(f"✅ COOLDOWN EXPIRED: {symbol}")
                        del self.symbol_cooldowns[symbol]
            
            # Decrement cluster cooldowns
            for cluster in list(self.cluster_cooldowns.keys()):
                if self.cluster_cooldowns[cluster] > 0:
                    self.cluster_cooldowns[cluster] -= 1
                    
                    if self.cluster_cooldowns[cluster] == 0:
                        logging.info(f"✅ COOLDOWN EXPIRED: Cluster {cluster}")
                        del self.cluster_cooldowns[cluster]
        
        except Exception as e:
            logging.error(f"❌ Cooldown decrement failed: {e}")
    
    def update_cooldowns(self) -> List[str]:
        """
        Update cooldown system and return currently active cooldowns
        
        Returns:
            List[str]: List of symbols/clusters in cooldown
        """
        try:
            self.decrement_cooldowns()
            
            # Return active cooldowns
            active = []
            active.extend([f"Symbol:{s}" for s in self.symbol_cooldowns.keys()])
            active.extend([f"Cluster:{c}" for c in self.cluster_cooldowns.keys()])
            
            return active
            
        except Exception as e:
            logging.error(f"❌ Cooldown update failed: {e}")
            return []
    
    def get_symbol_penalty(self, symbol: str) -> float:
        """Get current penalty EWMA for symbol"""
        return self.symbol_penalty_ewma.get(symbol, 0.0)
    
    def get_cluster_penalty(self, cluster: str) -> float:
        """Get current penalty EWMA for cluster"""
        return self.cluster_penalty_ewma.get(cluster, 0.0)
    
    def get_top_penalties(self, n: int = 10) -> List[tuple]:
        """
        Get top N symbols with highest penalties
        
        Returns:
            List of (symbol, penalty) tuples
        """
        try:
            sorted_penalties = sorted(
                self.symbol_penalty_ewma.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            return sorted_penalties[:n]
            
        except Exception as e:
            logging.error(f"❌ Failed to get top penalties: {e}")
            return []
    
    def save_state(self):
        """Save EWMA state and cooldowns to file"""
        try:
            state = {
                'symbol_penalty_ewma': self.symbol_penalty_ewma,
                'cluster_penalty_ewma': self.cluster_penalty_ewma,
                'symbol_cooldowns': self.symbol_cooldowns,
                'cluster_cooldowns': self.cluster_cooldowns,
                'last_update': datetime.now().isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            logging.debug("⚖️ Penalty state saved")
            
        except Exception as e:
            logging.error(f"❌ Failed to save penalty state: {e}")
    
    def load_state(self):
        """Load EWMA state and cooldowns from file"""
        try:
            if not self.state_file.exists():
                logging.debug("⚖️ No previous penalty state found")
                return
            
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            self.symbol_penalty_ewma = state.get('symbol_penalty_ewma', {})
            self.cluster_penalty_ewma = state.get('cluster_penalty_ewma', {})
            self.symbol_cooldowns = state.get('symbol_cooldowns', {})
            self.cluster_cooldowns = state.get('cluster_cooldowns', {})
            
            logging.info(
                f"⚖️ Penalty state loaded: {len(self.symbol_penalty_ewma)} symbols, "
                f"{len(self.symbol_cooldowns)} active cooldowns"
            )
            
        except Exception as e:
            logging.error(f"❌ Failed to load penalty state: {e}")
    
    def reset(self):
        """Reset all penalty tracking (for testing/debugging)"""
        self.symbol_penalty_ewma.clear()
        self.cluster_penalty_ewma.clear()
        self.symbol_cooldowns.clear()
        self.cluster_cooldowns.clear()
        logging.info("⚖️ Penalty calculator reset")


# Global instance
global_penalty_calculator = PenaltyCalculator()
