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
from typing import Tuple, Dict, Optional, List
from dataclasses import dataclass
from termcolor import colored
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
        
    def calculate_dynamic_position_sizes(self, available_balance: float) -> Tuple[float, float, float]:
        """
        🎯 DYNAMIC: Calcola position sizes in base al balance disponibile
        
        GARANTISCE: Sempre almeno 8 posizioni aggressive possibili
        SCALA: Automaticamente con crescita/decrescita balance
        
        Args:
            available_balance: Balance USDT disponibile per trading
            
        Returns:
            Tuple[float, float, float]: (conservative, moderate, aggressive)
        """
        try:
            from config import (
                POSITION_SIZING_TARGET_POSITIONS,
                POSITION_SIZING_RATIO_CONSERVATIVE,
                POSITION_SIZING_RATIO_MODERATE,
                POSITION_SIZING_RATIO_AGGRESSIVE,
                POSITION_SIZE_MIN_ABSOLUTE,
                POSITION_SIZE_MAX_ABSOLUTE
            )
            
            # 1. Calcola aggressive size (base per gli altri)
            # Dividi balance per target positions per garantire almeno N posizioni
            aggressive = available_balance / POSITION_SIZING_TARGET_POSITIONS
            
            # 2. Calcola gli altri tier mantenendo i ratios
            moderate = aggressive * POSITION_SIZING_RATIO_MODERATE
            conservative = aggressive * POSITION_SIZING_RATIO_CONSERVATIVE
            
            # 3. Applica limiti di sicurezza
            conservative = max(POSITION_SIZE_MIN_ABSOLUTE, 
                              min(POSITION_SIZE_MAX_ABSOLUTE, conservative))
            moderate = max(POSITION_SIZE_MIN_ABSOLUTE, 
                          min(POSITION_SIZE_MAX_ABSOLUTE, moderate))
            aggressive = max(POSITION_SIZE_MIN_ABSOLUTE, 
                            min(POSITION_SIZE_MAX_ABSOLUTE, aggressive))
            
            # 4. Log per debugging
            logging.debug(
                f"💰 Dynamic Sizing: Balance ${available_balance:.2f} → "
                f"C: ${conservative:.2f}, M: ${moderate:.2f}, A: ${aggressive:.2f}"
            )
            
            return conservative, moderate, aggressive
            
        except Exception as e:
            logging.error(f"Dynamic position sizing failed: {e}")
            # Fallback a valori fissi da config
            return (self.position_conservative, 
                    self.position_moderate, 
                    self.position_aggressive)
    
    def calculate_intelligent_position_size(self, confidence: float, atr_pct: float, 
                                           adx: float = 0.0, 
                                           available_balance: float = 1000.0) -> float:
        """
        🎯 INTELLIGENT 3-TIER con DYNAMIC SCALING
        
        Determina intelligentemente la size della posizione basandosi su:
        - Confidence del segnale ML
        - Volatilità del mercato (ATR)
        - Forza del trend (ADX)
        - Balance disponibile (DYNAMIC)
        
        Args:
            confidence: ML confidence (0-1)
            atr_pct: ATR as percentage
            adx: Trend strength (ADX indicator)
            available_balance: Balance disponibile per scaling dinamico
        
        Returns:
            float: Position size dinamica in USD
        """
        try:
            # 1. DYNAMIC: Calcola sizes basate su balance attuale
            conservative, moderate, aggressive = self.calculate_dynamic_position_sizes(
                available_balance
            )
            
            # 2. Score factors (0-3 points)
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
            
            # 3. Seleziona tier in base allo score (DYNAMIC sizes)
            if score >= 2.5:
                position_size = aggressive
                tier = "AGGRESSIVE"
            elif score >= 1.5:
                position_size = moderate
                tier = "MODERATE"
            else:
                position_size = conservative
                tier = "CONSERVATIVE"
            
            # 4. Log aggiornato con dynamic values
            logging.info(
                f"💰 POSITION SIZING: ${position_size:.2f} USD ({tier})\n"
                f"   📊 Score: {score:.1f}/3.0\n"
                f"   💵 Balance-Scaled: C=${conservative:.0f}, M=${moderate:.0f}, A=${aggressive:.0f}\n"
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
        Calculate dynamic margin using intelligent 3-tier system with balance scaling
        
        Args:
            atr_pct: ATR as percentage of price
            confidence: ML signal confidence (0-1)
            volatility: Market volatility (legacy, not used)
            balance: Account balance (for dynamic scaling and safety checks)
            adx: Trend strength (ADX indicator)
            
        Returns:
            float: Dynamic margin amount (scales with balance)
        """
        try:
            # Use intelligent 3-tier position sizing with dynamic balance scaling
            position_size = self.calculate_intelligent_position_size(
                confidence, atr_pct, adx, available_balance=balance
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
    
    def calculate_stop_loss_fixed(self, entry_price: float, side: str) -> float:
        """
        🛡️ FIXED STOP LOSS: -5% contro posizione
        
        Calcola stop loss fisso al 5% dal prezzo di entrata:
        - LONG: SL = entry × 0.95 (-5%)
        - SHORT: SL = entry × 1.05 (+5%)
        
        Con leva 10x: -5% prezzo = -50% margin
        
        Args:
            entry_price: Prezzo di entrata posizione
            side: Direzione posizione ('buy'/'long' o 'sell'/'short')
            
        Returns:
            float: Prezzo stop loss
        """
        try:
            from config import SL_FIXED_PCT
            
            if side.lower() in ['buy', 'long']:
                # LONG: Stop loss sotto entry (-5%)
                stop_loss = entry_price * (1 - SL_FIXED_PCT)
            else:  # SELL/SHORT
                # SHORT: Stop loss sopra entry (+5%)
                stop_loss = entry_price * (1 + SL_FIXED_PCT)
            
            logging.debug(
                f"🛡️ Fixed SL: Entry ${entry_price:.6f} | "
                f"Side {side.upper()} | SL ${stop_loss:.6f} "
                f"({'-' if side.lower() in ['buy', 'long'] else '+'}5%)"
            )
            
            return stop_loss
            
        except Exception as e:
            logging.error(f"Error calculating fixed stop loss: {e}")
            # Safe fallback
            return entry_price * (0.95 if side.lower() in ['buy', 'long'] else 1.05)
    
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
        
        NOTE: Margin will be overridden by portfolio-based sizing in trading_engine
        This is just for fallback calculations
        
        Args:
            market_data: Market data (price, ATR, volatility)
            side: Position side
            confidence: ML confidence
            balance: Account balance
            
        Returns:
            PositionLevels: Complete position setup data
        """
        try:
            # 1. Calculate dynamic margin (will be overridden by portfolio sizing)
            atr_pct = (market_data.atr / market_data.price) * 100
            margin = self.calculate_dynamic_margin(
                atr_pct, confidence, market_data.volatility, balance, market_data.adx
            )
            
            # 2. Calculate position size
            notional_value = margin * LEVERAGE
            position_size = notional_value / market_data.price
            
            # 3. FIX: Use correct stop loss function (-5% = -50% margin with 10x)
            stop_loss = self.calculate_stop_loss_fixed(market_data.price, side)
            
            # 4. Calculate take profit
            take_profit = self.calculate_take_profit_price(market_data.price, side, stop_loss)
            
            # 5. Calculate percentages with CORRECT -5% SL
            if side.lower() in ['buy', 'long']:
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
            # CRITICAL FIX: Fallback with correct -5% SL
            fallback_margin = self.base_margin
            fallback_notional = fallback_margin * LEVERAGE
            
            # Use correct -5% SL function
            fallback_sl = self.calculate_stop_loss_fixed(market_data.price, side)
            
            return PositionLevels(
                margin=fallback_margin,
                position_size=fallback_notional / market_data.price,
                stop_loss=fallback_sl,
                take_profit=market_data.price * (1.10 if side.lower() in ['buy', 'long'] else 0.90),
                risk_pct=5.0,  # Correct: 5% price with -5% SL
                reward_pct=10.0,
                risk_reward_ratio=2.0
            )
    
    def validate_portfolio_margin(self, existing_margins: list, new_margin: float, 
                                 total_balance: float) -> Tuple[bool, str]:
        """
        Validate portfolio margin usage
        
        Args:
            existing_margins: List of existing position margins (IGNORED if total_balance is available balance)
            new_margin: New position margin to add
            total_balance: AVAILABLE balance (already net of existing positions)
            
        Returns:
            Tuple[bool, str]: (approved, reason)
        """
        try:
            # FIX: Don't double-count! If balance is already "available", 
            # just check if new_margin fits within it
            # (existing_margins are already deducted from total_balance)
            
            if new_margin > total_balance:
                return False, f"Insufficient available balance: ${new_margin:.2f} > ${total_balance:.2f}"
            
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

    def calculate_portfolio_based_margins(self, signals: list, available_balance: float, total_wallet: float = None) -> list:
        """
        🎯 RISK-WEIGHTED POSITION SIZING
        
        Sistema DINAMICO che pesa le posizioni in base a:
        - Confidence del modello ML (più alta = più margin)
        - Rischio/Volatilità (più basso = più margin)
        - Usa TUTTO il balance disponibile
        
        Formula: Peso posizione = f(confidence, volatility, adx)
        Margin posizione = (peso / somma_pesi) × available_balance
        
        Args:
            signals: Lista segnali con confidence, atr, volatility, adx
            available_balance: Balance DISPONIBILE (già netto delle posizioni aperte)
            total_wallet: Wallet TOTALE (non usato, kept for compatibility)
            
        Returns:
            list: Lista di margin amounts per ogni segnale (pesati per rischio)
        """
        try:
            from config import MAX_CONCURRENT_POSITIONS
            
            # 1. Calcola quanti slot abbiamo per nuove posizioni
            n_signals_to_open = min(len(signals), MAX_CONCURRENT_POSITIONS)
            
            if n_signals_to_open == 0:
                logging.warning("⚠️ No signals to open")
                return []
            
            # 2. CALCOLA PESI DINAMICI per ogni segnale
            weights = []
            for i, signal in enumerate(signals[:n_signals_to_open]):
                # Estrai dati segnale
                confidence = signal.get('confidence', 0.7)
                atr = signal.get('atr', 0)
                price = signal.get('price', 1)
                volatility = signal.get('volatility', 0.03)
                adx = signal.get('adx', 0)
                
                # Calculate ATR percentage
                atr_pct = (atr / price * 100) if price > 0 else 3.0
                
                # PESO = f(confidence, volatility, trend_strength)
                # Range: 0.5 - 2.0
                
                # Factor 1: Confidence (peso base 0.5-1.5)
                confidence_weight = 0.5 + (confidence * 1.0)  # 0.5 per 0%, 1.5 per 100%
                
                # Factor 2: Volatility (inverso: bassa vol = più peso)
                # High volatility (>4%) = 0.7x, Low volatility (<2%) = 1.3x
                if atr_pct < 2.0:  # Low volatility
                    volatility_multiplier = 1.3
                elif atr_pct > 4.0:  # High volatility
                    volatility_multiplier = 0.7
                else:  # Medium volatility
                    volatility_multiplier = 1.0
                
                # Factor 3: Trend strength (ADX bonus)
                # Strong trend (ADX ≥25) = 1.2x, Weak trend = 1.0x
                trend_multiplier = 1.2 if adx >= 25 else 1.0
                
                # Peso finale
                weight = confidence_weight * volatility_multiplier * trend_multiplier
                
                # Clamp weight between 0.5 and 2.0
                weight = max(0.5, min(2.0, weight))
                
                weights.append(weight)
                
                logging.debug(
                    f"📊 Signal {i+1}/{n_signals_to_open}: "
                    f"Conf={confidence:.1%}, Vol={atr_pct:.1f}%, ADX={adx:.1f} → Weight={weight:.2f}"
                )
            
            # 3. NORMALIZZA PESI e CALCOLA MARGINS
            total_weight = sum(weights)
            margins = []
            
            for i, weight in enumerate(weights):
                # Margin proporzionale al peso
                margin = (weight / total_weight) * available_balance
                margins.append(margin)
            
            # 4. Applica limiti di sicurezza
            from config import POSITION_SIZE_MIN_ABSOLUTE, POSITION_SIZE_MAX_ABSOLUTE
            
            margins_safe = []
            for i, margin in enumerate(margins):
                signal = signals[i]
                # Clip tra min e max
                safe_margin = max(POSITION_SIZE_MIN_ABSOLUTE, 
                                 min(POSITION_SIZE_MAX_ABSOLUTE, margin))
                margins_safe.append(safe_margin)
                
                if safe_margin != margin:
                    logging.warning(
                        f"⚠️ Position {i+1} ({signal.get('symbol', 'N/A')}) margin adjusted: "
                        f"${margin:.2f} → ${safe_margin:.2f} "
                        f"(limits: ${POSITION_SIZE_MIN_ABSOLUTE}-${POSITION_SIZE_MAX_ABSOLUTE})"
                    )
            
            total_used = sum(margins_safe)
            utilization_pct = (total_used / available_balance) * 100 if available_balance > 0 else 0
            
            # 5. Log summary dettagliato
            logging.info(colored(
                f"💰 RISK-WEIGHTED POSITION SIZING:\n"
                f"   Available Balance: ${available_balance:.2f}\n"
                f"   Positions to open: {n_signals_to_open}\n"
                f"   Total Weight: {total_weight:.2f}\n"
                f"   Total Allocated: ${total_used:.2f} ({utilization_pct:.1f}%)\n"
                f"   Remaining: ${available_balance - total_used:.2f}",
                "cyan", attrs=['bold']
            ))
            
            # Log individual margins
            for i, (margin, weight) in enumerate(zip(margins_safe, weights)):
                signal = signals[i]
                symbol = signal.get('symbol', 'N/A').replace('/USDT:USDT', '')
                confidence = signal.get('confidence', 0)
                pct_of_total = (margin / total_used * 100) if total_used > 0 else 0
                
                logging.info(
                    f"   #{i+1} {symbol}: ${margin:.2f} ({pct_of_total:.1f}%) | "
                    f"Weight={weight:.2f}, Conf={confidence:.0%}"
                )
            
            return margins_safe
            
        except Exception as e:
            logging.error(f"Risk-weighted sizing failed: {e}")
            import traceback
            logging.error(traceback.format_exc())
            # Fallback: divide equally
            fallback_margin = available_balance / max(1, len(signals))
            return [fallback_margin] * len(signals)

    def calculate_adaptive_margins(
        self,
        signals: List[dict],
        wallet_equity: float,
        max_positions: int = 5
    ) -> Tuple[List[float], List[str], Dict]:
        """
        Calculate adaptive margins using AdaptivePositionSizing system
        
        This method integrates with the new adaptive sizing system that:
        - Learns from symbol performance
        - Rewards winners with larger sizes
        - Punishes losers with blocks
        
        Args:
            signals: List of trading signals
            wallet_equity: Total wallet equity (available balance)
            max_positions: Maximum concurrent positions
            
        Returns:
            Tuple[List[float], List[str], Dict]: (margins, symbols, stats)
        """
        try:
            # Import adaptive sizing
            from core.adaptive_position_sizing import global_adaptive_sizing
            
            if global_adaptive_sizing is None:
                logging.error("❌ Adaptive sizing not initialized - falling back to portfolio sizing")
                # Fallback to portfolio-based sizing
                return self._fallback_to_portfolio_sizing(signals, wallet_equity)
            
            # Use adaptive sizing system
            margins, symbols, stats = global_adaptive_sizing.calculate_adaptive_margins(
                signals, wallet_equity, max_positions
            )
            
            return margins, symbols, stats
            
        except Exception as e:
            logging.error(f"❌ Error in adaptive margins: {e}")
            import traceback
            logging.error(traceback.format_exc())
            # Fallback to portfolio sizing
            return self._fallback_to_portfolio_sizing(signals, wallet_equity)
    
    def _fallback_to_portfolio_sizing(
        self,
        signals: List[dict],
        wallet_equity: float
    ) -> Tuple[List[float], List[str], Dict]:
        """
        Fallback to legacy portfolio-based sizing
        
        Args:
            signals: List of trading signals
            wallet_equity: Total wallet equity
            
        Returns:
            Tuple[List[float], List[str], Dict]: (margins, symbols, stats)
        """
        logging.warning("⚠️ Using fallback portfolio sizing")
        
        # Use legacy portfolio-based margins
        margins = self.calculate_portfolio_based_margins(
            signals, wallet_equity, total_wallet=wallet_equity
        )
        
        # Extract symbols
        symbols = [s.get('symbol', f'UNKNOWN_{i}') for i, s in enumerate(signals[:len(margins)])]
        
        # Build stats
        stats = {
            'total_signals': len(signals),
            'positions_opened': len(margins),
            'total_margin': sum(margins),
            'max_loss': sum(margins) * 0.30,  # 30% loss multiplier
            'risk_pct': (sum(margins) * 0.30 / wallet_equity * 100) if wallet_equity > 0 else 0,
            'fallback': True
        }
        
        return margins, symbols, stats

# Global risk calculator instance
global_risk_calculator = RiskCalculator()
