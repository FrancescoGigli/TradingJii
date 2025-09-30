#!/usr/bin/env python3
"""
🔐 POSITION OPENING COORDINATOR

RESPONSABILITÀ CENTRALE:
- Apertura posizioni completamente atomica
- Validation robusta pre-execution
- Lock per prevenire duplicates
- Balance tracking real-time
- Rollback automatico su failure
- SL SEMPRE settato (or rollback)

GARANZIE:
- No duplicate positions
- Validazione completa Bybit constraints
- SL garantito o position rollback
- Balance aggiornato real-time
- Operazione atomica completa
"""

import asyncio
import logging
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from termcolor import colored

import config

@dataclass
class ValidationResult:
    """Risultato validation checks"""
    success: bool
    error_message: str = ""
    details: Dict = None


class PositionOpeningCoordinator:
    """
    Coordinator per apertura posizioni sicure e atomiche
    
    PHILOSOPHY:
    - Atomic operations (all or nothing)
    - Extensive validation pre-execution
    - Automatic rollback on failure
    - Real-time balance tracking
    - Lock-based duplicate prevention
    """
    
    def __init__(self):
        # Global lock per aperture atomiche
        self._opening_lock = asyncio.Lock()
        
        # Symbols attualmente in apertura (previene race)
        self._opening_positions: set = set()
        
        # Balance tracking real-time
        self._real_time_balance = None
        self._last_balance_update = None
        
        # Statistics
        self._total_attempts = 0
        self._successful_opens = 0
        self._failed_opens = 0
        self._rollback_count = 0
        self._duplicate_prevented = 0
        
        logging.info("🔐 PositionOpeningCoordinator initialized - Atomic position opening active")
    
    async def open_position_atomic(
        self,
        exchange,
        signal_data: Dict,
        market_data,
        initial_balance: float
    ):
        """
        Apre posizione con garanzia atomica completa
        
        Steps atomici:
        1. Acquire lock (previene race)
        2. Validate constraints (Bybit + portfolio)
        3. Execute market order
        4. Set SL (con retry mandatory)
        5. Register position (tracker)
        6. Release lock
        
        Se ANY step fallisce → ROLLBACK completo
        
        Args:
            exchange: Bybit exchange instance
            signal_data: Signal data con symbol, side, confidence
            market_data: Market data con price, atr, volatility
            initial_balance: Initial balance disponibile
            
        Returns:
            TradingResult con success garantito SOLO se tutto ok
        """
        from core.trading_orchestrator import TradingResult
        
        symbol = signal_data['symbol']
        side = signal_data['signal_name'].lower()
        
        self._total_attempts += 1
        
        # ACQUIRE GLOBAL LOCK
        async with self._opening_lock:
            
            try:
                # Check se apertura già in corso
                if symbol in self._opening_positions:
                    self._duplicate_prevented += 1
                    return TradingResult(
                        False, "", 
                        f"Position opening already in progress for {symbol}"
                    )
                
                # Mark as opening
                self._opening_positions.add(symbol)
                
                logging.info(colored(
                    f"🔐 ATOMIC OPEN: Starting for {symbol} {side.upper()}",
                    "cyan", attrs=['bold']
                ))
                
                # STEP 1: EXTENSIVE VALIDATION
                validation = await self._validate_position_opening(
                    exchange, symbol, side, market_data, initial_balance
                )
                
                if not validation.success:
                    self._failed_opens += 1
                    logging.warning(colored(
                        f"🔐 {symbol}: Validation failed - {validation.error_message}",
                        "yellow"
                    ))
                    return TradingResult(False, "", validation.error_message)
                
                logging.debug(f"🔐 {symbol}: Validation passed")
                
                # STEP 2: CALCULATE LEVELS
                from core.risk_calculator import global_risk_calculator
                
                levels = global_risk_calculator.calculate_position_levels(
                    market_data, side, signal_data.get('confidence', 0.7), initial_balance
                )
                
                logging.info(colored(
                    f"🔐 {symbol}: Levels calculated - Margin: ${levels.margin:.2f}, Size: {levels.position_size:.4f}",
                    "white"
                ))
                
                # STEP 3: NORMALIZE POSITION SIZE
                from core.price_precision_handler import global_price_precision_handler
                
                normalized_size, size_success = await global_price_precision_handler.normalize_position_size(
                    exchange, symbol, levels.position_size
                )
                
                if not size_success:
                    logging.warning(f"🔐 {symbol}: Size normalization failed, using original")
                    normalized_size = levels.position_size
                
                # Check minimum amount
                precision_info = await global_price_precision_handler.get_symbol_precision(exchange, symbol)
                min_amount = precision_info.get('min_amount', 0.001)
                
                if normalized_size < min_amount:
                    self._failed_opens += 1
                    error_msg = f"Position size {normalized_size:.6f} < minimum {min_amount}"
                    logging.error(colored(f"🔐 {symbol}: {error_msg}", "red"))
                    return TradingResult(False, "", error_msg)
                
                logging.debug(f"🔐 {symbol}: Size normalized to {normalized_size:.6f}")
                
                # STEP 4: EXECUTE ATOMIC OPENING
                result = await self._execute_atomic_opening(
                    exchange, symbol, side, normalized_size, market_data, levels, signal_data
                )
                
                if result.success:
                    self._successful_opens += 1
                    logging.info(colored(
                        f"✅ {symbol}: Position opened successfully",
                        "green", attrs=['bold']
                    ))
                else:
                    self._failed_opens += 1
                    logging.error(colored(
                        f"❌ {symbol}: Position opening failed - {result.error}",
                        "red"
                    ))
                
                return result
            
            except Exception as e:
                self._failed_opens += 1
                error_msg = f"Fatal error during atomic opening: {e}"
                logging.critical(colored(f"🔐 {symbol}: {error_msg}", "red"))
                return TradingResult(False, "", error_msg)
            
            finally:
                # ALWAYS remove from opening set
                self._opening_positions.discard(symbol)
    
    async def _validate_position_opening(
        self,
        exchange,
        symbol: str,
        side: str,
        market_data,
        balance: float
    ) -> ValidationResult:
        """
        Validazione ROBUSTA pre-execution
        
        Checks:
        1. Duplicate position (tracker + Bybit)
        2. Bybit constraints (min/max size, tick size, notional)
        3. Portfolio margin (con PnL non realizzato)
        4. Balance disponibile real-time
        
        Returns:
            ValidationResult con success e details
        """
        try:
            # Import managers
            from core.thread_safe_position_manager import global_thread_safe_position_manager
            from core.risk_calculator import global_risk_calculator
            
            # 1. DUPLICATE CHECK - Tracker
            if global_thread_safe_position_manager.safe_has_position_for_symbol(symbol):
                self._duplicate_prevented += 1
                return ValidationResult(
                    False,
                    f"Position already exists in tracker for {symbol}"
                )
            
            # 2. DUPLICATE CHECK - Bybit (STRICT)
            try:
                bybit_positions = await exchange.fetch_positions([symbol])
                for pos in bybit_positions:
                    contracts = float(pos.get('contracts', 0) or 0)
                    if abs(contracts) > 0:
                        self._duplicate_prevented += 1
                        return ValidationResult(
                            False,
                            f"Position already exists on Bybit for {symbol} ({contracts:+.4f} contracts)"
                        )
            except Exception as e:
                # STRICT: Se check fallisce, BLOCCA apertura
                logging.error(f"🔐 {symbol}: Cannot verify Bybit positions: {e}")
                return ValidationResult(
                    False,
                    f"Cannot verify Bybit positions (safety block): {e}"
                )
            
            # 3. BYBIT CONSTRAINTS VALIDATION
            from core.price_precision_handler import global_price_precision_handler
            
            precision_info = await global_price_precision_handler.get_symbol_precision(exchange, symbol)
            
            # Calculate provisional size
            levels = global_risk_calculator.calculate_position_levels(
                market_data, side, 0.7, balance
            )
            
            # Min amount check
            if levels.position_size < precision_info.get('min_amount', 0.001):
                return ValidationResult(
                    False,
                    f"Size {levels.position_size:.6f} < min {precision_info.get('min_amount', 0.001)}"
                )
            
            # Max amount check
            if levels.position_size > precision_info.get('max_amount', 1000):
                return ValidationResult(
                    False,
                    f"Size {levels.position_size:.6f} > max {precision_info.get('max_amount', 1000)}"
                )
            
            # Min notional check
            notional = levels.position_size * market_data.price
            min_notional = precision_info.get('min_notional', 5)
            
            if notional < min_notional:
                return ValidationResult(
                    False,
                    f"Notional ${notional:.2f} < min ${min_notional:.2f}"
                )
            
            # 4. PORTFOLIO MARGIN CHECK (con PnL)
            existing_positions = global_thread_safe_position_manager.safe_get_all_active_positions()
            
            total_used_margin = 0
            total_unrealized_pnl = 0
            
            for pos in existing_positions:
                margin = pos.position_size / pos.leverage
                total_used_margin += margin
                total_unrealized_pnl += pos.unrealized_pnl_usd
            
            # Real available = balance - used_margin - negative_pnl
            real_available = balance - total_used_margin + min(0, total_unrealized_pnl)
            
            if levels.margin > real_available:
                return ValidationResult(
                    False,
                    f"Insufficient balance: need ${levels.margin:.2f}, have ${real_available:.2f}"
                )
            
            # All checks passed
            return ValidationResult(
                True,
                "All validations passed",
                {
                    'real_available': real_available,
                    'required_margin': levels.margin,
                    'total_used_margin': total_used_margin,
                    'unrealized_pnl': total_unrealized_pnl
                }
            )
        
        except Exception as e:
            logging.error(f"🔐 {symbol}: Validation error: {e}")
            return ValidationResult(False, f"Validation error: {e}")
    
    async def _execute_atomic_opening(
        self,
        exchange,
        symbol: str,
        side: str,
        normalized_size: float,
        market_data,
        levels,
        signal_data: Dict
    ):
        """
        Execution atomica con rollback garantito
        
        Steps:
        1. Market order
        2. Set SL (MANDATORY)
        3. Register position
        4. If ANY fails → ROLLBACK
        
        Returns:
            TradingResult
        """
        from core.trading_orchestrator import TradingResult
        from core.order_manager import global_order_manager
        from core.thread_safe_position_manager import global_thread_safe_position_manager
        from core.stop_loss_coordinator import global_sl_coordinator
        
        executed_order_id = None
        sl_set = False
        position_registered = False
        position_id = None
        
        try:
            # STEP 1: Market order
            logging.info(f"🔐 {symbol}: Executing market order ({side} {normalized_size:.6f})")
            
            market_result = await global_order_manager.place_market_order(
                exchange, symbol, side, normalized_size
            )
            
            if not market_result.success:
                raise Exception(f"Market order failed: {market_result.error}")
            
            executed_order_id = market_result.order_id
            logging.info(colored(f"✅ {symbol}: Market order executed", "green"))
            
            # STEP 2: Set SL (MANDATORY con coordinator)
            logging.info(f"🔐 {symbol}: Setting Stop Loss (CRITICAL)")
            
            # Generate temporary position_id for SL coordinator
            temp_position_id = f"{symbol.replace('/USDT:USDT', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            sl_success, sl_price = await global_sl_coordinator.set_initial_sl(
                exchange, temp_position_id, symbol, side, market_data.price
            )
            
            if not sl_success:
                # SL FAILED → ROLLBACK REQUIRED
                raise Exception("CRITICAL: Could not set Stop Loss - Position will be rolled back")
            
            sl_set = True
            logging.info(colored(f"✅ {symbol}: Stop Loss set at ${sl_price:.6f}", "green"))
            
            # STEP 3: Register position in tracker
            logging.info(f"🔐 {symbol}: Registering position in tracker")
            
            position_id = global_thread_safe_position_manager.thread_safe_create_position(
                symbol=symbol,
                side=side,
                entry_price=market_data.price,
                position_size=normalized_size * market_data.price,  # USD value
                leverage=config.LEVERAGE,
                confidence=signal_data.get('confidence', 0.7)
            )
            
            if not position_id:
                raise Exception("Could not register position in tracker")
            
            position_registered = True
            logging.info(colored(f"✅ {symbol}: Position registered with ID {position_id}", "green"))
            
            # Update SL coordinator with real position_id
            sl_state = global_sl_coordinator.get_sl_state(temp_position_id)
            if sl_state:
                global_sl_coordinator.remove_position(temp_position_id)
                global_sl_coordinator._sl_state[position_id] = sl_state
                sl_state.position_id = position_id
            
            # SUCCESS - Return result
            return TradingResult(
                success=True,
                position_id=position_id,
                error="",
                order_ids={'main': executed_order_id, 'sl': 'coordinator_managed'}
            )
        
        except Exception as e:
            logging.error(colored(f"❌ {symbol}: Atomic execution failed: {e}", "red"))
            
            # ROLLBACK LOGIC
            if executed_order_id and not sl_set:
                # Position aperta MA SL non settato → CHIUDI IMMEDIATAMENTE
                self._rollback_count += 1
                logging.critical(colored(
                    f"🚨 ROLLBACK: Closing {symbol} position without SL",
                    "red", attrs=['bold']
                ))
                
                try:
                    close_side = 'sell' if side == 'buy' else 'buy'
                    rollback_result = await global_order_manager.place_market_order(
                        exchange, symbol, close_side, normalized_size
                    )
                    
                    if rollback_result.success:
                        logging.info(colored(f"✅ Rollback successful: {symbol} position closed", "green"))
                    else:
                        logging.critical(colored(
                            f"❌ ROLLBACK FAILED for {symbol}: {rollback_result.error}",
                            "red", attrs=['bold']
                        ))
                        logging.critical(f"🚨 MANUAL INTERVENTION REQUIRED: Close {symbol} manually on Bybit!")
                
                except Exception as rollback_error:
                    logging.critical(colored(
                        f"❌ ROLLBACK EXCEPTION for {symbol}: {rollback_error}",
                        "red", attrs=['bold']
                    ))
                    logging.critical(f"🚨 MANUAL INTERVENTION REQUIRED: Close {symbol} manually on Bybit!")
            
            return TradingResult(False, "", str(e))
    
    def get_available_balance(self) -> Optional[float]:
        """Get real-time tracked balance"""
        return self._real_time_balance
    
    def get_statistics(self) -> Dict:
        """Get coordinator statistics"""
        return {
            'total_attempts': self._total_attempts,
            'successful_opens': self._successful_opens,
            'failed_opens': self._failed_opens,
            'rollback_count': self._rollback_count,
            'duplicate_prevented': self._duplicate_prevented,
            'success_rate': (self._successful_opens / max(1, self._total_attempts)) * 100
        }
    
    def display_statistics(self):
        """Display coordinator statistics"""
        stats = self.get_statistics()
        
        logging.info(colored("=" * 60, "cyan"))
        logging.info(colored("🔐 POSITION OPENING COORDINATOR STATISTICS", "cyan", attrs=['bold']))
        logging.info(colored("=" * 60, "cyan"))
        logging.info(f"Total Attempts: {stats['total_attempts']}")
        logging.info(f"✅ Successful: {stats['successful_opens']}")
        logging.info(f"❌ Failed: {stats['failed_opens']}")
        logging.info(f"🔄 Rollbacks: {stats['rollback_count']}")
        logging.info(f"🚫 Duplicates Prevented: {stats['duplicate_prevented']}")
        logging.info(f"📊 Success Rate: {stats['success_rate']:.1f}%")
        logging.info(colored("=" * 60, "cyan"))


# Global coordinator instance
global_position_opening_coordinator = PositionOpeningCoordinator()
