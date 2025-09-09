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
        # Risk parameters
        self.min_margin = 20.0      # Minimum margin USD
        self.max_margin = 50.0      # Maximum margin USD  
        self.base_margin = 35.0     # Center point USD
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
            float: Dynamic margin amount (20-50 USD)
        """
        try:
            # Start with base margin
            margin = self.base_margin
            
            # 1. Volatility adjustment (-15 to +15 USD)
            if atr_pct < 1.0:          # Low volatility
                margin += 12.0
            elif atr_pct < 2.0:        # Medium-low volatility  
                margin += 5.0
            elif atr_pct < 3.0:        # Medium volatility
                margin += 0.0
            elif atr_pct < 5.0:        # High volatility
                margin -= 8.0  
            else:                      # Very high volatility
                margin -= 15.0
            
            # 2. Confidence adjustment (-10 to +10 USD)
            confidence_adjustment = (confidence - 0.7) * 25
            margin += max(-10.0, min(10.0, confidence_adjustment))
            
            # 3. Market volatility adjustment (-5 to +5 USD)
            if volatility > 3.0:
                margin -= 5.0
            elif volatility < 1.0:
                margin += 3.0
                
            # 4. Balance safety adjustment
            if balance < 100:
                margin -= 5.0
            elif balance > 500:
                margin += 3.0
            
            # 5. Enforce bounds
            final_margin = max(self.min_margin, min(self.max_margin, margin))
            
            logging.debug(f"💰 Dynamic margin: ATR {atr_pct:.1f}% + Conf {confidence:.1%} = ${final_margin:.2f}")
            
            return final_margin
            
        except Exception as e:
            logging.error(f"Error calculating dynamic margin: {e}")
            return self.base_margin  # Safe fallback
    
    def calculate_stop_loss_price(self, entry_price: float, side: str, atr: float,
                                 volatility: float = 0.0) -> float:
        """
        Calculate stop loss price based on ATR
        
        Args:
            entry_price: Position entry price
            side: Position side ('buy' or 'sell')
            atr: Average True Range
            volatility: Market volatility adjustment
            
        Returns:
            float: Stop loss price
        """
        try:
            # Base stop distance using ATR
            stop_distance = atr * self.atr_multiplier
            
            # Volatility adjustment
            if volatility > 0:
                vol_multiplier = max(0.8, min(2.0, 1.0 + abs(volatility) / 100))
                stop_distance *= vol_multiplier
            
            # Ensure minimum stop distance (1.5%)
            min_stop_distance = entry_price * 0.015
            stop_distance = max(stop_distance, min_stop_distance)
            
            # Calculate stop loss price
            if side.lower() == 'buy':
                stop_loss = entry_price - stop_distance
                # Ensure reasonable limit (max 15% loss)
                stop_loss = max(stop_loss, entry_price * 0.85)
            else:
                stop_loss = entry_price + stop_distance
                # Ensure reasonable limit (max 15% loss)
                stop_loss = min(stop_loss, entry_price * 1.15)
            
            return stop_loss
            
        except Exception as e:
            logging.error(f"Error calculating stop loss: {e}")
            # Emergency fallback: 5% stop
            return entry_price * (0.95 if side.lower() == 'buy' else 1.05)
    
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
                ratio = self.risk_reward_ratio
            
            # Calculate risk distance
            if side.lower() == 'buy':
                risk = entry_price - stop_loss
                take_profit = entry_price + (risk * ratio)
                # Cap at max 30% profit
                take_profit = min(take_profit, entry_price * 1.30)
            else:
                risk = stop_loss - entry_price  
                take_profit = entry_price - (risk * ratio)
                # Cap at max 30% profit
                take_profit = max(take_profit, entry_price * 0.70)
            
            return take_profit
            
        except Exception as e:
            logging.error(f"Error calculating take profit: {e}")
            # Conservative fallback: 10% profit target
            return entry_price * (1.10 if side.lower() == 'buy' else 0.90)
    
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
            # Return safe fallback levels
            return PositionLevels(
                margin=35.0,
                position_size=350.0 / market_data.price,
                stop_loss=market_data.price * (0.95 if side.lower() == 'buy' else 1.05),
                take_profit=market_data.price * (1.10 if side.lower() == 'buy' else 0.90),
                risk_pct=5.0,
                reward_pct=10.0,
                risk_reward_ratio=2.0
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
            
            # Rule: Single position ≤ $50 margin
            if new_margin > 50.0:
                return False, f"Single position limit: ${new_margin:.2f} > $50.00"
            
            return True, "Portfolio margin approved"
            
        except Exception as e:
            logging.error(f"Portfolio validation error: {e}")
            return False, f"Validation error: {e}"

# Global risk calculator instance
global_risk_calculator = RiskCalculator()
