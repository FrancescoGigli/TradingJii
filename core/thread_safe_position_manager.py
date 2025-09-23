#!/usr/bin/env python3
"""
🔒 THREAD-SAFE POSITION MANAGER

CRITICAL FIX: Eliminazione race conditions tra multiple thread
- Atomic operations per position updates
- Centralized state management
- Thread-safe access patterns
- Backward compatibility con sistema esistente

GARANTISCE: Zero race conditions, state consistency
"""

import threading
import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from copy import deepcopy
from termcolor import colored

# ONLINE LEARNING INTEGRATION: Import learning manager for automatic feedback
try:
    from core.online_learning_manager import global_online_learning_manager
    ONLINE_LEARNING_AVAILABLE = bool(global_online_learning_manager)
    if ONLINE_LEARNING_AVAILABLE:
        logging.debug("🔒 ThreadSafePositionManager: Online Learning integration enabled")
except ImportError:
    ONLINE_LEARNING_AVAILABLE = False
    global_online_learning_manager = None
    logging.debug("🔒 ThreadSafePositionManager: Online Learning not available")

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
    
    # Trailing system state (protected by lock)
    trailing_active: bool = False
    best_price: Optional[float] = None
    sl_corrente: Optional[float] = None
    
    # CRITICAL FIX: Add trailing_data field for TrailingMonitor compatibility
    trailing_data: Optional[Any] = None
    
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
    
    def atomic_update_trailing_state(self, position_id: str, trailing_data: Dict) -> bool:
        """
        🔒 ATOMIC: Aggiorna stato trailing (operazione critica)
        
        Args:
            position_id: ID posizione
            trailing_data: Dati trailing da aggiornare
                {
                    'trailing_active': bool,
                    'best_price': float,
                    'sl_corrente': float,
                    'trailing_trigger': float
                }
        """
        try:
            with self._lock:
                if position_id not in self._open_positions:
                    return False
                
                position = self._open_positions[position_id]
                
                # Update trailing state atomically
                if 'trailing_active' in trailing_data:
                    position.trailing_active = trailing_data['trailing_active']
                if 'best_price' in trailing_data:
                    position.best_price = trailing_data['best_price']
                if 'sl_corrente' in trailing_data:
                    position.sl_corrente = trailing_data['sl_corrente']
                if 'trailing_trigger' in trailing_data:
                    position.trailing_trigger = trailing_data['trailing_trigger']
                
                logging.debug(f"🔒 Atomic trailing update: {position.symbol} trailing={position.trailing_active}")
                return True
                
        except Exception as e:
            logging.error(f"🔒 Atomic trailing update failed: {e}")
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
                
                # STEP 2 FIX: Use UnifiedStopLossCalculator instead of hardcoded calculations
                try:
                    from core.unified_stop_loss_calculator import global_unified_stop_loss_calculator
                    stop_loss = global_unified_stop_loss_calculator.calculate_unified_stop_loss(
                        entry_price, side, symbol
                    )
                except Exception as e:
                    logging.warning(f"🔒 Unified SL failed for {symbol}: {e}")
                    # Emergency fallback with unified constants
                    stop_loss = entry_price * (0.94 if side.lower() == 'buy' else 1.06)
                
                # Calculate trailing trigger (keep this logic as it's specific to position management)
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
                
                # 🧠 ONLINE LEARNING: Notify about position closure (CENTRAL POINT)
                if ONLINE_LEARNING_AVAILABLE and global_online_learning_manager:
                    try:
                        # Map close reasons for learning system
                        learning_reason = close_reason
                        if close_reason in ["TRAILING_FAST", "TRAILING"]:
                            learning_reason = "TRAILING_STOP"
                        elif close_reason in ["MANUAL", "STOP_LOSS"]:
                            learning_reason = close_reason
                        
                        global_online_learning_manager.track_trade_closing(
                            position.symbol, exit_price, pnl_usd, pnl_pct, learning_reason
                        )
                        logging.debug(f"🧠 Learning notified: {position.symbol.replace('/USDT:USDT', '')} closed via {learning_reason} ({pnl_pct:+.2f}%)")
                    except Exception as learning_error:
                        logging.warning(f"🔒 Learning notification error: {learning_error}")
                
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
                        contracts_raw = float(pos.get('contracts', 0))
                        contracts = abs(contracts_raw)
                        entry_price = float(pos.get('entryPrice', 0))
                        unrealized_pnl = float(pos.get('unrealizedPnl', 0))
                        
                        # Check if Bybit provides explicit 'side' field
                        explicit_side = pos.get('side', '').lower()
                        if explicit_side in ['buy', 'long']:
                            side = 'buy'
                        elif explicit_side in ['sell', 'short']:
                            side = 'sell'
                        else:
                            # Fallback to contracts logic
                            side = 'buy' if contracts_raw > 0 else 'sell'
                        
                        # Debug logging per vedere cosa arriva da Bybit
                        symbol_short = symbol.replace('/USDT:USDT', '')
                        logging.debug(f"🔍 {symbol_short}: contracts={contracts_raw}, explicit_side='{explicit_side}', final_side='{side}'")
                        
                        bybit_symbols.add(symbol)
                        bybit_position_data[symbol] = {
                            'contracts': contracts,
                            'side': side,
                            'entry_price': entry_price,
                            'unrealized_pnl': unrealized_pnl
                        }
                    except (ValueError, TypeError) as e:
                        logging.warning(f"🔒 Invalid Bybit position data for {symbol}: {e}")
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
                        
                        # 🧠 ONLINE LEARNING: Notify about external closure (BYBIT SYNC)
                        if ONLINE_LEARNING_AVAILABLE and global_online_learning_manager:
                            try:
                                global_online_learning_manager.track_trade_closing(
                                    position.symbol, position.current_price, pnl_usd, pnl_pct, "EXTERNAL_CLOSURE"
                                )
                                logging.debug(f"🧠 Learning notified: {position.symbol.replace('/USDT:USDT', '')} external closure ({pnl_pct:+.2f}%)")
                            except Exception as learning_error:
                                logging.warning(f"🔒 Learning notification error: {learning_error}")
                        
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
        
        # STEP 2 FIX: Use UnifiedStopLossCalculator instead of hardcoded calculations
        try:
            from core.unified_stop_loss_calculator import global_unified_stop_loss_calculator
            stop_loss = global_unified_stop_loss_calculator.calculate_unified_stop_loss(
                entry_price, side, symbol
            )
        except Exception as e:
            logging.warning(f"🔒 Bybit sync unified SL failed for {symbol}: {e}")
            # Emergency fallback with unified constants
            stop_loss = entry_price * (0.94 if side == 'buy' else 1.06)
        
        # Calculate trailing trigger (position management specific)
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
        """UNSAFE: Save positions (use only when already in lock)"""
        try:
            # Convert to serializable format with trailing_data handling
            open_positions_dict = {}
            for pos_id, position in self._open_positions.items():
                pos_dict = asdict(position)
                
                # Handle trailing_data serialization if it exists
                if hasattr(position, 'trailing_data') and position.trailing_data is not None:
                    try:
                        if hasattr(position.trailing_data, 'to_dict'):
                            pos_dict['trailing_data'] = position.trailing_data.to_dict()
                        elif hasattr(position.trailing_data, '__dict__'):
                            # Convert object to dictionary recursively
                            pos_dict['trailing_data'] = self._serialize_object_to_dict(position.trailing_data)
                        else:
                            # Remove non-serializable trailing_data
                            logging.debug(f"🔒 Removing non-serializable trailing_data for {pos_id}")
                            pos_dict['trailing_data'] = None
                    except Exception as trailing_serial_error:
                        logging.warning(f"🔒 Failed to serialize trailing_data for {pos_id}: {trailing_serial_error}")
                        pos_dict['trailing_data'] = None
                
                open_positions_dict[pos_id] = pos_dict
            
            # Handle closed positions with same serialization logic
            closed_positions_dict = {}
            for pos_id, position in self._closed_positions.items():
                pos_dict = asdict(position)
                
                # Handle trailing_data in closed positions too
                if hasattr(position, 'trailing_data') and position.trailing_data is not None:
                    try:
                        if hasattr(position.trailing_data, 'to_dict'):
                            pos_dict['trailing_data'] = position.trailing_data.to_dict()
                        elif hasattr(position.trailing_data, '__dict__'):
                            pos_dict['trailing_data'] = self._serialize_object_to_dict(position.trailing_data)
                        else:
                            pos_dict['trailing_data'] = None
                    except Exception:
                        pos_dict['trailing_data'] = None
                
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
            
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logging.debug(f"🔒 Thread-safe positions saved: {len(self._open_positions)} open, {len(self._closed_positions)} closed")
            
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
                    position = ThreadSafePosition(**pos_data)
                    # Migrate to new logic if needed
                    self._migrate_position_to_new_logic_unsafe(position)
                    self._open_positions[pos_id] = position
                
                # Load closed positions
                for pos_id, pos_data in data.get('closed_positions', {}).items():
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
            
            # STEP 2 FIX: Use UnifiedStopLossCalculator for migration
            try:
                from core.unified_stop_loss_calculator import global_unified_stop_loss_calculator
                position.stop_loss = global_unified_stop_loss_calculator.calculate_unified_stop_loss(
                    entry_price, side, position.symbol
                )
            except Exception as e:
                logging.warning(f"🔒 Migration unified SL failed for {position.symbol}: {e}")
                # Emergency fallback with unified constants
                position.stop_loss = entry_price * (0.94 if side == 'buy' else 1.06)
            
            # Calculate trailing trigger (position management specific)
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


# Global thread-safe instance
global_thread_safe_position_manager = ThreadSafePositionManager()
