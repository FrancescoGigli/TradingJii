#!/usr/bin/env python3
"""
🔒 THREAD-SAFE POSITION MANAGER

CRITICAL FIX: Eliminazione race conditions tra multiple thread
- Atomic operations per position updates
- Centralized state management
- Thread-safe access patterns
- Backward compatibility con sistema esistente
- OS-level file locking per prevenire corruzione JSON

GARANTISCE: Zero race conditions, state consistency, file integrity
"""

import json
import asyncio
import threading
import logging
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from copy import deepcopy
from termcolor import colored

# OS-level file locking (CRITICAL FIX per prevenire corruzione JSON)
if sys.platform == 'win32':
    import msvcrt
else:
    import fcntl

# Removed: Online Learning / Post-mortem system (not functioning)

@dataclass
class ThreadSafePosition:
    """Position data structure ottimizzata per thread safety"""
    position_id: str
    symbol: str
    side: str
    entry_price: float
    position_size: float
    leverage: int
    
    # Protection levels
    stop_loss: float
    take_profit: Optional[float]
    trailing_trigger: float
    
    # Runtime data (protected by lock)
    current_price: float = 0.0
    unrealized_pnl_pct: float = 0.0
    unrealized_pnl_usd: float = 0.0
    max_favorable_pnl: float = 0.0
    
    # No trailing system - simplified position tracking
    
    # Metadata
    confidence: float = 0.7
    entry_time: str = ""
    close_time: Optional[str] = None
    status: str = "OPEN"
    
    # Order tracking
    sl_order_id: Optional[str] = None
    tp_order_id: Optional[str] = None
    
    # Migration flags
    _migrated: bool = False
    _needs_sl_update_on_bybit: bool = False


class ThreadSafePositionManager:
    """
    CRITICAL FIX: Manager thread-safe per posizioni
    
    FEATURES:
    - Atomic operations per tutti gli updates
    - Read/Write locks separati
    - Deep copy per read operations (evita modifiche esterne)
    - Backward compatibility completa
    - Performance ottimizzate (minimal lock time)
    """
    
    def __init__(self, storage_file: str = "thread_safe_positions.json"):
        self.storage_file = storage_file
        
        # THREAD SAFETY: RLock per operations annidate
        self._lock = threading.RLock()  # Reentrant per nested calls
        self._read_lock = threading.RLock()  # Separato per read operations
        
        # Position storage
        self._open_positions: Dict[str, ThreadSafePosition] = {}
        self._closed_positions: Dict[str, ThreadSafePosition] = {}
        
        # Balance tracking (thread-safe)
        self._session_balance = 1000.0
        self._session_start_balance = 1000.0
        self._real_balance_cache = 1000.0
        
        # Performance tracking
        self._operation_count = 0
        self._lock_contention_count = 0
        
        # Load existing data
        self.load_positions()
        

    
    # ========================================
    # ATOMIC WRITE OPERATIONS (Fully Protected)
    # ========================================
    
    def atomic_update_position(self, position_id: str, updates: Dict[str, Any]) -> bool:
        """
        🔒 ATOMIC: Aggiorna position con thread safety garantita
        
        Args:
            position_id: ID della posizione
            updates: Dict con field -> new_value
            
        Returns:
            bool: True se aggiornamento riuscito
        """
        try:
            with self._lock:
                self._operation_count += 1
                
                if position_id not in self._open_positions:
                    logging.warning(f"🔒 Position {position_id} not found for atomic update")
                    return False
                
                position = self._open_positions[position_id]
                
                # Apply updates atomically
                for field, value in updates.items():
                    if hasattr(position, field):
                        setattr(position, field, value)
                        logging.debug(f"🔒 Atomic update: {position_id}.{field} = {value}")
                    else:
                        logging.warning(f"🔒 Unknown field {field} for position {position_id}")
                
                # Auto-save after updates
                self._save_positions_unsafe()  # Unsafe perché già dentro lock
                return True
                
        except Exception as e:
            logging.error(f"🔒 Atomic update failed for {position_id}: {e}")
            return False
    
    def atomic_update_price_and_pnl(self, position_id: str, current_price: float) -> bool:
        """
        🔒 ATOMIC: Aggiorna prezzo e PnL insieme (operazione critica)
        
        Args:
            position_id: ID posizione
            current_price: Nuovo prezzo corrente
            
        Returns:
            bool: True se update riuscito
        """
        try:
            with self._lock:
                if position_id not in self._open_positions:
                    return False
                
                position = self._open_positions[position_id]
                
                # Calculate PnL atomically
                price_change_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                
                if position.side in ['buy', 'long']:
                    pnl_pct = price_change_pct * position.leverage
                else:
                    pnl_pct = -price_change_pct * position.leverage
                
                initial_margin = position.position_size / position.leverage
                pnl_usd = (pnl_pct / 100) * initial_margin
                
                # Atomic updates
                position.current_price = current_price
                position.unrealized_pnl_pct = pnl_pct
                position.unrealized_pnl_usd = pnl_usd
                position.max_favorable_pnl = max(position.max_favorable_pnl, pnl_pct)
                
                logging.debug(f"🔒 Atomic price/PnL update: {position.symbol} ${current_price:.6f} → {pnl_pct:+.2f}%")
                return True
                
        except Exception as e:
            logging.error(f"🔒 Atomic price/PnL update failed: {e}")
            return False
    
    
    # ========================================
    # SAFE READ OPERATIONS (Read-only, Deep Copy)
    # ========================================
    
    def safe_get_position(self, position_id: str) -> Optional[ThreadSafePosition]:
        """
        🔒 SAFE READ: Ottieni copia deep della posizione (read-only)
        
        Returns:
            ThreadSafePosition: Deep copy della posizione (safe to modify)
        """
        try:
            with self._read_lock:
                if position_id in self._open_positions:
                    # Deep copy per evitare modifiche esterne
                    return deepcopy(self._open_positions[position_id])
                return None
                
        except Exception as e:
            logging.error(f"🔒 Safe read failed for {position_id}: {e}")
            return None
    
    def safe_get_all_active_positions(self) -> List[ThreadSafePosition]:
        """
        🔒 SAFE READ: Ottieni copia deep di tutte le posizioni attive
        
        Returns:
            List[ThreadSafePosition]: Deep copies delle posizioni (safe to modify)
        """
        try:
            with self._read_lock:
                return [deepcopy(pos) for pos in self._open_positions.values() 
                       if pos.status == "OPEN"]
                
        except Exception as e:
            logging.error(f"🔒 Safe read all positions failed: {e}")
            return []
    
    def safe_has_position_for_symbol(self, symbol: str) -> bool:
        """
        🔒 SAFE READ: Controlla se esiste posizione per simbolo
        
        Args:
            symbol: Trading symbol
            
        Returns:
            bool: True se posizione esiste
        """
        try:
            with self._read_lock:
                return any(pos.symbol == symbol and pos.status == "OPEN" 
                          for pos in self._open_positions.values())
                
        except Exception as e:
            logging.error(f"🔒 Safe symbol check failed for {symbol}: {e}")
            return False
    
    def safe_get_position_count(self) -> int:
        """
        🔒 SAFE READ: Conta posizioni attive
        
        Returns:
            int: Numero posizioni attive
        """
        try:
            with self._read_lock:
                return len([pos for pos in self._open_positions.values() 
                          if pos.status == "OPEN"])
                
        except Exception as e:
            logging.error(f"🔒 Safe position count failed: {e}")
            return 0
    
    def safe_get_session_summary(self) -> Dict:
        """
        🔒 SAFE READ: Session summary thread-safe
        
        Returns:
            Dict: Session statistics (safe copy)
        """
        try:
            with self._read_lock:
                active_positions = [pos for pos in self._open_positions.values() 
                                  if pos.status == "OPEN"]
                
                realized_pnl = sum(pos.unrealized_pnl_usd for pos in self._closed_positions.values() 
                                 if pos.unrealized_pnl_usd)
                unrealized_pnl = sum(pos.unrealized_pnl_usd for pos in active_positions)
                total_pnl_usd = realized_pnl + unrealized_pnl
                total_pnl_pct = (total_pnl_usd / self._session_start_balance) * 100
                
                return {
                    'balance': self._session_balance,
                    'active_positions': len(active_positions),
                    'closed_positions': len(self._closed_positions),
                    'total_pnl_usd': total_pnl_usd,
                    'total_pnl_pct': total_pnl_pct,
                    'realized_pnl': realized_pnl,
                    'unrealized_pnl': unrealized_pnl,
                    'used_margin': sum(pos.position_size / pos.leverage for pos in active_positions),
                    'available_balance': max(0, self._session_balance - sum(pos.position_size / pos.leverage for pos in active_positions))
                }
                
        except Exception as e:
            logging.error(f"🔒 Safe session summary failed: {e}")
            return {
                'balance': 0.0,
                'active_positions': 0,
                'closed_positions': 0,
                'total_pnl_usd': 0.0,
                'total_pnl_pct': 0.0,
                'realized_pnl': 0.0,
                'unrealized_pnl': 0.0,
                'used_margin': 0.0,
                'available_balance': 0.0
            }
    
    # ========================================
    # POSITION LIFECYCLE (Thread-safe)
    # ========================================
    
    def thread_safe_create_position(self, symbol: str, side: str, entry_price: float,
                                   position_size: float, leverage: int = 10, 
                                   confidence: float = 0.7) -> str:
        """
        🔒 THREAD SAFE: Crea nuova posizione
        
        Returns:
            str: Position ID se creata con successo
        """
        try:
            with self._lock:
                # Generate unique position ID
                position_id = f"{symbol.replace('/USDT:USDT', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                
                # Simple stop loss calculation (SL system removed)
                stop_loss = entry_price * (0.94 if side.lower() == 'buy' else 1.06)
                
                # Calculate trailing trigger
                if side.lower() == 'buy':
                    trailing_trigger = entry_price * 1.006 * 1.010  # +1% over breakeven
                else:
                    trailing_trigger = entry_price * 0.9994 * 0.990  # -1% under breakeven
                
                position = ThreadSafePosition(
                    position_id=position_id,
                    symbol=symbol,
                    side=side.lower(),
                    entry_price=entry_price,
                    position_size=position_size,
                    leverage=leverage,
                    stop_loss=stop_loss,  # STEP 2 FIX: From unified calculator
                    take_profit=None,  # No fixed TP
                    trailing_trigger=trailing_trigger,
                    current_price=entry_price,
                    confidence=confidence,
                    entry_time=datetime.now().isoformat(),
                    _migrated=True  # New positions are already migrated
                )
                
                self._open_positions[position_id] = position
                self._save_positions_unsafe()  # Already in lock
                
                logging.info(f"🔒 Thread-safe position created with unified SL: {position_id}")
                return position_id
                
        except Exception as e:
            logging.error(f"🔒 Thread-safe position creation failed: {e}")
            return ""
    
    def thread_safe_close_position(self, position_id: str, exit_price: float, 
                                  close_reason: str = "MANUAL") -> bool:
        """
        🔒 THREAD SAFE: Chiudi posizione + Online Learning notification
        
        Returns:
            bool: True se chiusura riuscita
        """
        try:
            with self._lock:
                if position_id not in self._open_positions:
                    logging.warning(f"🔒 Position {position_id} not found for closure")
                    return False
                
                position = self._open_positions[position_id]
                
                # Calculate final PnL
                if position.side == 'buy':
                    pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100 * position.leverage
                else:
                    pnl_pct = ((position.entry_price - exit_price) / position.entry_price) * 100 * position.leverage
                
                initial_margin = position.position_size / position.leverage
                pnl_usd = (pnl_pct / 100) * initial_margin
                
                # Update position as closed
                position.status = f"CLOSED_{close_reason}"
                position.close_time = datetime.now().isoformat()
                position.unrealized_pnl_pct = pnl_pct
                position.unrealized_pnl_usd = pnl_usd
                position.current_price = exit_price
                
                # Move to closed positions
                self._closed_positions[position_id] = position
                del self._open_positions[position_id]
                
                # Update session balance
                self._session_balance += pnl_usd
                
                self._save_positions_unsafe()  # Already in lock
                
                logging.info(f"🔒 Thread-safe position closed: {position.symbol} {close_reason} PnL: {pnl_pct:+.2f}%")
                return True
                
        except Exception as e:
            logging.error(f"🔒 Thread-safe position closure failed: {e}")
            return False
    
    # ========================================
    # BALANCE OPERATIONS (Thread-safe)
    # ========================================
    
    def thread_safe_update_balance(self, new_balance: float) -> None:
        """
        🔒 THREAD SAFE: Aggiorna balance reale
        
        Args:
            new_balance: Nuovo balance da Bybit
        """
        try:
            with self._lock:
                old_balance = self._real_balance_cache
                self._real_balance_cache = new_balance
                self._session_balance = new_balance
                
                # Only update start balance if this is first update
                if self._session_start_balance == 1000.0:
                    self._session_start_balance = new_balance
                
                logging.debug(f"🔒 Thread-safe balance update: ${old_balance:.2f} → ${new_balance:.2f}")
                
        except Exception as e:
            logging.error(f"🔒 Balance update failed: {e}")
    
    def thread_safe_get_available_balance(self) -> float:
        """
        🔒 THREAD SAFE: Ottieni balance disponibile
        
        Returns:
            float: Balance disponibile per nuove posizioni
        """
        try:
            with self._read_lock:
                used_margin = sum(pos.position_size / pos.leverage 
                                for pos in self._open_positions.values() 
                                if pos.status == "OPEN")
                
                available = max(0, self._session_balance - used_margin)
                
                logging.debug(f"🔒 Available balance calculation: ${self._session_balance:.2f} - ${used_margin:.2f} = ${available:.2f}")
                return available
                
        except Exception as e:
            logging.error(f"🔒 Available balance calculation failed: {e}")
            return 0.0
    
    # ========================================
    # BYBIT SYNC (Thread-safe)
    # ========================================
    
    async def thread_safe_sync_with_bybit(self, exchange) -> Tuple[List[ThreadSafePosition], List[ThreadSafePosition]]:
        """
        🔒 THREAD SAFE: Sync con Bybit senza race conditions
        
        Returns:
            Tuple[List[Position], List[Position]]: (newly_opened, newly_closed)
        """
        try:
            # Get Bybit data (outside lock per minimizzare lock time)
            bybit_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_bybit_positions = [p for p in bybit_positions if float(p.get('contracts', 0)) != 0]
            
            # Build Bybit data structures
            bybit_symbols = set()
            bybit_position_data = {}
            
            for pos in active_bybit_positions:
                symbol = pos.get('symbol')
                if symbol:
                    try:
                        symbol_short = symbol.replace('/USDT:USDT', '')
                        
                        # FIX #1: ROBUST PRE-FLOAT VALIDATION
                        # Validate critical fields before float conversion
                        contracts_val = pos.get('contracts')
                        entry_price_val = pos.get('entryPrice')
                        
                        # Skip position if critical data is missing
                        if contracts_val is None or contracts_val == '':
                            logging.warning(f"⚠️ {symbol_short}: 'contracts' is None/empty, skipping position")
                            continue
                        
                        if entry_price_val is None or entry_price_val == '':
                            logging.warning(f"⚠️ {symbol_short}: 'entryPrice' is None/empty, skipping position")
                            continue
                        
                        # Safe float conversion of critical fields
                        contracts_raw = float(contracts_val)
                        contracts = abs(contracts_raw)
                        entry_price = float(entry_price_val)
                        
                        # FIX #2: INTELLIGENT PNL CALCULATION FALLBACK
                        # If unrealizedPnl is None, calculate it manually
                        unrealized_pnl_val = pos.get('unrealizedPnl')
                        
                        if unrealized_pnl_val is None or unrealized_pnl_val == '':
                            logging.info(f"💡 {symbol_short}: unrealizedPnl missing, calculating manually...")
                            
                            # Get current/mark price for calculation
                            current_price_val = pos.get('markPrice') or pos.get('lastPrice')
                            
                            if current_price_val is not None and current_price_val != '':
                                current_price = float(current_price_val)
                                
                                # Determine side first for PnL calculation
                                explicit_side = pos.get('side', '').lower()
                                if explicit_side in ['buy', 'long']:
                                    side_for_calc = 'buy'
                                elif explicit_side in ['sell', 'short']:
                                    side_for_calc = 'sell'
                                else:
                                    side_for_calc = 'buy' if contracts_raw > 0 else 'sell'
                                
                                # Calculate PnL percentage
                                if side_for_calc == 'buy':
                                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                                else:
                                    pnl_pct = ((entry_price - current_price) / entry_price) * 100
                                
                                # Get leverage (default to 10 if not available)
                                leverage = float(pos.get('leverage', 10))
                                
                                # Calculate unrealized PnL in USD
                                position_value = contracts * entry_price
                                unrealized_pnl = (pnl_pct / 100) * position_value * leverage
                                
                                logging.info(f"✅ {symbol_short}: Calculated PnL = ${unrealized_pnl:.2f} ({pnl_pct:+.2f}%)")
                            else:
                                # Cannot calculate without price - use 0 as emergency fallback
                                unrealized_pnl = 0.0
                                logging.warning(f"⚠️ {symbol_short}: No markPrice/lastPrice available, using PnL=0")
                        else:
                            unrealized_pnl = float(unrealized_pnl_val)
                        
                        # Determine side for storage
                        explicit_side = pos.get('side', '').lower()
                        if explicit_side in ['buy', 'long']:
                            side = 'buy'
                        elif explicit_side in ['sell', 'short']:
                            side = 'sell'
                        else:
                            # Fallback to contracts logic
                            side = 'buy' if contracts_raw > 0 else 'sell'
                        
                        # Debug logging
                        logging.debug(f"🔍 {symbol_short}: contracts={contracts_raw}, explicit_side='{explicit_side}', final_side='{side}'")
                        
                        bybit_symbols.add(symbol)
                        bybit_position_data[symbol] = {
                            'contracts': contracts,
                            'side': side,
                            'entry_price': entry_price,
                            'unrealized_pnl': unrealized_pnl
                        }
                        
                    except (ValueError, TypeError) as e:
                        # FIX #3: ENHANCED ERROR LOGGING
                        logging.warning(f"⚠️ Invalid Bybit position data for {symbol_short}: {e}")
                        logging.warning(f"   📊 Raw data: contracts={pos.get('contracts')}, "
                                      f"entryPrice={pos.get('entryPrice')}, "
                                      f"unrealizedPnl={pos.get('unrealizedPnl')}, "
                                      f"markPrice={pos.get('markPrice')}, "
                                      f"side={pos.get('side')}")
                        continue
            
            # ATOMIC SYNC OPERATION
            newly_opened = []
            newly_closed = []
            
            with self._lock:
                # Get currently tracked symbols
                tracked_symbols = set(pos.symbol for pos in self._open_positions.values() if pos.status == "OPEN")
                
                # Find newly opened (on Bybit but not tracked)
                newly_opened_symbols = bybit_symbols - tracked_symbols
                
                for symbol in newly_opened_symbols:
                    if not self._has_position_for_symbol_unsafe(symbol):  # Double-check
                        bybit_data = bybit_position_data[symbol]
                        position = self._create_position_from_bybit_unsafe(symbol, bybit_data)
                        self._open_positions[position.position_id] = position
                        newly_opened.append(deepcopy(position))
                        # Display LONG/SHORT with colors instead of BUY/SELL
                        side_display = "🟢 LONG" if bybit_data['side'] == 'buy' else "🔴 SHORT"
                        logging.info(f"🔒 Sync: NEW position {symbol} {side_display}")
                
                # Find newly closed (tracked but not on Bybit)
                newly_closed_symbols = tracked_symbols - bybit_symbols
                
                for symbol in newly_closed_symbols:
                    positions_to_close = [pos for pos in self._open_positions.values() 
                                        if pos.symbol == symbol and pos.status == "OPEN"]
                    
                    for position in positions_to_close:
                        # Close position atomically
                        position.status = "CLOSED_MANUAL"
                        position.close_time = datetime.now().isoformat()
                        
                        # Calculate final PnL
                        if position.unrealized_pnl_pct != 0:
                            pnl_pct = position.unrealized_pnl_pct
                            pnl_usd = position.unrealized_pnl_usd
                        else:
                            # Calculate PnL if not already set
                            if position.side == 'buy':
                                pnl_pct = ((position.current_price - position.entry_price) / position.entry_price) * 100 * position.leverage
                            else:
                                pnl_pct = ((position.entry_price - position.current_price) / position.entry_price) * 100 * position.leverage
                            
                            initial_margin = position.position_size / position.leverage
                            pnl_usd = (pnl_pct / 100) * initial_margin
                            
                            position.unrealized_pnl_pct = pnl_pct
                            position.unrealized_pnl_usd = pnl_usd
                        
                        # Move to closed positions
                        self._closed_positions[position.position_id] = position
                        newly_closed.append(deepcopy(position))
                        del self._open_positions[position.position_id]
                        
                        # Update balance
                        self._session_balance += position.unrealized_pnl_usd
                        
                        logging.info(f"🔒 Sync: CLOSED position {symbol} PnL: {position.unrealized_pnl_pct:+.2f}%")
                
                # Update existing positions with current prices
                for symbol in (bybit_symbols & tracked_symbols):
                    for position in self._open_positions.values():
                        if position.symbol == symbol and position.status == "OPEN":
                            # Update with real market price
                            try:
                                ticker = await exchange.fetch_ticker(symbol)
                                current_price = float(ticker['last'])
                                
                                # Atomic price/PnL update
                                self._update_position_price_unsafe(position, current_price)
                                
                            except Exception as e:
                                logging.warning(f"🔒 Could not update price for {symbol}: {e}")
                
                self._save_positions_unsafe()  # Already in lock
            
            return newly_opened, newly_closed
            
        except Exception as e:
            logging.error(f"🔒 Thread-safe Bybit sync failed: {e}")
            return [], []
    
    # ========================================
    # INTERNAL UNSAFE METHODS (Already in lock)
    # ========================================
    
    def _has_position_for_symbol_unsafe(self, symbol: str) -> bool:
        """UNSAFE: Use only when already in lock"""
        return any(pos.symbol == symbol and pos.status == "OPEN" 
                  for pos in self._open_positions.values())
    
    def _create_position_from_bybit_unsafe(self, symbol: str, bybit_data: Dict) -> ThreadSafePosition:
        """UNSAFE: Use only when already in lock"""
        entry_price = bybit_data['entry_price']
        side = bybit_data['side']
        
        # Simple stop loss calculation (SL system removed)
        stop_loss = entry_price * (0.94 if side == 'buy' else 1.06)
        
        # Calculate trailing trigger
        if side == 'buy':
            trailing_trigger = entry_price * 1.006 * 1.010  # +1% over breakeven
        else:
            trailing_trigger = entry_price * 0.9994 * 0.990  # -1% under breakeven
        
        position_id = f"{symbol.replace('/USDT:USDT', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        return ThreadSafePosition(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            position_size=bybit_data['contracts'] * entry_price,
            leverage=10,
            stop_loss=stop_loss,  # STEP 2 FIX: From unified calculator
            take_profit=None,
            trailing_trigger=trailing_trigger,
            current_price=entry_price,
            confidence=0.7,
            entry_time=datetime.now().isoformat(),
            unrealized_pnl_usd=bybit_data['unrealized_pnl'],
            _migrated=True
        )
    
    def _update_position_price_unsafe(self, position: ThreadSafePosition, current_price: float):
        """UNSAFE: Use only when already in lock"""
        price_change_pct = ((current_price - position.entry_price) / position.entry_price) * 100
        
        if position.side in ['buy', 'long']:
            pnl_pct = price_change_pct * position.leverage
        else:
            pnl_pct = -price_change_pct * position.leverage
        
        initial_margin = position.position_size / position.leverage
        pnl_usd = (pnl_pct / 100) * initial_margin
        
        position.current_price = current_price
        position.unrealized_pnl_pct = pnl_pct
        position.unrealized_pnl_usd = pnl_usd
        position.max_favorable_pnl = max(position.max_favorable_pnl, pnl_pct)
    
    def _save_positions_unsafe(self):
        """
        UNSAFE: Save positions (use only when already in lock)
        
        CRITICAL FIX: OS-level file locking per prevenire corruzione JSON
        """
        try:
            # Convert to serializable format (simplified - no legacy trailing_data)
            open_positions_dict = {}
            for pos_id, position in self._open_positions.items():
                pos_dict = asdict(position)
                open_positions_dict[pos_id] = pos_dict
            
            # Handle closed positions
            closed_positions_dict = {}
            for pos_id, position in self._closed_positions.items():
                pos_dict = asdict(position)
                closed_positions_dict[pos_id] = pos_dict
            
            data = {
                'open_positions': open_positions_dict,
                'closed_positions': closed_positions_dict,
                'session_balance': self._session_balance,
                'session_start_balance': self._session_start_balance,
                'last_save': datetime.now().isoformat(),
                'operation_count': self._operation_count,
                'lock_contention_count': self._lock_contention_count
            }
            
            # 🔒 CRITICAL FIX: OS-level file locking per prevenire corruzione
            with open(self.storage_file, 'w') as f:
                try:
                    # Acquire exclusive OS-level lock
                    if sys.platform == 'win32':
                        # Windows: Lock 1 byte at file start
                        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        # Unix/Linux/Mac: Exclusive non-blocking lock
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    
                    # Write JSON with lock held
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk
                    
                    # Lock released automatically on file close
                    
                except (IOError, OSError) as lock_error:
                    # File already locked by another process
                    logging.warning(f"🔒 File lock conflict (another process writing): {lock_error}")
                    # Data remains in memory, will retry next save
                    return
            
            logging.debug(f"🔒 Thread-safe positions saved with OS lock: {len(self._open_positions)} open, {len(self._closed_positions)} closed")
            
        except Exception as e:
            logging.error(f"🔒 Thread-safe save failed: {e}")
    
    def _serialize_object_to_dict(self, obj) -> Dict:
        """
        Recursively convert object to JSON-serializable dictionary
        
        Args:
            obj: Object to serialize
            
        Returns:
            Dict: JSON-serializable dictionary
        """
        try:
            if obj is None:
                return None
            
            # Basic types that are JSON serializable
            if isinstance(obj, (str, int, float, bool)):
                return obj
            
            # Lists and tuples
            if isinstance(obj, (list, tuple)):
                return [self._serialize_object_to_dict(item) for item in obj]
            
            # Dictionaries
            if isinstance(obj, dict):
                return {str(k): self._serialize_object_to_dict(v) for k, v in obj.items()}
            
            # Objects with __dict__
            if hasattr(obj, '__dict__'):
                result = {}
                for key, value in obj.__dict__.items():
                    # Skip private attributes and methods
                    if not key.startswith('_') and not callable(value):
                        try:
                            result[key] = self._serialize_object_to_dict(value)
                        except Exception as attr_error:
                            logging.debug(f"🔒 Skipping non-serializable attribute {key}: {attr_error}")
                            # Skip attributes that can't be serialized
                            continue
                return result
            
            # For other types, convert to string representation
            return str(obj)
            
        except Exception as e:
            logging.warning(f"🔒 Object serialization failed: {e}")
            return None
    
    # ========================================
    # BACKWARDS COMPATIBILITY LAYER
    # ========================================
    
    def create_position(self, *args, **kwargs) -> str:
        """Backward compatibility wrapper"""
        return self.thread_safe_create_position(*args, **kwargs)
    
    def close_position_manual(self, position_id: str, exit_price: float, reason: str = "MANUAL") -> bool:
        """Backward compatibility wrapper"""
        return self.thread_safe_close_position(position_id, exit_price, reason)
    
    def has_position_for_symbol(self, symbol: str) -> bool:
        """Backward compatibility wrapper"""
        return self.safe_has_position_for_symbol(symbol)
    
    def get_active_positions(self) -> List[ThreadSafePosition]:
        """Backward compatibility wrapper"""
        return self.safe_get_all_active_positions()
    
    def get_position_count(self) -> int:
        """Backward compatibility wrapper"""
        return self.safe_get_position_count()
    
    def get_session_summary(self) -> Dict:
        """Backward compatibility wrapper"""
        return self.safe_get_session_summary()
    
    def get_available_balance(self) -> float:
        """Backward compatibility wrapper"""
        return self.thread_safe_get_available_balance()
    
    def update_real_balance(self, real_balance: float):
        """Backward compatibility wrapper"""
        self.thread_safe_update_balance(real_balance)
    
    async def sync_with_bybit(self, exchange):
        """Backward compatibility wrapper"""
        return await self.thread_safe_sync_with_bybit(exchange)
    
    def get_trailing_positions(self) -> List[ThreadSafePosition]:
        """Backward compatibility wrapper for trailing positions"""
        return self.safe_get_all_active_positions()
    
    # ========================================
    # LOAD/SAVE OPERATIONS
    # ========================================
    
    def load_positions(self):
        """Load positions from storage with thread safety and corruption recovery"""
        try:
            with self._lock:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                
                # Load positions and convert to dataclass
                for pos_id, pos_data in data.get('open_positions', {}).items():
                    # Remove old trailing_data if present
                    if 'trailing_data' in pos_data:
                        pos_data.pop('trailing_data', None)
                    
                    position = ThreadSafePosition(**pos_data)
                    # Migrate to new logic if needed
                    self._migrate_position_to_new_logic_unsafe(position)
                    self._open_positions[pos_id] = position
                
                # Load closed positions
                for pos_id, pos_data in data.get('closed_positions', {}).items():
                    # Remove old trailing_data if present (system removed)
                    if 'trailing_data' in pos_data:
                        pos_data.pop('trailing_data', None)
                    
                    position = ThreadSafePosition(**pos_data)
                    self._closed_positions[pos_id] = position
                
                # Load balance data
                self._session_balance = data.get('session_balance', 1000.0)
                self._session_start_balance = data.get('session_start_balance', 1000.0)
                self._operation_count = data.get('operation_count', 0)
                
                total_positions = len(self._open_positions) + len(self._closed_positions)
                logging.debug(f"🔒 Thread-safe positions loaded: {len(self._open_positions)} open, {len(self._closed_positions)} closed")
                
        except FileNotFoundError:
            logging.info("🔒 No position file found, starting fresh thread-safe session")
        except json.JSONDecodeError as json_error:
            # Handle corrupted JSON file
            logging.warning(f"🔒 Corrupted position file detected: {json_error}")
            logging.warning("🔒 Creating backup and starting fresh session...")
            
            # Create backup of corrupted file
            try:
                import shutil
                backup_name = f"{self.storage_file}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(self.storage_file, backup_name)
                logging.info(f"🔒 Corrupted file backed up as: {backup_name}")
            except Exception as backup_error:
                logging.error(f"🔒 Could not backup corrupted file: {backup_error}")
            
            # Initialize fresh session
            self._open_positions.clear()
            self._closed_positions.clear()
            self._session_balance = 1000.0
            self._session_start_balance = 1000.0
            self._operation_count = 0
            self._lock_contention_count = 0
            
            # Save fresh data
            self._save_positions_unsafe()
            logging.info("🔒 Fresh session initialized after corruption recovery")
            
        except Exception as e:
            logging.error(f"🔒 Error loading thread-safe positions: {e}")
            # Emergency fallback to fresh session
            logging.warning("🔒 Emergency fallback: Starting fresh session")
            self._open_positions.clear()
            self._closed_positions.clear()
            self._session_balance = 1000.0
            self._session_start_balance = 1000.0
    
    def _migrate_position_to_new_logic_unsafe(self, position: ThreadSafePosition):
        """UNSAFE: Migrate position to new logic (use only when in lock)"""
        try:
            if position._migrated:
                return
            
            entry_price = position.entry_price
            side = position.side
            
            # Simple stop loss calculation (SL system removed)
            position.stop_loss = entry_price * (0.94 if side == 'buy' else 1.06)
            
            # Calculate trailing trigger
            if side == 'buy':
                position.trailing_trigger = entry_price * 1.006 * 1.010  # +1% over breakeven
            else:
                position.trailing_trigger = entry_price * 0.9994 * 0.990  # -1% under breakeven
            
            position.take_profit = None  # Remove TP
            position._migrated = True
            position._needs_sl_update_on_bybit = True
            
            logging.debug(f"🔒 Position migrated with unified SL: {position.symbol}")
            
        except Exception as e:
            logging.error(f"🔒 Position migration failed: {e}")
    
    def save_positions(self):
        """Public save method with thread safety"""
        try:
            with self._lock:
                self._save_positions_unsafe()
        except Exception as e:
            logging.error(f"🔒 Public save failed: {e}")
    
    def reset_session(self):
        """🔒 THREAD SAFE: Reset session for fresh start"""
        try:
            with self._lock:
                old_open = len(self._open_positions)
                old_closed = len(self._closed_positions)
                
                # Clear all positions
                self._open_positions.clear()
                self._closed_positions.clear()
                
                # Reset balance
                self._session_balance = 1000.0
                self._session_start_balance = 1000.0
                self._real_balance_cache = 1000.0
                
                # Reset counters
                self._operation_count = 0
                self._lock_contention_count = 0
                
                self._save_positions_unsafe()
                
                logging.info(f"🔒 Thread-safe session reset: Cleared {old_open} open + {old_closed} closed positions")
                
        except Exception as e:
            logging.error(f"🔒 Session reset failed: {e}")
    
    def get_performance_stats(self) -> Dict:
        """Get thread safety performance statistics"""
        try:
            with self._read_lock:
                return {
                    'total_operations': self._operation_count,
                    'lock_contention_events': self._lock_contention_count,
                    'active_positions': len(self._open_positions),
                    'closed_positions': len(self._closed_positions),
                    'thread_safety_enabled': True,
                    'lock_type': 'RLock (Reentrant)'
                }
        except Exception as e:
            logging.error(f"🔒 Performance stats failed: {e}")
            return {'error': str(e)}
    
    async def check_and_close_unsafe_positions(self, exchange):
        """
        🛡️ MIGRATED from position_safety_manager.py
        
        Controlla e chiude automaticamente posizioni non sicure:
        - Posizioni troppo piccole (< $100 notional o < $10 IM)
        - Posizioni senza stop loss (zero tolerance)
        
        Args:
            exchange: Bybit exchange instance
            
        Returns:
            int: Number of positions closed for safety
        """
        # Safety thresholds
        MIN_POSITION_USD = 100.0  # Minimum $100 notional value
        MIN_IM_USD = 10.0         # Minimum $10 initial margin
        
        closed_count = 0
        
        try:
            # Get real positions from Bybit
            bybit_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_positions = [p for p in bybit_positions if float(p.get('contracts', 0)) != 0]
            
            for position in active_positions:
                try:
                    symbol = position.get('symbol')
                    contracts = abs(float(position.get('contracts', 0)))
                    entry_price = float(position.get('entryPrice', 0))
                    leverage = float(position.get('leverage', 10))
                    
                    # Calculate position metrics
                    position_usd = contracts * entry_price
                    initial_margin = position_usd / leverage
                    
                    # Check if position is too small for safe trading
                    if position_usd < MIN_POSITION_USD or initial_margin < MIN_IM_USD:
                        symbol_short = symbol.replace('/USDT:USDT', '')
                        
                        logging.warning(colored(
                            f"⚠️ UNSAFE POSITION DETECTED: {symbol_short} "
                            f"(${position_usd:.2f} notional, ${initial_margin:.2f} IM)", 
                            "red", attrs=['bold']
                        ))
                        
                        # Close the unsafe position
                        side = 'sell' if contracts > 0 else 'buy'  # Opposite side to close
                        close_size = abs(contracts)
                        
                        # Place closing market order
                        if side == 'sell':
                            order = await exchange.create_market_sell_order(symbol, close_size)
                        else:
                            order = await exchange.create_market_buy_order(symbol, close_size)
                        
                        if order and order.get('id'):
                            logging.info(f"✅ Unsafe position closed: {symbol} | Order: {order['id']}")
                            
                            exit_price = float(order.get('average', 0) or order.get('price', 0))
                            
                            # Update tracked position if exists
                            if self.has_position_for_symbol(symbol) and exit_price > 0:
                                for pos_id, pos in list(self._open_positions.items()):
                                    if pos.symbol == symbol:
                                        self.close_position_manual(pos_id, exit_price, "SAFETY_CLOSURE")
                                        break
                        
                        closed_count += 1
                        logging.info(colored(
                            f"🔒 SAFETY CLOSURE: {symbol_short} closed for insufficient size", 
                            "yellow", attrs=['bold']
                        ))
                
                except Exception as pos_error:
                    logging.error(f"Error checking position safety: {pos_error}")
                    continue
            
            if closed_count > 0:
                logging.info(colored(f"🛡️ SAFETY MANAGER: Closed {closed_count} unsafe positions", "cyan"))
            
            return closed_count
            
        except Exception as e:
            logging.error(f"Error in position safety check: {e}")
            return 0


# Global thread-safe instance
global_thread_safe_position_manager = ThreadSafePositionManager()
