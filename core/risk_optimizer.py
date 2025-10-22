#!/usr/bin/env python3
"""
💰 RISK OPTIMIZER - Adaptive Learning System

Kelly Criterion-based position sizing with variance control.

Formula:
f* = (p × R - (1-p)) / R × vol_adjustment × k_factor

Where:
- p = win probability (calibrated confidence)
- R = reward/risk ratio (historical avg_win/avg_loss)
- vol_adjustment = target_sigma / max(sigma_pnl, target_sigma)
- k_factor = conservative multiplier (0.25 for quarter-Kelly)

FEATURES:
- Variance-adjusted Kelly fractions
- Per-symbol/cluster Kelly parameters
- Dynamic risk caps
- State persistence
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Optional

class RiskOptimizer:
    """
    Kelly Criterion optimizer with variance control
    
    Calculates optimal position fractions while controlling for
    volatility spikes and maintaining safety bounds.
    """
    
    def __init__(self,
                 k_factor: float = 0.40,
                 f_max: float = 0.015,
                 target_sigma: float = 1.0,
                 min_position_usd: float = 15.0,
                 max_position_usd: float = 150.0):
        """
        Initialize risk optimizer
        
        Args:
            k_factor: Conservative multiplier (0.40 = 40% Kelly - balanced aggression)
            f_max: Maximum position fraction (1.5% of wallet)
            target_sigma: Target volatility threshold
            min_position_usd: Minimum position size in USD
            max_position_usd: Maximum position size in USD
        """
        self.k_factor = k_factor
        self.f_max = f_max
        self.target_sigma = target_sigma
        self.min_position_usd = min_position_usd
        self.max_position_usd = max_position_usd
        
        # Kelly parameters per bucket: {bucket: (R, sigma_pnl)}
        self.kelly_params: Dict[str, Tuple[float, float]] = {}
        
        # Dynamic caps
        self.daily_loss_cap: Optional[float] = None
        self.current_daily_loss: float = 0.0
        self.daily_reset_time: Optional[datetime] = None
        
        # State file
        self.state_file = Path("adaptive_state/kelly_parameters.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load previous state
        self.load_state()
        
        logging.info(f"💰 RiskOptimizer initialized (k={k_factor}, f_max={f_max*100:.0f}%)")
    
    def calculate_kelly_fraction(self, 
                                 conf_cal: float, 
                                 bucket: str = 'DEFAULT',
                                 wallet_balance: float = 1000.0) -> float:
        """
        Calculate Kelly-optimal position fraction with Bayesian p_win
        
        CRITICAL FIX: Separates ML confidence from empirical win probability
        
        Args:
            conf_cal: ML confidence (used as multiplier, NOT as p_win!)
            bucket: Symbol/cluster/timeframe bucket
            wallet_balance: Current wallet balance
            
        Returns:
            float: Position fraction (0-1) of wallet to use
        """
        try:
            from core.feedback_logger import global_feedback_logger
            
            # 1. GET EMPIRICAL WINRATE STATS (not ML confidence!)
            wins, losses, avg_win, avg_loss = global_feedback_logger.get_winrate_stats(
                bucket=bucket,
                window=100
            )
            
            # 2. BAYESIAN P_WIN with Laplace smoothing
            # This prevents overfitting on small samples
            alpha, beta = 1.0, 1.0  # Laplace prior (α=β=1)
            
            if wins + losses > 0:
                p_win_bayesian = (wins + alpha) / (wins + losses + alpha + beta)
            else:
                # No historical data - use conservative default
                p_win_bayesian = 0.45  # Slightly below 50% to be conservative
                logging.debug(f"💰 {bucket}: No trade history, using default p_win={p_win_bayesian:.2f}")
            
            # 3. DYNAMIC R from empirical payoff
            if avg_loss > 0 and avg_win > 0:
                R_empirical = avg_win / avg_loss
            else:
                R_empirical = 2.0  # Conservative fallback
            
            # Cap R to prevent extreme sizing
            R_empirical = min(R_empirical, 3.5)
            
            # 4. CLASSIC KELLY FRACTION with empirical p_win (NOT ML confidence!)
            if R_empirical > 0:
                f_kelly = (p_win_bayesian * R_empirical - (1 - p_win_bayesian)) / R_empirical
            else:
                f_kelly = 0
            
            # Ensure non-negative
            f_kelly = max(0, f_kelly)
            
            # 5. GET VOLATILITY ADJUSTMENT
            _, _, sigma_pnl = self._get_kelly_parameters(bucket)
            vol_ratio = self.target_sigma / max(sigma_pnl, self.target_sigma)
            
            # 6. USE ML CONFIDENCE AS MULTIPLIER (separate concept!)
            # This scales position by how confident the model is
            confidence_multiplier = conf_cal
            
            # 7. COMBINE ALL FACTORS
            f_adjusted = f_kelly * vol_ratio * confidence_multiplier * self.k_factor
            
            # 8. APPLY MAXIMUM CAP
            f_final = min(f_adjusted, self.f_max)
            
            # 9. CHECK DAILY LOSS CAP
            if self.daily_loss_cap and self.current_daily_loss > self.daily_loss_cap:
                f_final *= 0.5
                logging.debug(f"💰 Daily loss cap hit: halving Kelly fraction")
            
            # 10. CONVERT TO USD with taker fee buffer
            TAKER_FEE = 0.0006  # 0.06% Bybit futures
            position_usd = f_final * wallet_balance * (1 - TAKER_FEE)
            position_usd = max(self.min_position_usd, 
                             min(self.max_position_usd, position_usd))
            
            # Convert back to fraction
            f_final = position_usd / wallet_balance if wallet_balance > 0 else 0
            
            # Enhanced logging
            logging.debug(
                f"💰 Kelly {bucket}: p_win={p_win_bayesian:.3f} (W{wins}/L{losses}), "
                f"R={R_empirical:.2f}, σ={sigma_pnl:.2f}, ML_conf={conf_cal:.2f} "
                f"→ f_kelly={f_kelly:.3f} → f_adj={f_adjusted:.3f} → ${position_usd:.2f}"
            )
            
            return f_final
            
        except Exception as e:
            logging.error(f"❌ Kelly fraction calculation failed: {e}")
            # Safe fallback
            return self.min_position_usd / wallet_balance if wallet_balance > 0 else 0.01
    
    def _get_kelly_parameters(self, bucket: str) -> Tuple[float, float]:
        """
        Get Kelly parameters (R, sigma) for a bucket
        
        Args:
            bucket: Bucket identifier
            
        Returns:
            Tuple[float, float]: (R ratio, sigma_pnl)
        """
        try:
            if bucket in self.kelly_params:
                return self.kelly_params[bucket]
            
            # Fetch from feedback logger if not cached
            from core.feedback_logger import global_feedback_logger
            
            R, p, sigma_pnl = global_feedback_logger.get_kelly_parameters(bucket)
            
            # Cache for this session
            self.kelly_params[bucket] = (R, sigma_pnl)
            
            return (R, sigma_pnl)
            
        except Exception as e:
            logging.error(f"❌ Failed to get Kelly parameters for {bucket}: {e}")
            # Conservative defaults
            return (2.0, 1.0)
    
    def update_parameters(self, feedback_logger) -> Dict:
        """
        Update Kelly parameters for all active buckets
        
        Args:
            feedback_logger: FeedbackLogger instance
            
        Returns:
            Dict: Updated parameters
        """
        try:
            updates = {}
            
            # Get unique symbols/clusters from recent trades
            recent_trades = feedback_logger.get_recent_trades(n=200)
            
            buckets = set()
            for trade in recent_trades:
                buckets.add(trade.get('symbol', 'UNKNOWN'))
                buckets.add(trade.get('cluster', 'DEFAULT'))
                buckets.add(trade.get('timeframe', '15m'))
            
            # Update parameters for each bucket
            for bucket in buckets:
                if bucket in ['UNKNOWN', '']:
                    continue
                
                try:
                    R, p, sigma_pnl = feedback_logger.get_kelly_parameters(bucket, window=100)
                    
                    old_params = self.kelly_params.get(bucket, (2.0, 1.0))
                    self.kelly_params[bucket] = (R, sigma_pnl)
                    
                    # Log significant changes
                    if abs(R - old_params[0]) > 0.5 or abs(sigma_pnl - old_params[1]) > 0.3:
                        updates[bucket] = f"R: {old_params[0]:.2f}→{R:.2f}, σ: {old_params[1]:.2f}→{sigma_pnl:.2f}"
                
                except Exception as e:
                    logging.debug(f"⚠️ Failed to update parameters for {bucket}: {e}")
            
            # Update daily loss cap
            self._update_daily_loss_cap(recent_trades)
            
            # Save state
            self.save_state()
            
            if updates:
                logging.info(f"💰 Kelly parameters updated: {len(updates)} buckets")
            
            return updates
            
        except Exception as e:
            logging.error(f"❌ Kelly parameters update failed: {e}")
            return {}
    
    def _update_daily_loss_cap(self, recent_trades: list):
        """
        Update daily loss cap based on recent performance
        
        Args:
            recent_trades: List of recent trade dictionaries
        """
        try:
            # Get losses from last 10 days
            losses = []
            cutoff_date = datetime.now().timestamp() - (10 * 24 * 3600)
            
            for trade in recent_trades:
                try:
                    trade_time = datetime.fromisoformat(trade.get('timestamp', '')).timestamp()
                    if trade_time < cutoff_date:
                        continue
                    
                    pnl_usd = trade.get('pnl_usd', 0)
                    if pnl_usd < 0:
                        losses.append(abs(pnl_usd))
                
                except Exception:
                    continue
            
            if len(losses) >= 5:
                # Calculate median loss
                losses.sort()
                median_loss = losses[len(losses) // 2]
                
                # Daily loss cap = 2× median loss
                self.daily_loss_cap = 2.0 * median_loss
                
                logging.debug(f"💰 Daily loss cap updated: ${self.daily_loss_cap:.2f}")
            else:
                # Not enough data - use default
                self.daily_loss_cap = 100.0  # $100 default
            
        except Exception as e:
            logging.error(f"❌ Daily loss cap update failed: {e}")
    
    def record_trade_outcome(self, pnl_usd: float):
        """
        Record trade outcome for daily loss tracking
        
        Args:
            pnl_usd: Trade PnL in USD
        """
        try:
            # Reset daily counter if new day
            now = datetime.now()
            if self.daily_reset_time is None or now.date() > self.daily_reset_time.date():
                self.current_daily_loss = 0.0
                self.daily_reset_time = now
                logging.debug("💰 Daily loss counter reset")
            
            # Add loss to daily total
            if pnl_usd < 0:
                self.current_daily_loss += abs(pnl_usd)
                
                # Check if cap reached
                if self.daily_loss_cap and self.current_daily_loss > self.daily_loss_cap:
                    logging.warning(
                        f"⚠️ DAILY LOSS CAP REACHED: ${self.current_daily_loss:.2f} > "
                        f"${self.daily_loss_cap:.2f} - reducing position sizes"
                    )
        
        except Exception as e:
            logging.error(f"❌ Trade outcome recording failed: {e}")
    
    def get_max_fraction(self) -> float:
        """Get current maximum allowed fraction"""
        if self.daily_loss_cap and self.current_daily_loss > self.daily_loss_cap:
            return self.f_max * 0.5  # Halved if cap hit
        return self.f_max
    
    def get_kelly_info(self) -> Dict:
        """Get Kelly optimizer info for monitoring"""
        return {
            'k_factor': self.k_factor,
            'f_max': self.f_max,
            'target_sigma': self.target_sigma,
            'n_buckets': len(self.kelly_params),
            'daily_loss_cap': self.daily_loss_cap,
            'current_daily_loss': self.current_daily_loss,
            'cap_active': (self.daily_loss_cap is not None and 
                          self.current_daily_loss > self.daily_loss_cap)
        }
    
    def save_state(self):
        """Save Kelly parameters and caps to file"""
        try:
            state = {
                'kelly_params': {
                    bucket: {'R': R, 'sigma': sigma}
                    for bucket, (R, sigma) in self.kelly_params.items()
                },
                'daily_loss_cap': self.daily_loss_cap,
                'current_daily_loss': self.current_daily_loss,
                'daily_reset_time': self.daily_reset_time.isoformat() if self.daily_reset_time else None,
                'last_update': datetime.now().isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            logging.debug("💰 Risk optimizer state saved")
            
        except Exception as e:
            logging.error(f"❌ Failed to save risk optimizer state: {e}")
    
    def load_state(self):
        """Load Kelly parameters and caps from file"""
        try:
            if not self.state_file.exists():
                logging.debug("💰 No previous risk optimizer state found")
                return
            
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            # Load Kelly parameters
            kelly_params_dict = state.get('kelly_params', {})
            for bucket, params in kelly_params_dict.items():
                self.kelly_params[bucket] = (params['R'], params['sigma'])
            
            # Load caps
            self.daily_loss_cap = state.get('daily_loss_cap')
            self.current_daily_loss = state.get('current_daily_loss', 0.0)
            
            reset_time_str = state.get('daily_reset_time')
            if reset_time_str:
                self.daily_reset_time = datetime.fromisoformat(reset_time_str)
            
            # Calculate daily cap value for logging
            daily_cap_value = self.daily_loss_cap if self.daily_loss_cap is not None else 0.0
            
            logging.info(
                f"💰 Risk optimizer state loaded: {len(self.kelly_params)} buckets, "
                f"daily_cap=${daily_cap_value:.2f}"
            )
            
        except Exception as e:
            logging.error(f"❌ Failed to load risk optimizer state: {e}")
    
    def reset(self):
        """Reset Kelly parameters and caps (for testing/debugging)"""
        self.kelly_params.clear()
        self.daily_loss_cap = None
        self.current_daily_loss = 0.0
        self.daily_reset_time = None
        logging.info("💰 Risk optimizer reset")


# Global instance
global_risk_optimizer = RiskOptimizer()
