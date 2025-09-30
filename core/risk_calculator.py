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
from config import (
    LEVERAGE,
    # Dynamic Position Sizing
    POSITION_SIZE_CONSERVATIVE,
    POSITION_SIZE_MODERATE,
    POSITION_SIZE_AGGRESSIVE,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_LOW_THRESHOLD,
    VOLATILITY_SIZING_LOW,
    VOLATILITY_SIZING_HIGH,
    ADX_STRONG_TREND,
    # Margin Ranges
    MARGIN_MIN,
    MARGIN_MAX,
    MARGIN_BASE,
    # Stop Loss
    SL_ATR_MULTIPLIER,
    SL_PRICE_PCT_FALLBACK,
    SL_MIN_DISTANCE_PCT,
    SL_MAX_DISTANCE_PCT,
    # Take Profit
    TP_RISK_REWARD_RATIO,
    TP_MAX_PROFIT_PCT,
    TP_MIN_PROFIT_PCT,
)

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
    adx: float = 0.0  # Trend strength (optional, default 0)
    
class RiskCalculator:
    """
    Clean risk calculation engine
    
    PHILOSOPHY: Pure functions, predictable outputs, zero side effects
    """
    
    def __init__(self):
        # Position Sizing from config
        self.position_conservative = POSITION_SIZE_CONSERVATIVE
        self.position_moderate = POSITION_SIZE_MODERATE
        self.position_aggressive = POSITION_SIZE_AGGRESSIVE
        
        # Thresholds from config
        self.confidence_high = CONFIDENCE_HIGH_THRESHOLD
        self.confidence_low = CONFIDENCE_LOW_THRESHOLD
        self.volatility_low = VOLATILITY_SIZING_LOW
        self.volatility_high = VOLATILITY_SIZING_HIGH
        self.adx_strong = ADX_STRONG_TREND
        
        # Margin ranges from config
        self.min_margin = MARGIN_MIN
        self.max_margin = MARGIN_MAX
        self.base_margin = MARGIN_BASE
        
        # Stop Loss from config
        self.atr_multiplier = SL_ATR_MULTIPLIER
        self.sl_fallback = SL_PRICE_PCT_FALLBACK
        self.sl_min_distance = SL_MIN_DISTANCE_PCT
        self.sl_max_distance = SL_MAX_DISTANCE_PCT
        
        # Take Profit from config
        self.risk_reward_ratio = TP_RISK_REWARD_RATIO
        self.tp_max_profit = TP_MAX_PROFIT_PCT
        self.tp_min_profit = TP_MIN_PROFIT_PCT
        
    def calculate_intelligent_position_size(self, confidence: float, atr_pct: float, 
                                           adx: float = 0.0) -> float:
        """
        🎯 INTELLIGENT 3-TIER POSITION SIZING
        
        Determina intelligentemente la size della posizione basandosi su:
        - Confidence del segnale ML
        - Volatilità del mercato (ATR)
        - Forza del trend (ADX)
        
        Returns:
            float: 50.0, 75.0, or 100.0 USD
        """
        try:
            # Score factors (0-3 points)
            score = 0
            
            # Factor 1: ML Confidence (0-1 point)
            if confidence >= self.confidence_high:  # ≥75%
                score += 1
                confidence_tier = "HIGH"
            elif confidence >= self.confidence_low:  # 65-75%
                score += 0.5
                confidence_tier = "MEDIUM"
            else:  # <65%
                confidence_tier = "LOW"
            
            # Factor 2: Volatility (0-1 point)
            volatility_pct = atr_pct / 100.0  # Convert to decimal
            if volatility_pct < self.volatility_low:  # <1.5%
                score += 1
                volatility_tier = "LOW"
            elif volatility_pct < self.volatility_high:  # 1.5-3.5%
                score += 0.5
                volatility_tier = "MEDIUM"
            else:  # >3.5%
                volatility_tier = "HIGH"
            
            # Factor 3: Trend Strength (0-1 point)
            if adx >= self.adx_strong:  # ≥25
                score += 1
                trend_tier = "STRONG"
            elif adx >= 20.0:
                score += 0.5
                trend_tier = "MODERATE"
            else:
                trend_tier = "WEAK"
            
            # Determine position size based on total score
            if score >= 2.5:
                # AGGRESSIVE: High confidence + low volatility + strong trend
                position_size = self.position_aggressive
                tier = "AGGRESSIVE"
            elif score >= 1.5:
                # MODERATE: Medium conditions
                position_size = self.position_moderate
                tier = "MODERATE"
            else:
                # CONSERVATIVE: Uncertain conditions
                position_size = self.position_conservative
                tier = "CONSERVATIVE"
            
            logging.info(
                f"💰 POSITION SIZING: ${position_size:.0f} USD ({tier})\n"
                f"   📊 Score: {score:.1f}/3.0\n"
                f"   🎯 Confidence: {confidence:.1%} ({confidence_tier})\n"
                f"   📉 Volatility: {atr_pct:.2f}% ({volatility_tier})\n"
                f"   📈 Trend ADX: {adx:.1f} ({trend_tier})"
            )
            
            return position_size
            
        except Exception as e:
            logging.error(f"Error in intelligent position sizing: {e}")
            return self.position_conservative  # Safe fallback
    
    def calculate_dynamic_margin(self, atr_pct: float, confidence: float, 
                                volatility: float = 0.0, balance: float = 200.0,
                                adx: float = 0.0) -> float:
        """
        Calculate dynamic margin using intelligent 3-tier system
        
        Args:
            atr_pct: ATR as percentage of price
            confidence: ML signal confidence (0-1)
            volatility: Market volatility (legacy, not used)
            balance: Account balance (for safety checks)
            adx: Trend strength (ADX indicator)
            
        Returns:
            float: Dynamic margin amount (50/75/100 USD)
        """
        try:
            # Use intelligent 3-tier position sizing
            position_size = self.calculate_intelligent_position_size(
                confidence, atr_pct, adx
            )
            
            # Balance safety check
            max_allowed = balance * 0.5  # Never use more than 50% of balance
            if position_size > max_allowed:
                logging.warning(
                    f"⚠️ Position size ${position_size:.0f} exceeds 50% of balance "
                    f"(${balance:.0f}). Capping at ${max_allowed:.0f}"
                )
                position_size = max_allowed
            
            return position_size
            
        except Exception as e:
            logging.error(f"Error calculating dynamic margin: {e}")
            return self.position_conservative  # Safe fallback
    
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
            # STEP 2 FIX: Emergency fallback uses config
            sl_pct = self.sl_fallback  # From config
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
                ratio = self.risk_reward_ratio  # From config
            
            # Calculate risk distance
            if side.lower() == 'buy':
                risk = abs(entry_price - stop_loss)  # Use abs to ensure positive
                take_profit = entry_price + (risk * ratio)  # Above entry for BUY
                # Cap at max profit from config
                max_tp = entry_price * (1 + self.tp_max_profit)
                take_profit = min(take_profit, max_tp)
            else:  # SELL position
                risk = abs(stop_loss - entry_price)  # Use abs to ensure positive  
                take_profit = entry_price - (risk * ratio)  # Below entry for SELL
                # Cap at max profit from config
                min_tp = entry_price * (1 - self.tp_max_profit)
                take_profit = max(take_profit, min_tp)
            
            logging.debug(f"🎯 TP Calc: Entry ${entry_price:.6f} | Side {side} | Risk {risk:.6f} | Ratio {ratio:.1f} | TP ${take_profit:.6f}")
            
            return take_profit
            
        except Exception as e:
            logging.error(f"Error calculating take profit: {e}")
            # Conservative fallback: min profit from config
            return entry_price * (
                1 + self.tp_min_profit if side.lower() == 'buy' 
                else 1 - self.tp_min_profit
            )
    
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
            # 1. Calculate dynamic margin with ADX for intelligent position sizing
            atr_pct = (market_data.atr / market_data.price) * 100
            margin = self.calculate_dynamic_margin(
                atr_pct, confidence, market_data.volatility, balance, market_data.adx
            )
            
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
