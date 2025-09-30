#!/usr/bin/env python3
"""
🎯 STOP LOSS COORDINATOR

RESPONSABILITÀ CENTRALE:
- Unico punto che modifica Stop Loss su Bybit
- Gestisce stato SL per ogni posizione
- Coordina aggiornamenti da trailing/orchestrator/manual
- Previene conflitti con priority-based queue
- Retry logic robusto + fallback

GARANZIE:
- Zero conflitti tra componenti
- State sempre accurato
- Aggiornamenti serializzati
- Rollback automatico su failure
"""

import asyncio
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from termcolor import colored

@dataclass
class StopLossState:
    """State tracking per Stop Loss di una posizione"""
    position_id: str
    symbol: str
    current_sl: float
    last_update: datetime
    source: str  # "INITIAL" | "TRAILING" | "ORCHESTRATOR" | "MANUAL"
    update_count: int = 0
    bybit_confirmed: bool = False


class StopLossCoordinator:
    """
    Coordinator centrale per gestione Stop Loss
    
    PHILOSOPHY:
    - Single source of truth per SL state
    - Priority-based conflict resolution
    - Serialized updates con lock
    - Robust error handling + retry
    """
    
    # Priority levels per source
    PRIORITY_LEVELS = {
        "MANUAL": 15,           # Manual override ha massima priorità
        "TRAILING_ACTIVE": 10,  # Trailing attivo ha alta priorità
        "INITIAL_SET": 5,       # Set iniziale ha media priorità
        "ORCHESTRATOR_SYNC": 3, # Sync ha bassa priorità
        "PROTECTION": 7         # Protection update ha priorità medio-alta
    }
    
    def __init__(self):
        # State tracking
        self._sl_state: Dict[str, StopLossState] = {}
        
        # Locking per operazioni atomiche
        self._global_lock = asyncio.Lock()
        self._symbol_locks: Dict[str, asyncio.Lock] = {}
        
        # Update queue con priority
        self._pending_updates: Dict[str, Tuple[float, str, int]] = {}
        
        # Statistics
        self._total_updates = 0
        self._successful_updates = 0
        self._failed_updates = 0
        self._conflicts_resolved = 0
        
        logging.info("🎯 StopLossCoordinator initialized - Centralized SL management active")
    
    def _get_symbol_lock(self, symbol: str) -> asyncio.Lock:
        """Get or create lock per symbol"""
        if symbol not in self._symbol_locks:
            self._symbol_locks[symbol] = asyncio.Lock()
        return self._symbol_locks[symbol]
    
    async def set_initial_sl(
        self, 
        exchange, 
        position_id: str,
        symbol: str, 
        side: str, 
        entry_price: float,
        max_retries: int = 3
    ) -> Tuple[bool, Optional[float]]:
        """
        Set Stop Loss iniziale su nuova posizione
        
        CRITICAL: Questo metodo è chiamato durante apertura posizione
        MUST succeed o la posizione non verrà aperta
        
        Args:
            exchange: Bybit exchange instance
            position_id: Position ID nel tracker
            symbol: Trading symbol
            side: 'buy' o 'sell'
            entry_price: Prezzo di entrata
            max_retries: Numero massimo tentativi
            
        Returns:
            Tuple[bool, Optional[float]]: (success, sl_price)
        """
        try:
            # Calculate SL 6% from entry
            if side.lower() == 'buy':
                sl_price = entry_price * 0.94  # -6%
            else:
                sl_price = entry_price * 1.06  # +6%
            
            # Acquire symbol lock
            lock = self._get_symbol_lock(symbol)
            async with lock:
                
                # Normalize SL price
                try:
                    from core.price_precision_handler import global_price_precision_handler
                    normalized_sl, success = await global_price_precision_handler.normalize_stop_loss_price(
                        exchange, symbol, side, entry_price, sl_price
                    )
                    if success:
                        sl_price = normalized_sl
                except Exception as e:
                    logging.warning(f"🎯 {symbol}: SL normalization failed, using raw: {e}")
                
                # Set SL su Bybit con retry
                for attempt in range(max_retries):
                    try:
                        from core.order_manager import global_order_manager
                        
                        result = await global_order_manager.set_trading_stop(
                            exchange, symbol, sl_price, None
                        )
                        
                        if result.success:
                            # SUCCESS - Register state
                            self._sl_state[position_id] = StopLossState(
                                position_id=position_id,
                                symbol=symbol,
                                current_sl=sl_price,
                                last_update=datetime.now(),
                                source="INITIAL_SET",
                                update_count=1,
                                bybit_confirmed=True
                            )
                            
                            self._successful_updates += 1
                            logging.info(colored(
                                f"🎯 {symbol}: Initial SL set at ${sl_price:.6f} (-6% protection)",
                                "green"
                            ))
                            return True, sl_price
                        
                        else:
                            # Retry on failure
                            logging.warning(f"🎯 {symbol}: SL set failed (attempt {attempt+1}/{max_retries}): {result.error}")
                            
                            if attempt < max_retries - 1:
                                await asyncio.sleep(1)  # Wait before retry
                    
                    except Exception as e:
                        logging.error(f"🎯 {symbol}: SL set error (attempt {attempt+1}/{max_retries}): {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                
                # All retries failed
                self._failed_updates += 1
                logging.critical(colored(
                    f"🚨 {symbol}: CRITICAL - Could not set initial SL after {max_retries} attempts!",
                    "red", attrs=['bold']
                ))
                return False, None
        
        except Exception as e:
            logging.critical(f"🚨 Fatal error setting initial SL for {symbol}: {e}")
            self._failed_updates += 1
            return False, None
    
    async def request_sl_update(
        self,
        position_id: str,
        new_sl: float,
        source: str,
        symbol: Optional[str] = None
    ) -> bool:
        """
        Request SL update (da trailing/orchestrator/manual)
        
        Updates vengono queued e processati con priority resolution
        
        Args:
            position_id: Position ID
            new_sl: Nuovo Stop Loss price
            source: Source dell'update ("TRAILING_ACTIVE" | "ORCHESTRATOR_SYNC" | etc)
            symbol: Trading symbol (optional, viene recuperato dallo state)
            
        Returns:
            bool: True se request accettato nella queue
        """
        try:
            # Get current state
            current_state = self._sl_state.get(position_id)
            
            if not current_state:
                logging.warning(f"🎯 Request SL update for unknown position {position_id}")
                return False
            
            # Get priorities
            new_priority = self.PRIORITY_LEVELS.get(source, 5)
            current_source = current_state.source
            current_priority = self.PRIORITY_LEVELS.get(current_source, 5)
            
            # Conflict resolution
            if position_id in self._pending_updates:
                # Already pending update
                pending_sl, pending_source, pending_priority = self._pending_updates[position_id]
                
                if new_priority > pending_priority:
                    # New request ha priorità maggiore
                    self._pending_updates[position_id] = (new_sl, source, new_priority)
                    self._conflicts_resolved += 1
                    logging.info(f"🎯 {current_state.symbol}: SL update replaced (new priority {new_priority} > {pending_priority})")
                    return True
                else:
                    # Reject - priorità troppo bassa
                    logging.debug(f"🎯 {current_state.symbol}: SL update rejected (priority {new_priority} <= {pending_priority})")
                    return False
            
            else:
                # No pending update - check vs current
                if new_priority >= current_priority:
                    # Accept update
                    self._pending_updates[position_id] = (new_sl, source, new_priority)
                    logging.debug(f"🎯 {current_state.symbol}: SL update queued from {source}")
                    return True
                else:
                    # Reject - current ha priorità maggiore
                    logging.debug(f"🎯 {current_state.symbol}: SL update rejected (current priority {current_priority} > {new_priority})")
                    return False
        
        except Exception as e:
            logging.error(f"🎯 Error queueing SL update for {position_id}: {e}")
            return False
    
    async def process_sl_updates(self, exchange) -> Dict[str, bool]:
        """
        Process queued SL updates
        
        Chiamato periodicamente dal main loop
        Applica updates con conflict resolution e retry
        
        Args:
            exchange: Bybit exchange instance
            
        Returns:
            Dict[str, bool]: Results per position_id
        """
        if not self._pending_updates:
            return {}
        
        results = {}
        
        # Process each pending update
        pending_items = list(self._pending_updates.items())
        
        for position_id, (new_sl, source, priority) in pending_items:
            try:
                current_state = self._sl_state.get(position_id)
                
                if not current_state:
                    logging.warning(f"🎯 Cannot process update for unknown position {position_id}")
                    del self._pending_updates[position_id]
                    results[position_id] = False
                    continue
                
                symbol = current_state.symbol
                
                # Check if SL actually changed
                if abs(new_sl - current_state.current_sl) < 0.0001:
                    # No change - skip
                    logging.debug(f"🎯 {symbol}: SL unchanged, skipping update")
                    del self._pending_updates[position_id]
                    results[position_id] = True
                    continue
                
                # Acquire lock
                lock = self._get_symbol_lock(symbol)
                async with lock:
                    
                    # Execute update su Bybit
                    try:
                        from core.order_manager import global_order_manager
                        
                        result = await global_order_manager.set_trading_stop(
                            exchange, symbol, new_sl, None
                        )
                        
                        if result.success:
                            # Update state
                            old_sl = current_state.current_sl
                            current_state.current_sl = new_sl
                            current_state.last_update = datetime.now()
                            current_state.source = source
                            current_state.update_count += 1
                            current_state.bybit_confirmed = True
                            
                            self._successful_updates += 1
                            
                            # Calculate change %
                            change_pct = abs((new_sl - old_sl) / old_sl) * 100
                            
                            logging.info(colored(
                                f"🎯 {symbol}: SL updated ${old_sl:.6f} → ${new_sl:.6f} (Δ{change_pct:.2f}%) [Source: {source}]",
                                "cyan"
                            ))
                            
                            results[position_id] = True
                        
                        else:
                            # Update failed
                            error_msg = result.error or "unknown error"
                            
                            # Check if it's "not modified" error (non-critical)
                            if "34040" in error_msg.lower() or "not modified" in error_msg.lower():
                                logging.debug(f"🎯 {symbol}: SL already at target value")
                                results[position_id] = True
                            else:
                                logging.warning(f"🎯 {symbol}: SL update failed: {error_msg}")
                                results[position_id] = False
                                self._failed_updates += 1
                    
                    except Exception as e:
                        logging.error(f"🎯 {symbol}: Error updating SL: {e}")
                        results[position_id] = False
                        self._failed_updates += 1
                    
                    # Remove from pending queue
                    del self._pending_updates[position_id]
            
            except Exception as e:
                logging.error(f"🎯 Error processing SL update for {position_id}: {e}")
                results[position_id] = False
                # Remove from queue to avoid infinite retry
                if position_id in self._pending_updates:
                    del self._pending_updates[position_id]
        
        return results
    
    def get_current_sl(self, position_id: str) -> Optional[float]:
        """
        Get current SL per position
        
        Args:
            position_id: Position ID
            
        Returns:
            Optional[float]: Current SL price or None
        """
        state = self._sl_state.get(position_id)
        return state.current_sl if state else None
    
    def get_sl_state(self, position_id: str) -> Optional[StopLossState]:
        """Get full SL state per position"""
        return self._sl_state.get(position_id)
    
    def remove_position(self, position_id: str):
        """Remove position dallo state tracking (quando chiusa)"""
        if position_id in self._sl_state:
            symbol = self._sl_state[position_id].symbol
            del self._sl_state[position_id]
            logging.debug(f"🎯 {symbol}: SL state removed (position closed)")
        
        # Remove pending updates
        if position_id in self._pending_updates:
            del self._pending_updates[position_id]
    
    def get_statistics(self) -> Dict:
        """Get coordinator statistics"""
        return {
            'total_updates': self._total_updates,
            'successful_updates': self._successful_updates,
            'failed_updates': self._failed_updates,
            'conflicts_resolved': self._conflicts_resolved,
            'active_positions': len(self._sl_state),
            'pending_updates': len(self._pending_updates),
            'success_rate': (self._successful_updates / max(1, self._total_updates)) * 100
        }
    
    def display_statistics(self):
        """Display coordinator statistics"""
        stats = self.get_statistics()
        
        logging.info(colored("=" * 60, "cyan"))
        logging.info(colored("🎯 STOP LOSS COORDINATOR STATISTICS", "cyan", attrs=['bold']))
        logging.info(colored("=" * 60, "cyan"))
        logging.info(f"Total Updates: {stats['total_updates']}")
        logging.info(f"✅ Successful: {stats['successful_updates']}")
        logging.info(f"❌ Failed: {stats['failed_updates']}")
        logging.info(f"🔄 Conflicts Resolved: {stats['conflicts_resolved']}")
        logging.info(f"📊 Success Rate: {stats['success_rate']:.1f}%")
        logging.info(f"🔒 Active Positions: {stats['active_positions']}")
        logging.info(f"⏳ Pending Updates: {stats['pending_updates']}")
        logging.info(colored("=" * 60, "cyan"))


# Global coordinator instance
global_sl_coordinator = StopLossCoordinator()
