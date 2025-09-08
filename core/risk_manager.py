"""
Advanced Risk Management System for Trading Bot

CRITICAL FIXES V2:
- Thread-safe singleton implementation
- Atomic operations for balance updates
- Improved synchronization with position tracker
- Dynamic stop loss based on ATR
- Volatility-based position sizing  
- Portfolio correlation limits
- Drawdown protection
- Maximum exposure controls
"""

import logging
import numpy as np
import threading
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
import pandas as pd
from contextlib import contextmanager

from config import MARGIN_USDT, LEVERAGE


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PositionRisk:
    """Risk assessment for a single position"""
    symbol: str
    side: str  # "Buy" or "Sell"
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_level: RiskLevel = RiskLevel.LOW
    max_loss_usd: float = 0.0
    

@dataclass
class PortfolioRisk:
    """Portfolio-level risk metrics"""
    total_exposure: float
    total_unrealized_pnl: float
    max_drawdown: float
    open_positions: int
    correlation_risk: float
    overall_risk_level: RiskLevel


class RobustRiskManager:
    """
    Thread-safe singleton Advanced Risk Management System
    
    CRITICAL FIXES V2:
    - Singleton pattern to ensure single instance
    - Thread-safe operations with locks
    - Atomic balance updates
    - Improved synchronization with PositionTracker
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Thread-safe singleton implementation"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Avoid re-initialization of singleton
        if hasattr(self, '_initialized'):
            return
            
        # Thread-safe locks for critical operations
        self._balance_lock = threading.RLock()  # Reentrant lock for balance operations
        self._position_lock = threading.RLock()  # Lock for position operations
        self._sync_lock = threading.Lock()  # Lock for synchronization operations
        
        # Risk parameters
        self.max_portfolio_risk = 0.02  # 2% max portfolio risk
        self.max_single_position_risk = 0.005  # 0.5% max risk per trade
        self.max_open_positions = 3
        self.max_correlation = 0.7  # Max correlation between positions
        self.max_daily_loss = 0.05  # 5% max daily loss
        self.atr_stop_multiplier = 2.0  # Stop loss = 2x ATR
        self.max_leverage = 10
        self.emergency_stop_loss = 0.10  # 10% emergency stop
        
        # Portfolio tracking with thread-safe operations
        self.daily_pnl = 0.0
        self.peak_balance = None
        self.current_drawdown = 0.0
        self._position_tracker = None
        self._last_sync_time = 0.0  # Track last synchronization
        
        # Mark as initialized
        self._initialized = True
        
        logging.debug("🔒 Thread-safe RobustRiskManager singleton initialized")
    
    @contextmanager
    def _atomic_balance_operation(self):
        """Context manager for atomic balance operations"""
        with self._balance_lock:
            try:
                yield
            except Exception as e:
                logging.error(f"Atomic balance operation failed: {e}")
                raise
    
    @contextmanager
    def _atomic_position_operation(self):
        """Context manager for atomic position operations"""
        with self._position_lock:
            try:
                yield
            except Exception as e:
                logging.error(f"Atomic position operation failed: {e}")
                raise
        
    
    def sync_with_position_tracker(self, force_sync: bool = False) -> bool:
        """
        CRITICAL FIX V2: Thread-safe sync with PositionTracker
        
        Args:
            force_sync: Force synchronization even if recently synced
            
        Returns:
            bool: True if sync successful, False otherwise
        """
        import time
        
        with self._sync_lock:
            try:
                # Avoid excessive sync calls (max once per second unless forced)
                current_time = time.time()
                if not force_sync and (current_time - self._last_sync_time) < 1.0:
                    return self._position_tracker is not None
                
                # Import and connect to position tracker
                from core.position_tracker import global_position_tracker
                self._position_tracker = global_position_tracker
                
                # Thread-safe balance synchronization
                with self._atomic_balance_operation():
                    if self._position_tracker and hasattr(self._position_tracker, 'session_stats'):
                        current_balance = self._position_tracker.session_stats['current_balance']
                        initial_balance = self._position_tracker.session_stats['initial_balance']
                        
                        # Initialize peak balance if needed
                        if self.peak_balance is None:
                            self.peak_balance = initial_balance
                            
                        # Update peak balance atomically
                        if current_balance > self.peak_balance:
                            self.peak_balance = current_balance
                            
                        # Update drawdown
                        if self.peak_balance > 0:
                            self.current_drawdown = max(0, (self.peak_balance - current_balance) / self.peak_balance)
                        
                        # Update sync timestamp
                        self._last_sync_time = current_time
                        
                        logging.debug(f"🔗 Risk Manager synced: Current={current_balance:.2f}, Peak={self.peak_balance:.2f}, DD={self.current_drawdown*100:.1f}%")
                        return True
                    else:
                        logging.warning("PositionTracker not available or invalid")
                        return False
                        
            except Exception as e:
                logging.error(f"Critical: Risk Manager sync failed: {e}")
                # Emergency fallback
                with self._atomic_balance_operation():
                    if self.peak_balance is None:
                        from config import DEMO_BALANCE
                        self.peak_balance = DEMO_BALANCE
                return False
    
    def get_current_balance(self) -> float:
        """Thread-safe balance retrieval with automatic sync"""
        with self._atomic_balance_operation():
            try:
                # Ensure we have a recent sync
                if not self.sync_with_position_tracker():
                    # Fallback to demo balance
                    from config import DEMO_BALANCE
                    logging.debug(f"Using fallback balance: {DEMO_BALANCE}")
                    return DEMO_BALANCE
                
                # Get balance from synced position tracker
                if self._position_tracker and hasattr(self._position_tracker, 'session_stats'):
                    balance = self._position_tracker.session_stats['current_balance']
                    return balance
                else:
                    from config import DEMO_BALANCE
                    return DEMO_BALANCE
                    
            except Exception as e:
                logging.error(f"Critical: Balance retrieval failed: {e}")
                from config import DEMO_BALANCE
                return DEMO_BALANCE
    
    def force_sync(self) -> bool:
        """Force immediate synchronization with position tracker"""
        return self.sync_with_position_tracker(force_sync=True)
    
    def calculate_position_size(self, 
                              symbol: str,
                              signal_strength: float,
                              current_price: float,
                              atr: float,
                              account_balance: float,
                              volatility: float = None) -> Tuple[float, float]:
        """
        ENHANCED: Dynamic Position Sizing with 20-50 USD range based on risk indicators
        
        Returns:
            (position_size, stop_loss_price)
        """
        try:
            # 1. Input validation
            if atr <= 0 or current_price <= 0:
                logging.error(f"Invalid ATR ({atr}) or price ({current_price}) for {symbol}")
                return 0.0, 0.0
            
            # 2. Calculate ATR percentage for volatility assessment
            atr_pct = (atr / current_price) * 100
            
            # 3. DYNAMIC MARGIN CALCULATION (20-50 USD range)
            dynamic_margin = self._calculate_dynamic_margin(
                atr_pct=atr_pct,
                volatility=volatility or 0.0,
                signal_strength=signal_strength,
                account_balance=account_balance
            )
            
            # 4. Calculate stop loss distance (ATR-based)
            stop_distance = atr * self.atr_stop_multiplier
            stop_loss_pct = stop_distance / current_price
            
            # Ensure minimum stop loss
            if stop_loss_pct < 0.01:  # Minimum 1% stop loss
                stop_loss_pct = 0.01
                stop_distance = current_price * 0.01
            
            # 5. Calculate position size using dynamic margin
            notional_value = dynamic_margin * LEVERAGE
            final_position_size = notional_value / current_price
            
            # 6. Calculate corresponding stop loss price
            stop_loss_price = current_price - stop_distance
            
            # 7. Enhanced logging with dynamic margin details
            logging.info(f"💰 DYNAMIC Position sizing for {symbol}:")
            logging.info(f"   📊 ATR: {atr_pct:.2f}% | Confidence: {signal_strength:.1%} | Vol: {volatility or 0:.2f}%")
            logging.info(f"   💵 Dynamic Margin: ${dynamic_margin:.2f} (range: $20-50)")
            logging.info(f"   🎯 Final Size: {final_position_size:.4f} | Notional: ${notional_value:.2f}")
            logging.info(f"   🛡️ Stop Loss: ${stop_loss_price:.6f} (-{stop_loss_pct*100:.1f}%)")
            
            return final_position_size, stop_loss_price
            
        except Exception as e:
            logging.error(f"Error calculating dynamic position size for {symbol}: {e}")
            return 0.0, 0.0
    
    def _calculate_dynamic_margin(self, atr_pct: float, volatility: float, 
                                 signal_strength: float, account_balance: float) -> float:
        """
        Calculate dynamic margin in 20-50 USD range based on risk indicators
        
        Args:
            atr_pct: ATR as percentage of price
            volatility: Market volatility percentage  
            signal_strength: ML signal confidence (0-1)
            account_balance: Current account balance
            
        Returns:
            float: Dynamic margin amount (20-50 USD)
        """
        try:
            # Base margin (center of range)
            base_margin = 35.0  # $35 USD center point
            
            # 1. VOLATILITY ADJUSTMENT (-15 to +15 USD)
            vol_adjustment = 0.0
            
            if atr_pct < 1.0:          # Low volatility (< 1%)
                vol_adjustment = +12.0  # Increase position size
            elif atr_pct < 2.0:        # Medium-low volatility (1-2%)
                vol_adjustment = +5.0   # Slight increase
            elif atr_pct < 3.0:        # Medium volatility (2-3%)
                vol_adjustment = 0.0    # No change
            elif atr_pct < 5.0:        # High volatility (3-5%)
                vol_adjustment = -8.0   # Decrease position size
            else:                      # Very high volatility (>5%)
                vol_adjustment = -15.0  # Significant decrease
            
            # 2. SIGNAL CONFIDENCE ADJUSTMENT (-10 to +10 USD)
            # Stronger signals = larger positions
            confidence_adjustment = (signal_strength - 0.7) * 25  # Scale around 70% confidence
            confidence_adjustment = max(-10.0, min(10.0, confidence_adjustment))
            
            # 3. MARKET VOLATILITY ADJUSTMENT (-5 to +5 USD)
            market_vol_adjustment = 0.0
            if volatility > 3.0:       # High market volatility
                market_vol_adjustment = -5.0
            elif volatility < 1.0:     # Low market volatility  
                market_vol_adjustment = +3.0
            
            # 4. BALANCE-BASED SAFETY ADJUSTMENT
            balance_safety = 0.0
            if account_balance < 100:
                balance_safety = -5.0  # Smaller positions with low balance
            elif account_balance > 500:
                balance_safety = +3.0  # Slightly larger with higher balance
            
            # 5. COMBINE ALL ADJUSTMENTS
            dynamic_margin = (base_margin + vol_adjustment + confidence_adjustment + 
                            market_vol_adjustment + balance_safety)
            
            # 6. ENFORCE STRICT BOUNDS (20-50 USD)
            dynamic_margin = max(20.0, min(50.0, dynamic_margin))
            
            # 7. DETAILED LOGGING FOR TRANSPARENCY
            logging.debug(f"🔧 Dynamic margin calculation:")
            logging.debug(f"   📊 Base: ${base_margin:.2f}")
            logging.debug(f"   📈 Volatility (ATR {atr_pct:.1f}%): {vol_adjustment:+.2f}")
            logging.debug(f"   🎯 Confidence ({signal_strength:.1%}): {confidence_adjustment:+.2f}")
            logging.debug(f"   🌊 Market Vol ({volatility:.1f}%): {market_vol_adjustment:+.2f}")
            logging.debug(f"   💰 Balance Safety: {balance_safety:+.2f}")
            logging.debug(f"   ✅ Final: ${dynamic_margin:.2f}")
            
            return dynamic_margin
            
        except Exception as e:
            logging.error(f"Error in dynamic margin calculation: {e}")
            return 35.0  # Safe fallback to center of range
    
    def validate_new_position(self,
                            symbol: str,
                            side: str,
                            size: float,
                            current_price: float,
                            account_balance: float,
                            existing_positions: List[PositionRisk]) -> Tuple[bool, str]:
        """
        Validate if a new position meets risk management criteria
        
        Returns:
            (approved, reason)
        """
        try:
            # 1. Check maximum positions
            if len(existing_positions) >= self.max_open_positions:
                return False, f"Maximum positions reached ({self.max_open_positions})"
            
            # 2. Check daily loss limit
            if self.daily_pnl < -account_balance * self.max_daily_loss:
                return False, f"Daily loss limit reached: {self.daily_pnl:.2f}"
            
            # 3. Check portfolio margin exposure - FIXED: Sum of MARGIN (pre-leverage) not NOTIONAL (post-leverage)
            # Calculate existing margin usage
            total_margin_used = sum(pos.size / LEVERAGE for pos in existing_positions)  # Convert notional to margin
            new_position_notional = size * current_price  # New position notional value
            new_position_margin = new_position_notional / LEVERAGE  # New position margin required
            total_new_margin = total_margin_used + new_position_margin
            
            max_total_margin = account_balance * 1.0  # Max margin = 1x wallet balance (your requirement)
            
            if total_new_margin > max_total_margin:
                logging.debug(f"Portfolio margin check: Existing=${total_margin_used:.2f}, New=${new_position_margin:.2f}, Total=${total_new_margin:.2f}, Max=${max_total_margin:.2f}")
                return False, f"Portfolio margin limit exceeded: ${total_new_margin:.2f} > ${max_total_margin:.2f} (wallet balance)"
            
            # 4. Check individual position risk - FIXED: Check MARGIN (pre-leverage) not NOTIONAL (post-leverage)
            position_notional = size * current_price  # Notional value (post-leverage)
            position_margin = position_notional / LEVERAGE  # Actual margin required (pre-leverage)
            
            max_margin_per_position = 50.0  # Max 50 USD margin per position (matching dynamic margin range)
            
            if position_margin > max_margin_per_position:
                return False, f"Position margin too large: ${position_margin:.2f} > ${max_margin_per_position:.2f}"
            
            # 5. Check symbol concentration - FIXED: Max 1 position per symbol (exact symbol match)
            same_symbol_count = sum(1 for pos in existing_positions if pos.symbol == symbol)
            if same_symbol_count >= 1:
                return False, f"Position already exists for {symbol} (max 1 per symbol)"
            
            # All checks passed
            return True, "Position approved"
            
        except Exception as e:
            logging.error(f"Error validating position for {symbol}: {e}")
            return False, f"Validation error: {e}"
    
    def calculate_stop_loss(self,
                          symbol: str,
                          side: str,
                          entry_price: float,
                          atr: float,
                          volatility: float = None) -> float:
        """
        Calculate dynamic stop loss based on market conditions
        """
        try:
            if atr <= 0 or entry_price <= 0:
                # Emergency fallback: fixed percentage stop loss
                emergency_stop_pct = 0.05  # 5% emergency stop
                if side == "Buy":
                    return entry_price * (1 - emergency_stop_pct)
                else:
                    return entry_price * (1 + emergency_stop_pct)
            
            # Base stop distance using ATR
            base_stop_distance = atr * self.atr_stop_multiplier
            
            # Adjust for volatility if available
            if volatility is not None:
                vol_multiplier = max(0.8, min(2.0, 1.0 + abs(volatility) / 100))
                stop_distance = base_stop_distance * vol_multiplier
            else:
                stop_distance = base_stop_distance
            
            # Ensure minimum stop distance
            min_stop_pct = 0.015  # Minimum 1.5% stop loss
            min_stop_distance = entry_price * min_stop_pct
            stop_distance = max(stop_distance, min_stop_distance)
            
            # Calculate stop loss price
            if side == "Buy":
                stop_loss = entry_price - stop_distance
            else:  # Sell
                stop_loss = entry_price + stop_distance
            
            # Ensure stop loss is reasonable (not negative or too extreme)
            if side == "Buy":
                stop_loss = max(stop_loss, entry_price * 0.85)  # Max 15% stop loss
            else:
                stop_loss = min(stop_loss, entry_price * 1.15)  # Max 15% stop loss
            
            logging.debug(f"Stop loss for {symbol} {side}: {stop_loss:.6f} (distance: {stop_distance:.6f})")
            return stop_loss
            
        except Exception as e:
            logging.error(f"Error calculating stop loss for {symbol}: {e}")
            # Emergency fallback
            if side == "Buy":
                return entry_price * 0.95  # 5% stop loss
            else:
                return entry_price * 1.05  # 5% stop loss
    
    def calculate_take_profit(self,
                            symbol: str,
                            side: str,
                            entry_price: float,
                            stop_loss: float,
                            risk_reward_ratio: float = 2.0) -> float:
        """
        Calculate take profit based on risk-reward ratio
        """
        try:
            # Calculate risk (distance to stop loss)
            if side == "Buy":
                risk = entry_price - stop_loss
                take_profit = entry_price + (risk * risk_reward_ratio)
            else:  # Sell
                risk = stop_loss - entry_price
                take_profit = entry_price - (risk * risk_reward_ratio)
            
            # Ensure take profit is reasonable
            if side == "Buy":
                take_profit = min(take_profit, entry_price * 1.30)  # Max 30% profit target
            else:
                take_profit = max(take_profit, entry_price * 0.70)  # Max 30% profit target
            
            logging.debug(f"Take profit for {symbol} {side}: {take_profit:.6f} (R:R = {risk_reward_ratio})")
            return take_profit
            
        except Exception as e:
            logging.error(f"Error calculating take profit for {symbol}: {e}")
            # Conservative fallback
            if side == "Buy":
                return entry_price * 1.10  # 10% profit target
            else:
                return entry_price * 0.90  # 10% profit target
    
    def assess_portfolio_risk(self,
                            positions: List[PositionRisk],
                            account_balance: float) -> PortfolioRisk:
        """
        Assess overall portfolio risk level
        """
        try:
            if not positions:
                return PortfolioRisk(
                    total_exposure=0.0,
                    total_unrealized_pnl=0.0,
                    max_drawdown=0.0,
                    open_positions=0,
                    correlation_risk=0.0,
                    overall_risk_level=RiskLevel.LOW
                )
            
            # Calculate metrics
            total_exposure = sum(pos.size * pos.current_price for pos in positions)
            total_pnl = sum(pos.unrealized_pnl for pos in positions)
            
            # Update drawdown tracking
            current_balance = account_balance + total_pnl
            self.peak_balance = max(self.peak_balance, current_balance)
            self.current_drawdown = (self.peak_balance - current_balance) / self.peak_balance
            
            # Assess risk level
            risk_factors = []
            
            # Exposure risk
            if total_exposure > account_balance * 1.5:
                risk_factors.append("high_exposure")
            
            # Drawdown risk
            if self.current_drawdown > 0.10:
                risk_factors.append("high_drawdown")
            elif self.current_drawdown > 0.05:
                risk_factors.append("medium_drawdown")
            
            # PnL risk
            pnl_pct = total_pnl / account_balance
            if pnl_pct < -0.05:
                risk_factors.append("high_loss")
            elif pnl_pct < -0.02:
                risk_factors.append("medium_loss")
            
            # Position count risk
            if len(positions) >= self.max_open_positions:
                risk_factors.append("max_positions")
            
            # Determine overall risk level
            if len(risk_factors) >= 3 or "high_drawdown" in risk_factors:
                overall_risk = RiskLevel.CRITICAL
            elif len(risk_factors) >= 2 or any(rf.startswith("high") for rf in risk_factors):
                overall_risk = RiskLevel.HIGH
            elif len(risk_factors) >= 1:
                overall_risk = RiskLevel.MEDIUM
            else:
                overall_risk = RiskLevel.LOW
            
            # CRITICAL FIX: Calculate correlation risk between positions
            correlation_risk = self._calculate_correlation_risk(positions)
            
            # Add correlation risk to overall assessment
            if correlation_risk > 0.8:
                risk_factors.append("high_correlation")
                if overall_risk == RiskLevel.LOW:
                    overall_risk = RiskLevel.MEDIUM
                elif overall_risk == RiskLevel.MEDIUM:
                    overall_risk = RiskLevel.HIGH
            elif correlation_risk > 0.6:
                risk_factors.append("medium_correlation")
            
            return PortfolioRisk(
                total_exposure=total_exposure,
                total_unrealized_pnl=total_pnl,
                max_drawdown=self.current_drawdown,
                open_positions=len(positions),
                correlation_risk=correlation_risk,
                overall_risk_level=overall_risk
            )
            
        except Exception as e:
            logging.error(f"Error assessing portfolio risk: {e}")
            return PortfolioRisk(
                total_exposure=0.0,
                total_unrealized_pnl=0.0,
                max_drawdown=0.0,
                open_positions=0,
                correlation_risk=0.0,
                overall_risk_level=RiskLevel.CRITICAL  # Assume worst case
            )
    
    def should_emergency_close(self,
                             portfolio_risk: PortfolioRisk,
                             account_balance: float) -> Tuple[bool, str]:
        """
        Determine if emergency position closure is needed
        """
        try:
            reasons = []
            
            # Critical drawdown
            if self.current_drawdown >= 0.20:  # 20% drawdown
                reasons.append(f"Critical drawdown: {self.current_drawdown*100:.1f}%")
            
            # Daily loss limit
            if self.daily_pnl <= -account_balance * self.max_daily_loss:
                reasons.append(f"Daily loss limit exceeded: {self.daily_pnl:.2f}")
            
            # Portfolio risk level
            if portfolio_risk.overall_risk_level == RiskLevel.CRITICAL:
                reasons.append("Critical portfolio risk level")
            
            # Large unrealized loss
            if portfolio_risk.total_unrealized_pnl <= -account_balance * 0.15:  # 15% unrealized loss
                reasons.append(f"Large unrealized loss: {portfolio_risk.total_unrealized_pnl:.2f}")
            
            if reasons:
                return True, "; ".join(reasons)
            
            return False, ""
            
        except Exception as e:
            logging.error(f"Error in emergency close check: {e}")
            return True, f"Emergency check error: {e}"  # Err on safe side
    
    def _calculate_correlation_risk(self, positions: List[PositionRisk]) -> float:
        """
        CRITICAL FIX: Calculate correlation risk between portfolio positions
        
        Args:
            positions: List of current positions
            
        Returns:
            float: Correlation risk score (0.0-1.0)
        """
        try:
            if len(positions) < 2:
                return 0.0  # No correlation with less than 2 positions
            
            # Simplified correlation calculation based on asset types
            base_assets = [pos.symbol.split('/')[0] if '/' in pos.symbol else pos.symbol[:3] 
                          for pos in positions]
            
            # Define asset correlation groups
            major_crypto = ['BTC', 'ETH']
            altcoins = ['SOL', 'ADA', 'MATIC', 'LINK', 'DOT', 'UNI', 'AVAX']
            meme_coins = ['DOGE', 'SHIB', 'PEPE', 'FLOKI', 'WIF', 'BONK']
            defi_tokens = ['AAVE', 'COMP', 'SNX', 'UNI', 'SUSHI']
            
            # Count positions by correlation groups
            group_counts = {
                'major_crypto': sum(1 for asset in base_assets if asset in major_crypto),
                'altcoins': sum(1 for asset in base_assets if asset in altcoins),
                'meme_coins': sum(1 for asset in base_assets if asset in meme_coins),
                'defi_tokens': sum(1 for asset in base_assets if asset in defi_tokens)
            }
            
            # Calculate correlation risk
            total_positions = len(positions)
            correlation_risk = 0.0
            
            for group, count in group_counts.items():
                if count > 1:
                    # High correlation risk if multiple positions in same group
                    group_correlation = (count / total_positions) ** 2
                    correlation_risk = max(correlation_risk, group_correlation)
            
            # Additional penalty for same-asset positions
            asset_counts = {}
            for asset in base_assets:
                asset_counts[asset] = asset_counts.get(asset, 0) + 1
            
            for asset, count in asset_counts.items():
                if count > 1:
                    same_asset_risk = count / total_positions
                    correlation_risk = max(correlation_risk, same_asset_risk)
            
            logging.debug(f"Portfolio correlation risk: {correlation_risk:.3f} (groups: {group_counts})")
            return min(1.0, correlation_risk)  # Cap at 1.0
            
        except Exception as e:
            logging.error(f"Error calculating correlation risk: {e}")
            return 0.5  # Conservative middle value on error

    def get_risk_adjusted_margin(self,
                               base_margin: float,
                               portfolio_risk: PortfolioRisk) -> float:
        """
        Adjust margin based on current risk level
        """
        try:
            risk_multipliers = {
                RiskLevel.LOW: 1.0,
                RiskLevel.MEDIUM: 0.8,
                RiskLevel.HIGH: 0.5,
                RiskLevel.CRITICAL: 0.2
            }
            
            multiplier = risk_multipliers.get(portfolio_risk.overall_risk_level, 0.5)
            adjusted_margin = base_margin * multiplier
            
            logging.info(f"Risk-adjusted margin: {adjusted_margin:.2f} (risk: {portfolio_risk.overall_risk_level.value})")
            return adjusted_margin
            
        except Exception as e:
            logging.error(f"Error adjusting margin: {e}")
            return base_margin * 0.5  # Conservative fallback


# Backward compatibility functions for existing code
def calculate_safe_position_size(exchange, symbol, usdt_balance, current_price, atr, volatility=None):
    """Backward compatible position sizing function"""
    risk_manager = RobustRiskManager()
    size, stop_loss = risk_manager.calculate_position_size(
        symbol=symbol,
        signal_strength=1.0,  # Default strength
        current_price=current_price,
        atr=atr,
        account_balance=usdt_balance,
        volatility=volatility
    )
    return size

def calculate_dynamic_stop_loss(symbol, side, entry_price, atr, volatility=None):
    """Backward compatible stop loss function"""
    risk_manager = RobustRiskManager()
    return risk_manager.calculate_stop_loss(symbol, side, entry_price, atr, volatility)
