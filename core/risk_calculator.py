#!/usr/bin/env python3
"""
🛡️ CLEAN RISK CALCULATOR

SINGLE RESPONSIBILITY: Calcoli risk management
- Fixed position sizing ($30 USD)
- Stop loss calculation (ATR-based)
- Take profit calculation (risk-reward ratio)
- Portfolio risk validation
- Zero order execution, solo calcoli

GARANTISCE: Calcoli accurati e configurabili
"""

import logging
from typing import Tuple, Dict, Optional, List
from dataclasses import dataclass
from termcolor import colored
from config import (
    LEVERAGE,
    # Take Profit
    TP_RISK_REWARD_RATIO,
    TP_MAX_PROFIT_PCT,
    TP_MIN_PROFIT_PCT,
    # Fixed Size Mode
    FIXED_POSITION_SIZE_AMOUNT,
    BASE_MARGIN,
    MIN_MARGIN,
    MAX_MARGIN,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_LOW_THRESHOLD,
    VOLATILITY_LOW_TIER,
    VOLATILITY_HIGH_TIER,
    ADX_STRONG_THRESHOLD,
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
    """Market data for risk calculations with defensive validation"""
    price: float
    atr: float
    volatility: float
    adx: float = 0.0  # Trend strength (optional, default 0)
    
    def __post_init__(self):
        """🔧 FIX #3: DEFENSIVE GUARDS - Validate and sanitize inputs"""
        # Ensure all values are floats (handle None, "", etc.)
        self.price = float(self.price or 0)
        self.atr = float(self.atr or 0)
        self.volatility = float(self.volatility or 0.03)  # Default 3% volatility
        self.adx = float(self.adx or 0)
        
        # Sanity checks
        if self.price <= 0:
            raise ValueError(f"Invalid price: {self.price}. Price must be > 0")
        
        # Negative values don't make sense, set to 0
        if self.atr < 0:
            logging.warning(f"Negative ATR {self.atr} detected, setting to 0")
            self.atr = 0
        
        if self.volatility < 0:
            logging.warning(f"Negative volatility {self.volatility} detected, setting to default 0.03")
            self.volatility = 0.03
        
        if self.adx < 0:
            self.adx = 0
        
        # Log if using defaults
        if self.atr == 0:
            logging.debug("ATR is 0, risk calculations may use fallbacks")
    
class RiskCalculator:
    """
    Clean risk calculation engine
    
    PHILOSOPHY: Pure functions, predictable outputs, zero side effects
    """
    
    def __init__(self):
        # Take Profit from config
        self.risk_reward_ratio = TP_RISK_REWARD_RATIO
        self.tp_max_profit = TP_MAX_PROFIT_PCT
        self.tp_min_profit = TP_MIN_PROFIT_PCT
        
        # Fixed Size
        self.fixed_size = FIXED_POSITION_SIZE_AMOUNT
        
        # Threshold reference (kept for logging/analysis)
        self.confidence_high = CONFIDENCE_HIGH_THRESHOLD
        self.confidence_low = CONFIDENCE_LOW_THRESHOLD
        self.volatility_low = VOLATILITY_LOW_TIER
        self.volatility_high = VOLATILITY_HIGH_TIER
        self.adx_strong = ADX_STRONG_THRESHOLD
        
        # Limits
        self.min_margin = MIN_MARGIN
        self.max_margin = MAX_MARGIN
        self.base_margin = BASE_MARGIN
        
    def calculate_dynamic_position_sizes(self, available_balance: float) -> Tuple[float, float, float]:
        """
        🎯 FIXED: Restituisce sempre la size fissa configurata
        
        Args:
            available_balance: Balance USDT disponibile (non usato per il calcolo size)
            
        Returns:
            Tuple[float, float, float]: (fixed, fixed, fixed)
        """
        return (self.fixed_size, self.fixed_size, self.fixed_size)
    
    def calculate_intelligent_position_size(self, confidence: float, atr_pct: float, 
                                           adx: float = 0.0, 
                                           available_balance: float = 1000.0) -> float:
        """
        🎯 FIXED: Restituisce sempre la size fissa configurata
        Ignora i parametri di input del segnale.
        """
        return self.fixed_size
    
    def calculate_dynamic_margin(self, atr_pct: float, confidence: float, 
                                volatility: float = 0.0, balance: float = 200.0,
                                adx: float = 0.0) -> float:
        """
        Calculate margin using fixed size strategy
        """
        try:
            # Always use fixed size
            position_size = self.fixed_size
            
            # Balance safety check
            # Ensure we have enough balance for at least 1 position
            if balance < position_size:
                logging.warning(
                    f"⚠️ Insufficient balance ${balance:.2f} for fixed size ${position_size:.2f}"
                )
                return 0.0 # Cannot open
            
            return position_size
            
        except Exception as e:
            logging.error(f"Error calculating margin: {e}")
            return self.fixed_size
    
    def calculate_stop_loss_fixed(self, entry_price: float, side: str) -> float:
        """
        🛡️ FIXED STOP LOSS: -5% contro posizione
        
        Calcola stop loss fisso al 5% dal prezzo di entrata:
        - LONG: SL = entry × 0.95 (-5%)
        - SHORT: SL = entry × 1.05 (+5%)
        """
        try:
            from config import STOP_LOSS_PCT
            
            if side.lower() in ['buy', 'long']:
                stop_loss = entry_price * (1 - STOP_LOSS_PCT)
            else:
                stop_loss = entry_price * (1 + STOP_LOSS_PCT)
            
            return stop_loss
            
        except Exception as e:
            logging.error(f"Error calculating fixed stop loss: {e}")
            # Safe fallback
            return entry_price * (0.95 if side.lower() in ['buy', 'long'] else 1.05)
    
    def calculate_take_profit_price(self, entry_price: float, side: str, 
                                   stop_loss: float, ratio: float = None) -> float:
        """Calculate take profit price based on risk-reward ratio"""
        try:
            if ratio is None:
                ratio = self.risk_reward_ratio
            
            if side.lower() == 'buy':
                risk = abs(entry_price - stop_loss)
                take_profit = entry_price + (risk * ratio)
                max_tp = entry_price * (1 + self.tp_max_profit)
                take_profit = min(take_profit, max_tp)
            else:
                risk = abs(stop_loss - entry_price)
                take_profit = entry_price - (risk * ratio)
                min_tp = entry_price * (1 - self.tp_max_profit)
                take_profit = max(take_profit, min_tp)
            
            return take_profit
            
        except Exception as e:
            logging.error(f"Error calculating take profit: {e}")
            return entry_price * (1.05 if side.lower() == 'buy' else 0.95)
    
    def calculate_position_levels(self, market_data: MarketData, side: str, 
                                 confidence: float, balance: float) -> Optional[PositionLevels]:
        """
        Calculate complete position levels
        
        Returns:
            PositionLevels if valid, None if position would be too small
        """
        try:
            # 1. Fixed Margin
            margin = self.fixed_size
            
            # 2. Position Size
            notional_value = margin * LEVERAGE
            position_size = notional_value / market_data.price
            
            # 🛡️ SAFETY CHECK: Validate minimum IM before proceeding
            # For high-price assets (XAUT, ZEC), IM can be as low as $2
            # We need at least MIN_MARGIN to avoid unsafe tiny positions
            estimated_im = self._estimate_bybit_initial_margin(position_size, market_data.price, LEVERAGE)
            
            if estimated_im < self.min_margin:
                logging.warning(
                    f"⚠️ Position too small for {market_data.price:.2f} price asset: "
                    f"Est. IM ${estimated_im:.2f} < Min ${self.min_margin:.2f} - SKIPPING"
                )
                return None
            
            # 3. SL/TP
            stop_loss = self.calculate_stop_loss_fixed(market_data.price, side)
            take_profit = self.calculate_take_profit_price(market_data.price, side, stop_loss)
            
            # 4. Stats
            if side.lower() in ['buy', 'long']:
                risk_pct = ((market_data.price - stop_loss) / market_data.price) * 100
                reward_pct = ((take_profit - market_data.price) / market_data.price) * 100
            else:
                risk_pct = ((stop_loss - market_data.price) / market_data.price) * 100
                reward_pct = ((market_data.price - take_profit) / market_data.price) * 100
            
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
            return None  # Return None on error instead of fallback
    
    def _estimate_bybit_initial_margin(self, position_size: float, price: float, leverage: float) -> float:
        """
        Estimate what Bybit's Initial Margin will be for a given position
        
        Bybit IM calculation (simplified):
        IM = (Position Size × Price) / Leverage
        
        For small positions on expensive assets, IM can be very low.
        Example: 0.036 contracts of XAUT @ $4113 with 5x = ~$2 IM
        """
        try:
            notional = position_size * price
            estimated_im = notional / leverage
            return estimated_im
        except:
            return 0.0
    
    def validate_portfolio_margin(self, existing_margins: list, new_margin: float, 
                                 total_balance: float) -> Tuple[bool, str]:
        """Validate portfolio margin usage"""
        try:
            if new_margin > total_balance:
                return False, f"Insufficient available balance: ${new_margin:.2f} > ${total_balance:.2f}"
            
            if new_margin < self.min_margin:
                return False, f"Position too small: ${new_margin:.2f} < ${self.min_margin:.2f}"
            
            return True, "Portfolio margin approved"
            
        except Exception as e:
            logging.error(f"Portfolio validation error: {e}")
            return False, f"Validation error: {e}"

    def calculate_portfolio_based_margins(self, signals: list, available_balance: float, total_wallet: float = None) -> list:
        """
        🎯 FIXED ALLOCATION STRATEGY
        
        Allocates fixed size positions sequentially until balance is exhausted.
        
        Args:
            signals: List of trading signals
            available_balance: Available balance to allocate
            
        Returns:
            list: List of margin amounts
        """
        try:
            from config import MAX_CONCURRENT_POSITIONS
            
            n_signals_to_open = min(len(signals), MAX_CONCURRENT_POSITIONS)
            
            if n_signals_to_open == 0:
                return []
            
            fixed_margin = self.fixed_size
            margins = []
            current_avail = available_balance
            
            for i in range(n_signals_to_open):
                if current_avail >= fixed_margin:
                    margins.append(fixed_margin)
                    current_avail -= fixed_margin
                else:
                    # Not enough balance
                    logging.warning(f"⚠️ Not enough balance (${current_avail:.2f}) for fixed position #{i+1}")
                    break
            
            if not margins:
                logging.warning("⚠️ Insufficient balance to open ANY position")
                return []
                
            logging.info(f"🔒 FIXED SIZING: Allocated {len(margins)} positions of ${fixed_margin:.2f}")
            return margins
            
        except Exception as e:
            logging.error(f"Allocation failed: {e}")
            return []

    def calculate_adaptive_margins(self, signals, wallet_equity, max_positions=5):
        """Fallback for adaptive calls - redirects to fixed strategy"""
        return self._fallback_to_portfolio_sizing(signals, wallet_equity)
    
    def _fallback_to_portfolio_sizing(self, signals, wallet_equity):
        """Calculates fixed margins and creates stats dummy"""
        margins = self.calculate_portfolio_based_margins(signals, wallet_equity)
        symbols = [s.get('symbol', f'UNKNOWN_{i}') for i, s in enumerate(signals[:len(margins)])]
        stats = {'mode': 'FIXED'}
        return margins, symbols, stats

# Global risk calculator instance
global_risk_calculator = RiskCalculator()
