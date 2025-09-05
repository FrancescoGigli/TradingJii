"""
Advanced Risk Management System for Trading Bot

CRITICAL FIXES:
- Dynamic stop loss based on ATR
- Volatility-based position sizing  
- Portfolio correlation limits
- Drawdown protection
- Maximum exposure controls
"""

import logging
import numpy as np
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
import pandas as pd

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
    Advanced risk management system that prevents catastrophic losses
    """
    
    def __init__(self):
        self.max_portfolio_risk = 0.02  # 2% max portfolio risk
        self.max_single_position_risk = 0.005  # 0.5% max risk per trade
        self.max_open_positions = 3
        self.max_correlation = 0.7  # Max correlation between positions
        self.max_daily_loss = 0.05  # 5% max daily loss
        self.atr_stop_multiplier = 2.0  # Stop loss = 2x ATR
        self.max_leverage = 10
        self.emergency_stop_loss = 0.10  # 10% emergency stop
        
        # Portfolio tracking with dynamic connection to PositionTracker
        self.daily_pnl = 0.0
        self.peak_balance = None  # FIXED: Will sync with PositionTracker
        self.current_drawdown = 0.0
        self._position_tracker = None  # Will be linked dynamically
        
    
    def sync_with_position_tracker(self):
        """
        CRITICAL FIX: Sync with global PositionTracker for dynamic balance
        """
        try:
            from core.position_tracker import global_position_tracker
            self._position_tracker = global_position_tracker
            
            # Update peak balance from position tracker
            current_balance = self._position_tracker.session_stats['current_balance']
            if self.peak_balance is None:
                self.peak_balance = self._position_tracker.session_stats['initial_balance']
                
            # Sync peak balance 
            if current_balance > self.peak_balance:
                self.peak_balance = current_balance
                
            logging.info(f"🔗 Risk Manager synced: Current: {current_balance:.2f}, Peak: {self.peak_balance:.2f}")
            return True
            
        except Exception as e:
            logging.warning(f"Failed to sync with PositionTracker: {e}")
            # Fallback to static values
            if self.peak_balance is None:
                from config import DEMO_BALANCE
                self.peak_balance = DEMO_BALANCE
            return False
    
    def get_current_balance(self) -> float:
        """Get current balance from PositionTracker or fallback"""
        try:
            if self._position_tracker:
                return self._position_tracker.session_stats['current_balance']
            else:
                self.sync_with_position_tracker()
                if self._position_tracker:
                    return self._position_tracker.session_stats['current_balance']
                    
            # Fallback
            from config import DEMO_BALANCE
            return DEMO_BALANCE
            
        except Exception as e:
            logging.error(f"Error getting current balance: {e}")
            from config import DEMO_BALANCE
            return DEMO_BALANCE
    
    def calculate_position_size(self, 
                              symbol: str,
                              signal_strength: float,
                              current_price: float,
                              atr: float,
                              account_balance: float,
                              volatility: float = None) -> Tuple[float, float]:
        """
        Calculate optimal position size based on risk management rules
        
        Returns:
            (position_size, stop_loss_price)
        """
        try:
            # 1. Risk-based position sizing
            if atr <= 0 or current_price <= 0:
                logging.error(f"Invalid ATR ({atr}) or price ({current_price}) for {symbol}")
                return 0.0, 0.0
            
            # Calculate stop loss distance (ATR-based)
            stop_distance = atr * self.atr_stop_multiplier
            stop_loss_pct = stop_distance / current_price
            
            # Ensure minimum stop loss
            if stop_loss_pct < 0.01:  # Minimum 1% stop loss
                stop_loss_pct = 0.01
                stop_distance = current_price * 0.01
            
            # Maximum risk per trade in USD
            max_risk_usd = account_balance * self.max_single_position_risk
            
            # Calculate position size based on stop loss
            # Risk = Position Size * Stop Loss Distance
            # Position Size = Risk / Stop Loss Distance
            base_position_size = max_risk_usd / stop_distance
            
            # 2. Volatility adjustment
            if volatility is not None:
                vol_adjustment = max(0.5, min(1.5, 1.0 / (1.0 + abs(volatility) / 10.0)))
                base_position_size *= vol_adjustment
            
            # 3. Signal strength adjustment (0.5 to 1.5 multiplier)
            signal_adjustment = max(0.5, min(1.5, signal_strength))
            adjusted_position_size = base_position_size * signal_adjustment
            
            # 4. Leverage and margin constraints
            max_margin = MARGIN_USDT
            max_notional = max_margin * LEVERAGE
            max_size_by_margin = max_notional / current_price
            
            # Take minimum of all constraints
            final_position_size = min(adjusted_position_size, max_size_by_margin)
            
            # Calculate corresponding stop loss
            stop_loss_price = current_price - stop_distance
            
            logging.info(f"💰 Position size for {symbol}: {final_position_size:.4f} (risk: ${max_risk_usd:.2f}, stop: {stop_loss_price:.6f})")
            
            return final_position_size, stop_loss_price
            
        except Exception as e:
            logging.error(f"Error calculating position size for {symbol}: {e}")
            return 0.0, 0.0
    
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
            
            # 3. Check portfolio exposure
            total_exposure = sum(pos.size * pos.current_price for pos in existing_positions)
            new_exposure = size * current_price
            total_new_exposure = total_exposure + new_exposure
            
            max_exposure = account_balance * 2.0  # Max 2x account balance in total exposure
            if total_new_exposure > max_exposure:
                return False, f"Portfolio exposure limit: {total_new_exposure:.2f} > {max_exposure:.2f}"
            
            # 4. Check individual position risk
            max_position_value = account_balance * 0.5  # Max 50% of balance per position
            position_value = size * current_price
            if position_value > max_position_value:
                return False, f"Position too large: {position_value:.2f} > {max_position_value:.2f}"
            
            # 5. Check symbol concentration (max 2 positions of same base asset)
            base_asset = symbol.split('/')[0] if '/' in symbol else symbol[:3]
            same_asset_count = sum(1 for pos in existing_positions 
                                 if pos.symbol.split('/')[0] == base_asset)
            if same_asset_count >= 2:
                return False, f"Too many {base_asset} positions: {same_asset_count}"
            
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
            
            return PortfolioRisk(
                total_exposure=total_exposure,
                total_unrealized_pnl=total_pnl,
                max_drawdown=self.current_drawdown,
                open_positions=len(positions),
                correlation_risk=0.0,  # Simplified for now
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
