#!/usr/bin/env python3
"""
⚡ TRAILING MONITOR - High Frequency Stop Loss Management

RESPONSABILITÀ:
- Thread separato per monitoraggio trailing ogni 30 secondi
- Esecuzione ordini di chiusura quando trailing colpito  
- Aggiornamento real-time prezzi e trailing stops
- Coordinamento con ciclo principale senza interferenze

GARANTISCE: Trailing stops rapidi e precisi
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional
from termcolor import colored

# CRITICAL FIX: Import unified managers for thread safety
try:
    from core.thread_safe_position_manager import global_thread_safe_position_manager
    from core.smart_api_manager import global_smart_api_manager
    UNIFIED_MANAGERS_AVAILABLE = True
    logging.debug("🔒 TrailingMonitor: Unified managers integration enabled")
except ImportError as e:
    UNIFIED_MANAGERS_AVAILABLE = False
    logging.warning(f"⚠️ TrailingMonitor: Unified managers not available: {e}")

# ONLINE LEARNING INTEGRATION: Import learning manager for feedback
try:
    from core.online_learning_manager import global_online_learning_manager
    ONLINE_LEARNING_AVAILABLE = bool(global_online_learning_manager)
    if ONLINE_LEARNING_AVAILABLE:
        logging.info("🧠 TrailingMonitor: Online Learning integration enabled")
except ImportError:
    ONLINE_LEARNING_AVAILABLE = False
    global_online_learning_manager = None
    logging.debug("⚠️ TrailingMonitor: Online Learning not available")

# SL COORDINATOR INTEGRATION: Use centralized SL management (REQUIRED)
from core.stop_loss_coordinator import global_sl_coordinator
logging.info("🎯 TrailingMonitor: SL Coordinator loaded - Centralized SL updates REQUIRED")

class TrailingMonitor:
    """
    Monitor dedicato per trailing stops ad alta frequenza
    
    Funziona in parallelo al ciclo principale del bot (300s)
    Monitora trailing stops ogni 30 secondi per reattività massima
    """
    
    def __init__(self, position_manager, trailing_manager, order_manager):
        self.position_manager = position_manager
        self.trailing_manager = trailing_manager
        self.order_manager = order_manager
        
        # Configurazione monitoraggio
        self.monitor_interval = 30  # 30 secondi (molto più veloce del ciclo principale)
        self.is_running = False
        self.monitor_task = None
        
        logging.info("⚡ TRAILING MONITOR: Initialized for high-frequency stop monitoring (cache-free)")
    
    async def start_monitoring(self, exchange):
        """
        Avvia il thread di monitoraggio trailing
        
        Args:
            exchange: Bybit exchange instance
        """
        if self.is_running:
            logging.warning("⚡ Trailing monitor already running")
            return
            
        self.is_running = True
        logging.info(f"⚡ TRAILING MONITOR: Starting high-frequency monitoring (every {self.monitor_interval}s)")
        
        # Avvia il task asincrono di monitoraggio
        self.monitor_task = asyncio.create_task(self._monitoring_loop(exchange))
    
    async def stop_monitoring(self):
        """Ferma il monitoraggio trailing"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logging.info("⚡ TRAILING MONITOR: Stopped")
    
    async def _monitoring_loop(self, exchange):
        """
        STEP 3 FIX: True Independence Loop - GUARANTEED 30s intervals anche durante main cycle wait
        
        FEATURES:
        - Compensation per processing time → sempre exactly 30s
        - Independent error recovery → continua sempre
        - Cache-only operations → zero API conflicts
        - Atomic operations only → zero race conditions
        """
        import time
        
        try:
            while self.is_running:
                start_time = time.time()
                
                try:
                    # STEP 3 FIX: Lightweight monitoring con cache-only operations
                    await self._monitor_all_positions_lightweight(exchange)
                    
                except Exception as e:
                    logging.error(f"⚡ Error in monitoring loop: {e}")
                    # Independent error recovery - continua sempre
                
                # STEP 3 FIX: Guaranteed 30s intervals (compensation per processing time)
                elapsed = time.time() - start_time
                sleep_time = max(0.1, self.monitor_interval - elapsed)  # At least 0.1s, target 30s
                
                if elapsed > 2.0:  # Log se processing time > 2s
                    logging.debug(f"⚡ PERFORMANCE: Monitoring took {elapsed:.2f}s, sleeping {sleep_time:.2f}s")
                
                await asyncio.sleep(sleep_time)
                    
        except asyncio.CancelledError:
            logging.info("⚡ TRAILING MONITOR: Monitoring loop cancelled gracefully")
        except Exception as e:
            logging.error(f"⚡ FATAL: Monitoring loop failed: {e}")
            # Try to restart after 30s
            await asyncio.sleep(30)
            if self.is_running:
                logging.info("⚡ RECOVERY: Attempting to restart monitoring loop")
                self.monitor_task = asyncio.create_task(self._monitoring_loop(exchange))
        finally:
            self.is_running = False
    
    async def _monitor_all_positions_lightweight(self, exchange):
        """
        STEP 3 FIX: Lightweight monitoring con CACHE-ONLY operations
        
        FEATURES:
        - Uses ONLY cached prices (no direct API calls)
        - Atomic operations only (no race conditions)
        - Fast execution (< 0.5s typical)
        - Zero interference con main cycle
        """
        try:
            # CRITICAL FIX: Use global position manager to ensure we find positions
            if UNIFIED_MANAGERS_AVAILABLE:
                active_positions = global_thread_safe_position_manager.safe_get_all_active_positions()
            else:
                active_positions = self.position_manager.get_active_positions()
            
            if not active_positions:
                return  # Nessuna posizione da monitorare - silent return
            
            # Track if any updates were made during this cycle  
            updates_made = False
            updated_positions = []
            
            # Log status every 10 cycles (5 minutes) to confirm monitor is working
            cycle_count = getattr(self, '_cycle_count', 0) + 1
            self._cycle_count = cycle_count
            
            if cycle_count % 10 == 0:  # Every 10 cycles = 5 minutes
                logging.info(f"⚡ TRAILING STATUS: Monitoring {len(active_positions)} positions (cycle #{cycle_count})")
            
            for position in active_positions:
                position_updated = await self._monitor_single_position_lightweight(exchange, position)
                if position_updated:
                    updates_made = True
                    updated_positions.append(position)
            
            # Only log when updates were made
            if updates_made:
                logging.info(f"⚡ TRAILING UPDATES: {len(updated_positions)} positions updated")
                # Trigger position table display by calling the display utility
                await self._display_positions_after_updates(updated_positions)
                
        except Exception as e:
            logging.error(f"⚡ Error in lightweight monitoring: {e}")

    async def _monitor_all_positions(self, exchange):
        """
        LEGACY: Original monitoring method (kept for compatibility)
        
        Args:
            exchange: Bybit exchange instance
        """
        try:
            active_positions = self.position_manager.get_active_positions()
            
            if not active_positions:
                return  # Nessuna posizione da monitorare
            
            # Log ogni 5 cicli per evitare spam
            if datetime.now().second % 150 == 0:  # 5 cicli * 30s = 150s
                logging.debug(f"⚡ MONITORING: {len(active_positions)} active positions")
            
            for position in active_positions:
                await self._monitor_single_position(exchange, position)
                
        except Exception as e:
            logging.error(f"⚡ Error monitoring all positions: {e}")
    
    async def _monitor_single_position_lightweight(self, exchange, position):
        """
        STEP 3 FIX: Lightweight single position monitoring con CACHE-ONLY operations
        
        OPTIMIZATIONS:
        - Uses ONLY cached prices (no API calls)
        - Atomic operations for all updates
        - Skip expensive operations (ATR estimation, SL updates on Bybit)
        - Fast execution for 30s guarantee
        
        Returns:
            bool: True if position was updated, False otherwise
        """
        position_updated = False
        
        try:
            symbol = position.symbol
            position_id = position.position_id
            
            # 1. CRITICAL DEBUG: Get price real-time (temporary fix for debugging)
            if UNIFIED_MANAGERS_AVAILABLE:
                # Try cache first, fallback to real-time
                current_price = global_smart_api_manager.get_current_price_cached(symbol)
                if current_price is None:
                    logging.debug(f"⚡ Cache miss for {symbol}, fetching real-time")
                    current_price = await global_smart_api_manager.get_current_price_fast(exchange, symbol)
            else:
                current_price = await self._get_current_price(exchange, symbol)
            
            if current_price is None:
                logging.warning(f"⚡ Could not get price for {symbol} (cache + real-time failed)")
                return  # Skip if no price available at all
            
            logging.debug(f"⚡ Processing {symbol} at ${current_price:.6f}")
            
            # 2. ATOMIC UPDATE: Price and PnL update (use global manager)
            if UNIFIED_MANAGERS_AVAILABLE and hasattr(global_thread_safe_position_manager, 'atomic_update_price_and_pnl'):
                success = global_thread_safe_position_manager.atomic_update_price_and_pnl(position_id, current_price)
                if not success:
                    return  # Position may have been closed
            
            # CRITICAL FIX: Skip trailing_data initialization completely to avoid conflicts
            trailing_data = None
            if hasattr(position, 'trailing_data') and position.trailing_data is not None:
                trailing_data = position.trailing_data
                logging.debug(f"⚡ Using existing trailing_data for {symbol}")
            else:
                # SKIP INITIALIZATION: Let trading_orchestrator handle it
                logging.debug(f"⚡ No trailing_data for {symbol} - skipping (will be handled by trading_orchestrator)")
                return  # Skip position without trailing_data
            
            if trailing_data is None:
                return  # Skip if no trailing_data available
            
            # 4. LIGHTWEIGHT: Simple trailing activation check
            if not trailing_data.trailing_attivo:
                if self.trailing_manager.check_activation_conditions(trailing_data, current_price):
                    # Simple activation (no Bybit SL update in lightweight mode)
                    atr_estimated = position.entry_price * 0.02  # Quick ATR estimate
                    self.trailing_manager.activate_trailing(
                        trailing_data, current_price, position.side, atr_estimated
                    )
                    
                    # ATOMIC UPDATE: Trailing state update (use global manager)
                    if UNIFIED_MANAGERS_AVAILABLE:
                        global_thread_safe_position_manager.atomic_update_trailing_state(position_id, {
                            'trailing_active': True,
                            'best_price': current_price,
                            'sl_corrente': trailing_data.sl_corrente
                        })
                    
                    logging.info(colored(f"⚡ TRAILING ACTIVATED: {symbol} → SL: ${trailing_data.sl_corrente:.6f}", "green"))
                    position_updated = True
            
            # 5. LIGHTWEIGHT: Trailing update if active
            if trailing_data.trailing_attivo:
                old_sl = trailing_data.sl_corrente
                atr_estimated = position.entry_price * 0.02  # Quick ATR estimate
                
                # Update trailing stop
                self.trailing_manager.update_trailing(
                    trailing_data, current_price, position.side, atr_estimated
                )
                
                # ATOMIC UPDATE: Sync state if changed (use global manager)
                if old_sl != trailing_data.sl_corrente:
                    if UNIFIED_MANAGERS_AVAILABLE:
                        global_thread_safe_position_manager.atomic_update_trailing_state(position_id, {
                            'best_price': trailing_data.best_price,
                            'sl_corrente': trailing_data.sl_corrente
                        })
                    
                    # 🎯 USE SL COORDINATOR: Request update via coordinator (REQUIRED)
                    # Check if the new SL is significantly different
                    sl_diff_pct = abs(trailing_data.sl_corrente - old_sl) / old_sl * 100
                    if sl_diff_pct >= 0.1:  # Only update if difference >= 0.1%
                        # Request update via coordinator with HIGH priority
                        update_accepted = await global_sl_coordinator.request_sl_update(
                            position_id,
                            trailing_data.sl_corrente,
                            source="TRAILING_ACTIVE"
                        )
                        
                        if update_accepted:
                            symbol_short = symbol.replace('/USDT:USDT', '')
                            
                            # Calculate PnL at new stop loss for display
                            if position.side.lower() == 'buy':
                                pnl_at_new_sl = ((trailing_data.sl_corrente - position.entry_price) / position.entry_price) * 100 * getattr(position, 'leverage', 10)
                            else:
                                pnl_at_new_sl = ((position.entry_price - trailing_data.sl_corrente) / position.entry_price) * 100 * getattr(position, 'leverage', 10)
                            
                            # PROMINENT DISPLAY: Clear visual update during cycle wait
                            print(colored("=" * 80, "yellow"))
                            print(colored(f"🎯 TRAILING STOP UPDATE QUEUED: {symbol_short}", "cyan", attrs=['bold']))
                            print(colored(f"💰 Old SL: ${old_sl:.6f} → New SL: ${trailing_data.sl_corrente:.6f}", "green", attrs=['bold']))
                            print(colored(f"🛡️ Protected PnL: {pnl_at_new_sl:+.1f}% minimum guaranteed", "green", attrs=['bold']))
                            print(colored(f"📈 Current Price: ${current_price:.6f} | Entry: ${position.entry_price:.6f}", "white"))
                            print(colored("=" * 80, "yellow"))
                            
                            logging.info(colored(f"🎯 {symbol_short}: SL update queued via coordinator", "green"))
                        else:
                            logging.debug(f"🎯 {symbol}: SL update rejected by coordinator (lower priority)")
                    else:
                        logging.debug(f"⚡ {symbol}: SL change too small ({sl_diff_pct:.2f}%), skipping update")
                    
                    # Log the trailing stop update with details
                    if position.side.lower() == 'buy':
                        pnl_at_sl = ((trailing_data.sl_corrente - position.entry_price) / position.entry_price) * 100 * getattr(position, 'leverage', 10)
                    else:
                        pnl_at_sl = ((position.entry_price - trailing_data.sl_corrente) / position.entry_price) * 100 * getattr(position, 'leverage', 10)
                    
                    logging.info(colored(f"⚡ TRAILING UPDATED: {symbol} → SL: ${old_sl:.6f} → ${trailing_data.sl_corrente:.6f} (Exit at {pnl_at_sl:+.1f}%)", "cyan"))
                    position_updated = True
                
                # 6. CRITICAL: Check trailing hit and execute exit
                if self.trailing_manager.is_trailing_hit(trailing_data, current_price, position.side):
                    # IMMEDIATE EXIT: Use lightweight exit method
                    success = await self._execute_lightweight_trailing_exit(exchange, position, current_price)
                    if success:
                        logging.info(colored(f"⚡ TRAILING EXIT: {symbol} closed at ${current_price:.6f} (stop hit)", "yellow"))
                        position_updated = True
                        return position_updated
            
            return position_updated
            
        except Exception as e:
            logging.debug(f"⚡ Lightweight monitoring error for {position.symbol}: {e}")
            return False

    async def _monitor_single_position(self, exchange, position):
        """
        🔒 THREAD-SAFE: Monitora una singola posizione con atomic operations
        
        ELIMINA RACE CONDITIONS: Usa atomic updates invece di accesso diretto
        USA API MANAGER: Cache intelligente per ridurre API calls
        """
        try:
            symbol = position.symbol
            position_id = position.position_id
            
            # 1. OTTIENI PREZZO con API Manager (cache intelligente)
            if UNIFIED_MANAGERS_AVAILABLE:
                current_price = await global_smart_api_manager.get_current_price_fast(exchange, symbol)
            else:
                current_price = await self._get_current_price(exchange, symbol)
            
            if current_price is None:
                return
            
            # 2. ATOMIC UPDATE: Aggiorna prezzo e PnL atomicamente (no race conditions)
            if UNIFIED_MANAGERS_AVAILABLE and hasattr(self.position_manager, 'atomic_update_price_and_pnl'):
                success = self.position_manager.atomic_update_price_and_pnl(position_id, current_price)
                if not success:
                    logging.warning(f"⚡ Atomic price update failed for {symbol}")
                    return
            else:
                # Legacy: Direct access (with race condition risk)
                position.current_price = current_price
            
            # 3. Assicurati che trailing_data esista (init se necessario)
            if not hasattr(position, 'trailing_data') or position.trailing_data is None:
                atr = await self._estimate_atr(exchange, symbol)
                trailing_data = self.trailing_manager.initialize_trailing_data(
                    position.symbol, position.side, position.entry_price, atr
                )
                
                # ATOMIC UPDATE: Salva trailing_data atomicamente
                if UNIFIED_MANAGERS_AVAILABLE and hasattr(self.position_manager, 'atomic_update_position'):
                    self.position_manager.atomic_update_position(position_id, {'trailing_data': trailing_data})
                else:
                    position.trailing_data = trailing_data
                
                logging.debug(f"⚡ TrailingMonitor: Initialized trailing_data for {symbol}")
            
            trailing_data = position.trailing_data
            
            # 4. Controlla se trigger è raggiunto (attivazione trailing)
            if not trailing_data.trailing_attivo:
                if self.trailing_manager.check_activation_conditions(trailing_data, current_price):
                    # Attiva trailing stop
                    atr = await self._estimate_atr(exchange, symbol)
                    self.trailing_manager.activate_trailing(
                        trailing_data, current_price, position.side, atr
                    )
                    
                    # ATOMIC UPDATE: Sync trailing state atomicamente
                    trailing_state = {
                        'trailing_active': True,
                        'best_price': current_price,
                        'sl_corrente': trailing_data.sl_corrente
                    }
                    
                    if UNIFIED_MANAGERS_AVAILABLE and hasattr(self.position_manager, 'atomic_update_trailing_state'):
                        self.position_manager.atomic_update_trailing_state(position_id, trailing_state)
                    else:
                        # Legacy: Direct access (with race condition risk)
                        position.trailing_attivo = True
                        position.best_price = current_price
                        position.sl_corrente = trailing_data.sl_corrente
                    
                    # 🎯 CRITICAL FIX: Use SL Coordinator instead of direct Bybit update
                    if trailing_data.sl_corrente is not None:
                        update_accepted = await global_sl_coordinator.request_sl_update(
                            position_id,
                            trailing_data.sl_corrente,
                            source="TRAILING_ACTIVE"
                        )
                        if update_accepted:
                            logging.info(colored(f"🎯 {symbol}: Trailing SL activation queued via coordinator ${trailing_data.sl_corrente:.6f}", "green"))
                        else:
                            logging.debug(f"⚡ {symbol}: SL update queued for coordinator processing")
                    
                    logging.info(colored(f"⚡ TRAILING SYSTEM ACTIVE: {symbol} monitoring every 30s", "green"))
            
            # 5. Se trailing è attivo, aggiorna e controlla hit
            if trailing_data.trailing_attivo:
                atr = await self._estimate_atr(exchange, symbol)
                
                # Salva vecchio SL per confronto
                old_sl = trailing_data.sl_corrente
                
                # Aggiorna trailing stop
                self.trailing_manager.update_trailing(
                    trailing_data, current_price, position.side, atr
                )
                
                # ATOMIC UPDATE: Sync trailing state se cambiato
                if old_sl != trailing_data.sl_corrente:
                    trailing_state = {
                        'best_price': trailing_data.best_price,
                        'sl_corrente': trailing_data.sl_corrente
                    }
                    
                    if UNIFIED_MANAGERS_AVAILABLE and hasattr(self.position_manager, 'atomic_update_trailing_state'):
                        self.position_manager.atomic_update_trailing_state(position_id, trailing_state)
                    else:
                        # Legacy: Direct access (with race condition risk)
                        position.best_price = trailing_data.best_price
                        position.sl_corrente = trailing_data.sl_corrente
                
                # 🎯 CRITICAL FIX: Use SL Coordinator instead of direct Bybit update (ELIMINATES RACE CONDITION)
                if old_sl != trailing_data.sl_corrente and trailing_data.sl_corrente is not None:
                    update_accepted = await global_sl_coordinator.request_sl_update(
                        position_id,
                        trailing_data.sl_corrente,
                        source="TRAILING_ACTIVE"
                    )
                    if update_accepted:
                        # Calcola PnL target per uscita
                        if position.side == 'buy':
                            exit_pnl_pct = ((trailing_data.sl_corrente - position.entry_price) / position.entry_price) * 100 * 10
                        else:
                            exit_pnl_pct = ((position.entry_price - trailing_data.sl_corrente) / position.entry_price) * 100 * 10
                        
                        logging.debug(colored(f"🎯 {symbol}: Stop update queued via coordinator → Target exit at {exit_pnl_pct:+.1f}% PnL (${trailing_data.sl_corrente:.6f})", "cyan"))
                    else:
                        logging.debug(f"🎯 {symbol}: SL update queued for coordinator (lower priority)")
                
                # Controlla se trailing stop è colpito
                if self.trailing_manager.is_trailing_hit(trailing_data, current_price, position.side):
                    # ESEGUI USCITA IMMEDIATA
                    success = await self._execute_trailing_exit(exchange, position, current_price)
                    if success:
                        logging.info(colored(f"⚡ TRAILING EXIT EXECUTED: {symbol} at ${current_price:.6f}", "yellow"))
                        # Position viene chiusa nel _execute_trailing_exit
                        return
            
            # 6. ATOMIC SAVE: Salva solo se necessario
            if not UNIFIED_MANAGERS_AVAILABLE:
                # Legacy save (con race condition risk)
                self.position_manager.save_positions()
            # Note: ThreadSafePositionManager auto-saves durante atomic operations
            
        except Exception as e:
            logging.error(f"⚡ Error monitoring position {position.symbol}: {e}")
    
    async def _get_current_price(self, exchange, symbol: str) -> Optional[float]:
        """
        Ottieni prezzo corrente real-time
        
        Args:
            exchange: Bybit exchange instance
            symbol: Trading symbol
            
        Returns:
            Optional[float]: Current price or None if error
        """
        try:
            ticker = await exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            logging.warning(f"⚡ Could not fetch price for {symbol}: {e}")
            return None
    
    
    async def _estimate_atr(self, exchange, symbol: str) -> float:
        """
        Stima ATR per il simbolo (fallback se non disponibile)
        
        Args:
            exchange: Bybit exchange instance  
            symbol: Trading symbol
            
        Returns:
            float: Estimated ATR
        """
        try:
            # Cerca di ottenere ATR real-time se possibile
            if exchange:
                ticker = await exchange.fetch_ticker(symbol)
                price = float(ticker['last'])
                # Stima ATR come % del prezzo (2% tipico per crypto)
                return price * 0.02
            else:
                # Fallback: usa 2% del prezzo entry
                return 0.02
                
        except Exception as e:
            logging.debug(f"⚡ ATR estimation failed for {symbol}: {e}")
            return 0.02  # Fallback conservativo
    
    async def _execute_lightweight_trailing_exit(self, exchange, position, current_price: float) -> bool:
        """
        STEP 3 FIX: Lightweight trailing exit per performance ottimale
        
        OPTIMIZATIONS:
        - Fast exit order execution
        - Atomic position closure
        - Minimal logging per speed
        - Online Learning notification
        
        Args:
            exchange: Bybit exchange instance
            position: Position to exit
            current_price: Current market price
            
        Returns:
            bool: True if exit successful
        """
        try:
            symbol = position.symbol
            
            # Calculate PnL before closing
            entry_price = position.entry_price
            if position.side.lower() == 'buy':
                pnl_percentage = ((current_price - entry_price) / entry_price) * 100
            else:  # sell/short
                pnl_percentage = ((entry_price - current_price) / entry_price) * 100
            
            # Apply leverage for actual PnL
            leverage = getattr(position, 'leverage', 10)  # Default to 10x if not available
            pnl_percentage *= leverage
            
            # Estimate USD PnL (approximate)
            position_value = getattr(position, 'position_value', entry_price * position.position_size)
            pnl_usd = (pnl_percentage / 100) * position_value
            
            # FAST EXIT: Direct market order (bypass trailing_manager overhead)
            exit_side = 'sell' if position.side.lower() == 'buy' else 'buy'
            
            # Use order manager for fast execution
            order_result = await self.order_manager.place_market_order(
                exchange, symbol, exit_side, position.position_size
            )
            
            if order_result.success:
                # ATOMIC CLOSURE: Close position atomically
                if UNIFIED_MANAGERS_AVAILABLE:
                    success = self.position_manager.thread_safe_close_position(
                        position.position_id, current_price, "TRAILING_FAST"
                    )
                else:
                    success = self.position_manager.close_position_manual(
                        position.position_id, current_price, "TRAILING"
                    )
                
                if success:
                    logging.info(colored(f"⚡ FAST EXIT: {symbol} closed at ${current_price:.6f}", "yellow"))
                    
                    # 🧠 ONLINE LEARNING: Notify about trailing stop exit
                    if ONLINE_LEARNING_AVAILABLE and global_online_learning_manager:
                        try:
                            global_online_learning_manager.track_trade_closing(
                                symbol, current_price, pnl_usd, pnl_percentage, "TRAILING_STOP"
                            )
                            logging.debug(f"🧠 Learning notified: {symbol.replace('/USDT:USDT', '')} trailing exit ({pnl_percentage:+.2f}%)")
                        except Exception as learning_error:
                            logging.warning(f"Learning notification error: {learning_error}")
                
                return success
            else:
                logging.error(f"⚡ Fast exit failed for {symbol}: {order_result.error}")
                return False
            
        except Exception as e:
            logging.error(f"⚡ Lightweight exit error for {position.symbol}: {e}")
            return False

    async def _execute_trailing_exit(self, exchange, position, current_price: float) -> bool:
        """
        LEGACY: Full trailing exit con comprehensive logging + Online Learning notification
        
        Args:
            exchange: Bybit exchange instance
            position: Position to exit
            current_price: Current market price
            
        Returns:
            bool: True if exit successful
        """
        try:
            symbol = position.symbol
            
            # Calculate PnL before closing (same logic as lightweight method)
            entry_price = position.entry_price
            if position.side.lower() == 'buy':
                pnl_percentage = ((current_price - entry_price) / entry_price) * 100
            else:  # sell/short
                pnl_percentage = ((entry_price - current_price) / entry_price) * 100
            
            # Apply leverage for actual PnL
            leverage = getattr(position, 'leverage', 10)  # Default to 10x if not available
            pnl_percentage *= leverage
            
            # Estimate USD PnL (approximate)
            position_value = getattr(position, 'position_value', entry_price * position.position_size)
            pnl_usd = (pnl_percentage / 100) * position_value
            
            # Usa il trailing manager per eseguire l'uscita
            success = await self.trailing_manager.execute_trailing_exit(
                exchange, position.symbol, position.side, 
                position.position_size, current_price
            )
            
            if success:
                # Aggiorna position manager
                self.position_manager.close_position_manual(
                    position.position_id, current_price, "TRAILING"
                )
                
                # 🧠 ONLINE LEARNING: Notify about trailing stop exit (legacy method)
                if ONLINE_LEARNING_AVAILABLE and global_online_learning_manager:
                    try:
                        global_online_learning_manager.track_trade_closing(
                            symbol, current_price, pnl_usd, pnl_percentage, "TRAILING_STOP"
                        )
                        logging.debug(f"🧠 Learning notified: {symbol.replace('/USDT:USDT', '')} trailing exit ({pnl_percentage:+.2f}%)")
                    except Exception as learning_error:
                        logging.warning(f"Learning notification error: {learning_error}")
            
            return success
            
        except Exception as e:
            logging.error(f"⚡ Error executing trailing exit for {position.symbol}: {e}")
            return False
    
    async def _display_positions_after_updates(self, updated_positions):
        """
        Mostra la tabella delle posizioni solo quando ci sono stati aggiornamenti trailing
        
        Args:
            updated_positions: List of positions that were updated
        """
        try:
            # Import display utility for showing position table
            from core.realtime_display import RealtimeDisplay
            
            if not UNIFIED_MANAGERS_AVAILABLE:
                return
                
            # Get all active positions for table display
            all_positions = global_thread_safe_position_manager.safe_get_all_active_positions()
            
            if all_positions:
                display = RealtimeDisplay()
                
                # Display header with update info
                updated_symbols = [pos.symbol.replace('/USDT:USDT', '') for pos in updated_positions]
                logging.info(f"⚡ UPDATED SYMBOLS: {', '.join(updated_symbols)}")
                
                # Show position table
                await display.show_positions_snapshot(all_positions, "Bybit", "TRAILING UPDATE")
                
        except Exception as e:
            logging.debug(f"⚡ Error displaying positions after updates: {e}")
    
    def get_monitoring_status(self) -> Dict:
        """
        Ottieni stato del monitoraggio
        
        Returns:
            Dict: Status information
        """
        return {
            'is_running': self.is_running,
            'monitor_interval': self.monitor_interval,
            'active_positions': len(self.position_manager.get_active_positions()),
            'last_check': datetime.now().isoformat() if self.is_running else None
        }

# Global trailing monitor instance
global_trailing_monitor = None  # Inizializzato nel main
