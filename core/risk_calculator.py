#!/usr/bin/env python3
"""
🛡️ CLEAN RISK CALCULATOR

SINGLE RESPONSIBILITY: Calcoli risk management
- Dynamic position sizing (20-50 USD range)
- Stop loss calculation (ATR-based)
- Take profit calculation (risk-reward ratio)
- Portfolio risk validation
- Zero order execution, solo calcoli

GARANTISCE: Calcoli accurati e configurabili
"""

import logging
from typing import Tuple, Dict, Optional
from dataclasses import dataclass
from config import LEVERAGE

@dataclass
class PositionLevels:
    """Clean data class for position levels"""
    margin: float           # Margin to use (20-50 USD)
    position_size: float    # Position size in contracts
    stop_loss: float        # Stop loss price
    take_profit: float      # Take profit price
    risk_pct: float         # Risk percentage
    reward_pct: float       # Reward percentage
    risk_reward_ratio: float # Risk:Reward ratio

@dataclass 
class MarketData:
    """Market data for risk calculations"""
    price: float
    atr: float
    volatility: float
    
class RiskCalculator:
    """
    Clean risk calculation engine
    
    PHILOSOPHY: Pure functions, predictable outputs, zero side effects
    """
    
    def __init__(self):
        # Risk parameters - CRITICAL FIX: Force higher minimums
        self.min_margin = 25.0      # INCREASED: Minimum margin USD (was 20)
        self.max_margin = 60.0      # INCREASED: Maximum margin USD (was 50)
        self.base_margin = 40.0     # INCREASED: Center point USD (was 35)
        self.atr_multiplier = 2.0   # Stop loss = 2x ATR
        self.risk_reward_ratio = 2.0 # Take profit ratio
        
    def calculate_dynamic_margin(self, atr_pct: float, confidence: float, 
                                volatility: float = 0.0, balance: float = 200.0) -> float:
        """
        Calculate dynamic margin in 20-50 USD range
        
        Args:
            atr_pct: ATR as percentage of price
            confidence: ML signal confidence (0-1)
            volatility: Market volatility
            balance: Account balance
            
        Returns:
            float: Dynamic margin amount (20-50 USD range)
        """
        try:
            # CRITICAL FIX: Start with higher base to ensure proper IM
            margin = self.base_margin  # Use the increased base_margin (40.0)
            
            # 1. Volatility adjustment (more conservative)
            if atr_pct < 1.0:          # Low volatility
                margin += 5.0
            elif atr_pct < 2.0:        # Medium-low volatility  
                margin += 2.0
            elif atr_pct < 3.0:        # Medium volatility
                margin += 0.0
            elif atr_pct < 5.0:        # High volatility
                margin -= 3.0  
            else:                      # Very high volatility
                margin -= 5.0
            
            # 2. Confidence adjustment (more conservative)
            confidence_adjustment = (confidence - 0.7) * 15  # Reduced from 20
            margin += max(-5.0, min(5.0, confidence_adjustment))  # Reduced range
            
            # 3. Market volatility adjustment (more conservative)
            if volatility > 3.0:
                margin -= 2.0  # Reduced from 3.0
            elif volatility < 1.0:
                margin += 1.0  # Reduced from 2.0
                
            # 4. Balance safety adjustment (more conservative)
            if balance < 100:
                margin -= 2.0  # Reduced from 3.0
            elif balance > 500:
                margin += 1.0  # Reduced from 2.0
            
            # 5. CRITICAL FIX: Enforce higher minimum range (25-60 USD)
            final_margin = max(self.min_margin, min(self.max_margin, margin))
            
            logging.debug(f"💰 Dynamic margin: ATR {atr_pct:.1f}% + Conf {confidence:.1%} = ${final_margin:.2f} (20-50 USD range)")
            
            return final_margin
            
        except Exception as e:
            logging.error(f"Error calculating dynamic margin: {e}")
            return 25.0  # Safe fallback in 20-50 range
    
    def calculate_stop_loss_price(self, entry_price: float, side: str, atr: float,
                                 volatility: float = 0.0) -> float:
        """
        STEP 2 FIX: Delegate to UnifiedStopLossCalculator (eliminate hardcoded calculations)
        
        Args:
            entry_price: Position entry price
            side: Position side ('buy' or 'sell')
            atr: Average True Range (used for validation only)
            volatility: Market volatility (used for validation only)
            
        Returns:
            float: Stop loss price from unified calculator
        """
        try:
            # STEP 2 FIX: Use UnifiedStopLossCalculator instead of hardcoded calculations
            from core.unified_stop_loss_calculator import global_unified_stop_loss_calculator
            
            # Get unified stop loss calculation
            unified_sl = global_unified_stop_loss_calculator.calculate_unified_stop_loss(
                entry_price, side, f"Risk_Calculator_Request"
            )
            
            logging.debug(f"🛡️ UNIFIED SL: Entry ${entry_price:.6f} | Side {side} | Unified SL ${unified_sl:.6f}")
            
            return unified_sl
            
        except Exception as e:
            logging.error(f"Error with unified SL calculation: {e}")
            # STEP 2 FIX: Emergency fallback still uses unified calculator constants
            sl_pct = 0.06  # 6% from UnifiedStopLossCalculator
            return entry_price * (1 - sl_pct if side.lower() == 'buy' else 1 + sl_pct)
    
    def calculate_take_profit_price(self, entry_price: float, side: str, 
                                   stop_loss: float, ratio: float = None) -> float:
        """
        Calculate take profit price based on risk-reward ratio
        
        Args:
            entry_price: Position entry price
            side: Position side ('buy' or 'sell')
            stop_loss: Stop loss price
            ratio: Risk-reward ratio (default: 2.0)
            
        Returns:
            float: Take profit price
        """
        try:
            if ratio is None:
                ratio = 1.5  # CONSERVATIVE: Reduced from 2.0 to 1.5 for more realistic targets
            
            # Calculate risk distance
            if side.lower() == 'buy':
                risk = abs(entry_price - stop_loss)  # Use abs to ensure positive
                take_profit = entry_price + (risk * ratio)  # Above entry for BUY
                # CONSERVATIVE: Cap at max 8% profit instead of 30%
                take_profit = min(take_profit, entry_price * 1.08)
            else:  # SELL position
                risk = abs(stop_loss - entry_price)  # Use abs to ensure positive  
                take_profit = entry_price - (risk * ratio)  # Below entry for SELL
                # CONSERVATIVE: Cap at max 8% profit instead of 30%
                take_profit = max(take_profit, entry_price * 0.92)
            
            logging.debug(f"🎯 TP Calc: Entry ${entry_price:.6f} | Side {side} | Risk {risk:.6f} | Ratio {ratio:.1f} | TP ${take_profit:.6f}")
            
            return take_profit
            
        except Exception as e:
            logging.error(f"Error calculating take profit: {e}")
            # Conservative fallback: 4% profit target
            return entry_price * (1.04 if side.lower() == 'buy' else 0.96)
    
    def calculate_position_levels(self, market_data: MarketData, side: str, 
                                 confidence: float, balance: float) -> PositionLevels:
        """
        Calculate complete position levels (margin, size, SL, TP)
        
        Args:
            market_data: Market data (price, ATR, volatility)
            side: Position side
            confidence: ML confidence
            balance: Account balance
            
        Returns:
            PositionLevels: Complete position setup data
        """
        try:
            # 1. Calculate dynamic margin
            atr_pct = (market_data.atr / market_data.price) * 100
            margin = self.calculate_dynamic_margin(atr_pct, confidence, market_data.volatility, balance)
            
            # 2. Calculate position size
            notional_value = margin * LEVERAGE
            position_size = notional_value / market_data.price
            
            # 3. Calculate stop loss
            stop_loss = self.calculate_stop_loss_price(
                market_data.price, side, market_data.atr, market_data.volatility
            )
            
            # 4. Calculate take profit
            take_profit = self.calculate_take_profit_price(market_data.price, side, stop_loss)
            
            # 5. Calculate percentages
            if side.lower() == 'buy':
                risk_pct = ((market_data.price - stop_loss) / market_data.price) * 100
                reward_pct = ((take_profit - market_data.price) / market_data.price) * 100
            else:
                risk_pct = ((stop_loss - market_data.price) / market_data.price) * 100
                reward_pct = ((market_data.price - take_profit) / market_data.price) * 100
            
            # 6. Calculate risk-reward ratio
            rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0
            
            return PositionLevels(
                margin=margin,
                position_size=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_pct=risk_pct,
                reward_pct=reward_pct,
                risk_reward_ratio=rr_ratio
            )
            
        except Exception as e:
            logging.error(f"Error calculating position levels: {e}")
            # CRITICAL FIX: Return safe fallback levels with higher margin
            fallback_margin = self.base_margin  # Use the new higher base (40.0)
            fallback_notional = fallback_margin * LEVERAGE
            
            # STEP 2 FIX: Use unified calculator even in fallback
            try:
                from core.unified_stop_loss_calculator import global_unified_stop_loss_calculator
                fallback_sl = global_unified_stop_loss_calculator.calculate_unified_stop_loss(
                    market_data.price, side, "Risk_Calculator_Fallback"
                )
            except:
                fallback_sl = market_data.price * (0.94 if side.lower() == 'buy' else 1.06)
            
            return PositionLevels(
                margin=fallback_margin,
                position_size=fallback_notional / market_data.price,
                stop_loss=fallback_sl,  # STEP 2 FIX: Use unified calculator
                take_profit=market_data.price * (1.10 if side.lower() == 'buy' else 0.90),
                risk_pct=6.0,
                reward_pct=10.0,
                risk_reward_ratio=1.67
            )
    
    def validate_portfolio_margin(self, existing_margins: list, new_margin: float, 
                                 total_balance: float) -> Tuple[bool, str]:
        """
        Validate portfolio margin usage
        
        Args:
            existing_margins: List of existing position margins
            new_margin: New position margin to add
            total_balance: Total account balance
            
        Returns:
            Tuple[bool, str]: (approved, reason)
        """
        try:
            current_total = sum(existing_margins)
            new_total = current_total + new_margin
            
            # Rule: Total margin ≤ Account balance
            max_allowed = total_balance * 1.0
            
            if new_total > max_allowed:
                return False, f"Portfolio margin limit: ${new_total:.2f} > ${max_allowed:.2f}"
            
            # CRITICAL FIX: Update to match new max_margin
            if new_margin > self.max_margin:
                return False, f"Single position limit: ${new_margin:.2f} > ${self.max_margin:.2f}"
            
            # CRITICAL FIX: Enforce absolute minimum margin
            if new_margin < self.min_margin:
                return False, f"Position too small: ${new_margin:.2f} < ${self.min_margin:.2f} minimum required"
            
            return True, "Portfolio margin approved"
            
        except Exception as e:
            logging.error(f"Portfolio validation error: {e}")
            return False, f"Validation error: {e}"

# Global risk calculator instance
global_risk_calculator = RiskCalculator()
