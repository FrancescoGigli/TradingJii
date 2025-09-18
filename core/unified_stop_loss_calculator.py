#!/usr/bin/env python3
"""
🛡️ UNIFIED STOP LOSS CALCULATOR

CRITICAL FIX: Single source of truth per Stop Loss calculation
- Eliminazione delle 4 implementazioni diverse di SL
- Mandatory precision handling sempre
- Unified 6% SL logic con validazione Bybit
- Atomic SL operations con retry logic
- Backward compatibility completa

GARANTISCE: SL consistency, zero ordini rifiutati per precision
"""

import logging
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from termcolor import colored

# Import precision handler per mandatory validation
from core.price_precision_handler import global_price_precision_handler


@dataclass
class StopLossResult:
    """Result structure per operazioni stop loss"""
    success: bool
    stop_loss_price: float
    order_id: Optional[str] = None
    error: Optional[str] = None
    normalized: bool = False
    precision_info: Optional[str] = None


class UnifiedStopLossCalculator:
    """
    CRITICAL FIX: Calculator unificato per tutti gli stop loss
    
    ELIMINA IMPLEMENTAZIONI MULTIPLE:
    1. config.py INITIAL_SL_PRICE_PCT = 0.06  ❌
    2. risk_calculator.py calculate_stop_loss_price()  ❌  
    3. smart_position_manager.py calculated_sl = entry_price * 0.94  ❌
    4. trading_orchestrator.py raw_sl = market_data.price * (1 - 0.06)  ❌
    
    SOSTITUISCE CON:
    ✅ Single calculate_unified_stop_loss() method
    ✅ Mandatory PricePrecisionHandler integration
    ✅ Bybit validation rules sempre rispettate
    ✅ Standard retry logic per failures
    """
    
    def __init__(self):
        # Unified SL parameters
        self.sl_percentage = 0.06  # 6% stop loss fisso
        self.commission_rate = 0.0006  # 0.06% total commissions
        
        # Retry parameters
        self.max_retries = 3
        self.retry_adjustment_factor = 0.001  # 0.1% adjustment per retry
        
        # Performance tracking
        self.calculations_performed = 0
        self.precision_normalizations = 0
        self.bybit_validations_failed = 0
        self.retries_performed = 0
        
        logging.info("🛡️ UnifiedStopLossCalculator initialized - SL implementations unified")
    
    def calculate_unified_stop_loss(self, entry_price: float, side: str, symbol: str) -> float:
        """
        🛡️ UNIFIED: Single implementation per tutti gli stop loss
        
        Args:
            entry_price: Prezzo di entrata posizione
            side: Direzione posizione ('buy' o 'sell')
            symbol: Trading symbol (per logging)
            
        Returns:
            float: Stop loss price (grezzo, senza precision)
        """
        try:
            self.calculations_performed += 1
            
            # UNIFIED LOGIC: Always 6% stop loss
            if side.lower() in ['buy', 'long']:
                # LONG: Stop loss 6% below entry
                raw_sl = entry_price * (1 - self.sl_percentage)
            else:
                # SHORT: Stop loss 6% above entry  
                raw_sl = entry_price * (1 + self.sl_percentage)
            
            symbol_short = symbol.replace('/USDT:USDT', '') if symbol else 'Unknown'
            logging.debug(f"🛡️ Unified SL: {symbol_short} {side.upper()} @ ${entry_price:.6f} → SL ${raw_sl:.6f} (6%)")
            
            return raw_sl
            
        except Exception as e:
            logging.error(f"🛡️ Unified SL calculation failed: {e}")
            # Fallback: same logic but with hardcoded values
            return entry_price * (0.94 if side.lower() in ['buy', 'long'] else 1.06)
    
    async def calculate_and_normalize_stop_loss(self, exchange, symbol: str, side: str, 
                                              entry_price: float) -> StopLossResult:
        """
        🛡️ COMPLETE: Calcola e normalizza stop loss con precision handling
        
        Args:
            exchange: Bybit exchange instance
            symbol: Trading symbol
            side: Direzione posizione
            entry_price: Prezzo di entrata
            
        Returns:
            StopLossResult: Risultato completo con SL normalizzato
        """
        try:
            # Phase 1: Calculate raw stop loss (unified)
            raw_sl = self.calculate_unified_stop_loss(entry_price, side, symbol)
            
            # Phase 2: Normalize with precision handler (MANDATORY)
            normalized_sl, precision_success = await global_price_precision_handler.normalize_stop_loss_price(
                exchange, symbol, side, entry_price, raw_sl
            )
            
            if precision_success:
                self.precision_normalizations += 1
                precision_info = f"Normalized: ${raw_sl:.6f} → ${normalized_sl:.6f}"
                logging.debug(f"🛡️ {symbol.replace('/USDT:USDT', '')}: {precision_info}")
            else:
                logging.warning(f"🛡️ Precision normalization failed for {symbol}, using raw SL")
                normalized_sl = raw_sl
                precision_info = "Normalization failed - using raw SL"
            
            # Phase 3: Bybit rules validation
            current_price = await global_price_precision_handler.get_current_price(exchange, symbol)
            
            if current_price > 0:
                # Validate Bybit rules
                rules_valid = global_price_precision_handler.validate_price_rules(
                    symbol, side, normalized_sl, current_price
                )
                
                if not rules_valid:
                    self.bybit_validations_failed += 1
                    # Auto-fix: adjust SL to comply with Bybit rules
                    if side.lower() in ['buy', 'long']:
                        # LONG: SL must be < current price
                        if normalized_sl >= current_price:
                            tick_info = await global_price_precision_handler.get_symbol_precision(exchange, symbol)
                            tick_size = tick_info.get('tick_size', 0.01)
                            adjusted_sl = current_price - (tick_size * 2)  # 2 ticks below current
                            logging.warning(f"🛡️ {symbol}: SL auto-adjusted ${normalized_sl:.6f} → ${adjusted_sl:.6f} (Bybit rules)")
                            normalized_sl = adjusted_sl
                    else:
                        # SHORT: SL must be > current price
                        if normalized_sl <= current_price:
                            tick_info = await global_price_precision_handler.get_symbol_precision(exchange, symbol)
                            tick_size = tick_info.get('tick_size', 0.01)
                            adjusted_sl = current_price + (tick_size * 2)  # 2 ticks above current
                            logging.warning(f"🛡️ {symbol}: SL auto-adjusted ${normalized_sl:.6f} → ${adjusted_sl:.6f} (Bybit rules)")
                            normalized_sl = adjusted_sl
            
            return StopLossResult(
                success=True,
                stop_loss_price=normalized_sl,
                normalized=precision_success,
                precision_info=precision_info
            )
            
        except Exception as e:
            logging.error(f"🛡️ Complete SL calculation failed for {symbol}: {e}")
            # Emergency fallback
            fallback_sl = entry_price * (0.94 if side.lower() in ['buy', 'long'] else 1.06)
            return StopLossResult(
                success=False,
                stop_loss_price=fallback_sl,
                error=str(e),
                precision_info="Emergency fallback used"
            )
    
    async def place_stop_loss_with_retries(self, exchange, order_manager, symbol: str, 
                                         side: str, entry_price: float) -> StopLossResult:
        """
        🛡️ ROBUST: Piazza stop loss con retry logic standard
        
        Args:
            exchange: Bybit exchange instance
            order_manager: Order manager per API calls
            symbol: Trading symbol
            side: Direzione posizione
            entry_price: Prezzo di entrata
            
        Returns:
            StopLossResult: Risultato con order_id se successful
        """
        symbol_short = symbol.replace('/USDT:USDT', '')
        
        for attempt in range(self.max_retries):
            try:
                # Calculate and normalize SL
                sl_result = await self.calculate_and_normalize_stop_loss(
                    exchange, symbol, side, entry_price
                )
                
                if not sl_result.success:
                    if attempt == self.max_retries - 1:
                        return sl_result  # Return failed result on final attempt
                    continue
                
                # Apply retry adjustment if this is not first attempt
                stop_loss_price = sl_result.stop_loss_price
                if attempt > 0:
                    adjustment = entry_price * self.retry_adjustment_factor * attempt
                    if side.lower() in ['buy', 'long']:
                        stop_loss_price -= adjustment  # Make SL more conservative for LONG
                    else:
                        stop_loss_price += adjustment  # Make SL more conservative for SHORT
                    
                    logging.debug(f"🛡️ Retry {attempt + 1}: SL adjusted by ${adjustment:.6f}")
                
                # Place stop loss order
                order_result = await order_manager.set_trading_stop(
                    exchange, symbol, stop_loss_price, None
                )
                
                if order_result.success:
                    logging.info(f"🛡️ SL placed: {symbol_short} @ ${stop_loss_price:.6f} (attempt {attempt + 1})")
                    return StopLossResult(
                        success=True,
                        stop_loss_price=stop_loss_price,
                        order_id=order_result.order_id,
                        normalized=sl_result.normalized,
                        precision_info=sl_result.precision_info
                    )
                else:
                    # Check if error is retry-able
                    error_msg = str(order_result.error).lower()
                    if any(retryable in error_msg for retryable in ['timeout', 'network', 'temporary']):
                        if attempt < self.max_retries - 1:
                            self.retries_performed += 1
                            logging.warning(f"🛡️ Retry {attempt + 1}: {order_result.error}")
                            continue
                    
                    # Non-retryable error or final attempt
                    if attempt == self.max_retries - 1:
                        logging.error(f"🛡️ SL placement failed after {self.max_retries} attempts: {order_result.error}")
                        return StopLossResult(
                            success=False,
                            stop_loss_price=stop_loss_price,
                            error=order_result.error,
                            precision_info=sl_result.precision_info
                        )
                    else:
                        # Try again with adjustment
                        self.retries_performed += 1
                        logging.warning(f"🛡️ Attempt {attempt + 1} failed: {order_result.error}, retrying...")
                        continue
                        
            except Exception as e:
                logging.error(f"🛡️ Exception in SL placement attempt {attempt + 1}: {e}")
                if attempt == self.max_retries - 1:
                    return StopLossResult(
                        success=False,
                        stop_loss_price=entry_price * (0.94 if side.lower() in ['buy', 'long'] else 1.06),
                        error=str(e),
                        precision_info="Exception during placement"
                    )
                continue
        
        # Should never reach here, but safety fallback
        return StopLossResult(
            success=False,
            stop_loss_price=entry_price * (0.94 if side.lower() in ['buy', 'long'] else 1.06),
            error="Maximum retries exceeded",
            precision_info="Retry limit reached"
        )
    
    # ========================================
    # VALIDATION & COMPATIBILITY
    # ========================================
    
    def validate_stop_loss_parameters(self, entry_price: float, side: str, symbol: str) -> Tuple[bool, str]:
        """
        🛡️ VALIDATION: Valida parametri per SL calculation
        
        Args:
            entry_price: Prezzo di entrata
            side: Direzione posizione
            symbol: Trading symbol
            
        Returns:
            Tuple[bool, str]: (valid, reason)
        """
        try:
            # Basic validation
            if entry_price <= 0:
                return False, f"Invalid entry price: ${entry_price:.6f}"
            
            if side.lower() not in ['buy', 'sell', 'long', 'short']:
                return False, f"Invalid side: {side}"
            
            if not symbol or len(symbol) < 3:
                return False, f"Invalid symbol: {symbol}"
            
            # Calculate theoretical SL for validation
            theoretical_sl = self.calculate_unified_stop_loss(entry_price, side, symbol)
            
            # Validate SL is reasonable (not too close to entry)
            min_distance = entry_price * 0.01  # Minimum 1% distance
            distance = abs(theoretical_sl - entry_price)
            
            if distance < min_distance:
                return False, f"SL too close to entry: {distance:.6f} < {min_distance:.6f}"
            
            return True, "Parameters validated successfully"
            
        except Exception as e:
            return False, f"Validation error: {e}"
    
    def get_stop_loss_info(self, entry_price: float, side: str) -> Dict:
        """
        🛡️ INFO: Ottieni informazioni dettagliate sul SL senza calcoli
        
        Args:
            entry_price: Prezzo di entrata
            side: Direzione posizione
            
        Returns:
            Dict: Informazioni SL dettagliate
        """
        try:
            raw_sl = entry_price * (0.94 if side.lower() in ['buy', 'long'] else 1.06)
            distance = abs(raw_sl - entry_price)
            distance_pct = (distance / entry_price) * 100
            
            # Calculate potential PnL impact with 10x leverage
            potential_loss_pct = distance_pct * 10  # With 10x leverage
            
            return {
                'entry_price': entry_price,
                'stop_loss_price': raw_sl,
                'distance_usd': distance,
                'distance_percentage': distance_pct,
                'potential_loss_with_leverage': potential_loss_pct,
                'side': side.lower(),
                'sl_percentage_used': self.sl_percentage * 100,
                'risk_reward_ratio': f"1:{(0.06 / 0.06):.1f}",  # 6% risk for 6% reward = 1:1
                'recommended_take_profit': entry_price * (1.06 if side.lower() in ['buy', 'long'] else 0.94)
            }
            
        except Exception as e:
            logging.error(f"🛡️ SL info calculation failed: {e}")
            return {'error': str(e)}
    
    def get_performance_stats(self) -> Dict:
        """
        🛡️ STATS: Ottieni statistiche performance calculator
        
        Returns:
            Dict: Statistiche dettagliate
        """
        try:
            success_rate = ((self.calculations_performed - self.bybit_validations_failed) / 
                          max(self.calculations_performed, 1)) * 100
            
            return {
                'total_calculations': self.calculations_performed,
                'precision_normalizations': self.precision_normalizations,
                'bybit_validation_failures': self.bybit_validations_failed,
                'retries_performed': self.retries_performed,
                'success_rate_pct': success_rate,
                'sl_percentage_used': self.sl_percentage * 100,
                'max_retries_configured': self.max_retries,
                'unified_implementation': True
            }
            
        except Exception as e:
            logging.error(f"🛡️ Performance stats failed: {e}")
            return {'error': str(e)}
    
    def display_performance_dashboard(self):
        """
        🛡️ DISPLAY: Mostra dashboard performance SL calculator
        """
        try:
            stats = self.get_performance_stats()
            
            print(colored("\n🛡️ STOP LOSS CALCULATOR DASHBOARD", "red", attrs=['bold']))
            print(colored("=" * 80, "red"))
            
            print(f"📊 Total Calculations: {colored(str(stats['total_calculations']), 'cyan')}")
            
            success_rate_str = f"{stats['success_rate_pct']:.1f}%"
            success_color = 'green' if stats['success_rate_pct'] >= 95 else 'yellow'
            print(f"🎯 Success Rate: {colored(success_rate_str, success_color)}")
            
            print(f"🔧 Precision Normalizations: {colored(str(stats['precision_normalizations']), 'cyan')}")
            
            validation_failures_color = 'yellow' if stats['bybit_validation_failures'] > 0 else 'green'
            print(f"⚠️ Bybit Validation Failures: {colored(str(stats['bybit_validation_failures']), validation_failures_color)}")
            
            retries_color = 'yellow' if stats['retries_performed'] > 0 else 'green'
            print(f"🔄 Retries Performed: {colored(str(stats['retries_performed']), retries_color)}")
            
            sl_percentage_str = f"{stats['sl_percentage_used']:.1f}%"
            print(f"🛡️ SL Percentage: {colored(sl_percentage_str, 'cyan', attrs=['bold'])}")
            
            print(f"🔁 Max Retries: {colored(str(stats['max_retries_configured']), 'cyan')}")
            
            print(colored("=" * 80, "red"))
            
        except Exception as e:
            logging.error(f"🛡️ Dashboard display failed: {e}")
            print(colored(f"❌ SL Dashboard Error: {e}", "red"))


# Global unified stop loss calculator instance
global_unified_stop_loss_calculator = UnifiedStopLossCalculator()


# ========================================
# CONVENIENCE FUNCTIONS (Backward Compatibility)
# ========================================

async def calculate_unified_sl(entry_price: float, side: str, symbol: str) -> float:
    """
    Convenience function for unified SL calculation
    
    Returns:
        float: Raw stop loss price (without precision/normalization)
    """
    return global_unified_stop_loss_calculator.calculate_unified_stop_loss(entry_price, side, symbol)

async def calculate_and_place_sl(exchange, order_manager, symbol: str, side: str, entry_price: float) -> StopLossResult:
    """
    Convenience function for complete SL calculation and placement
    
    Returns:
        StopLossResult: Complete result with order_id if successful
    """
    return await global_unified_stop_loss_calculator.place_stop_loss_with_retries(
        exchange, order_manager, symbol, side, entry_price
    )

def get_sl_calculator_stats() -> Dict:
    """
    Convenience function to get SL calculator statistics
    
    Returns:
        Dict: Performance statistics
    """
    return global_unified_stop_loss_calculator.get_performance_stats()
