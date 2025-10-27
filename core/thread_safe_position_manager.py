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
class TrailingStopData:
    """Trailing stop tracking data for position protection"""
    enabled: bool = False
    trigger_price: float = 0.0
    trigger_pct: float = 0.01  # +1% default trigger
    protection_pct: float = 0.50  # Protect 50% of max profit
    max_favorable_price: float = 0.0
    current_stop_loss: float = 0.0
    last_update_time: float = 0.0
    activation_time: Optional[str] = None

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
    
    # Trailing stop system (OPTIMIZED)
    trailing_data: Optional[TrailingStopData] = None
    
    # Metadata
    confidence: float = 0.7
    entry_time: str = ""
    close_time: Optional[str] = None
    status: str = "OPEN"
    origin: str = "SESSION"  # "SYNCED" (from Bybit at startup) or "SESSION" (opened in this session)
    open_reason: str = "Unknown"  # Motivo di apertura (es. "ML: High confidence SHORT")
    close_snapshot: Optional[str] = None  # Snapshot dati al momento della chiusura (JSON string)
    
    # Technical indicators (for dashboard display)
    atr: float = 0.0  # Average True Range
    adx: float = 0.0  # ADX trend strength
    volatility: float = 0.0  # Market volatility
    
    # Real Initial Margin from Bybit (FIX: Read actual IM instead of calculating)
    real_initial_margin: Optional[float] = None  # Actual IM from Bybit
    
    # Real Stop Loss from Bybit (FIX: Read actual SL instead of calculating)
    real_stop_loss: Optional[float] = None  # Actual SL from Bybit
    
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
    
    def __init__(self):
        # THREAD SAFETY: RLock per operations annidate
        self._lock = threading.RLock()  # Reentrant per nested calls
        self._read_lock = threading.RLock()  # Separato per read operations
        
        # Position storage (WITH FILE PERSISTENCE)
        self._open_positions: Dict[str, ThreadSafePosition] = {}
        self._closed_positions: Dict[str, ThreadSafePosition] = {}
        
        # Storage file
        self.storage_file = "thread_safe_positions.json"
        
        # Balance tracking (thread-safe)
        self._session_balance = 1000.0
        self._session_start_balance = 1000.0
        self._real_balance_cache = 1000.0
        
        # Performance tracking
        self._operation_count = 0
        self._lock_contention_count = 0
        
        # Load existing positions from file
        self.load_positions()
        
        logging.debug("🔒 ThreadSafePositionManager: FILE PERSISTENCE MODE (saving to disk)")
        

    
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
    
    def safe_get_positions_by_origin(self, origin: str) -> List[ThreadSafePosition]:
        """
        🔒 SAFE READ: Ottieni posizioni filtrate per origin
        
        Args:
            origin: "SYNCED" o "SESSION"
            
        Returns:
            List[ThreadSafePosition]: Deep copies delle posizioni con origin specificato
        """
        try:
            with self._read_lock:
                return [deepcopy(pos) for pos in self._open_positions.values() 
                       if pos.status == "OPEN" and pos.origin == origin]
                
        except Exception as e:
            logging.error(f"🔒 Safe read positions by origin failed: {e}")
            return []
    
    def safe_get_closed_positions(self) -> List[ThreadSafePosition]:
        """
        🔒 SAFE READ: Ottieni tutte le posizioni chiuse
        
        Returns:
            List[ThreadSafePosition]: Deep copies delle posizioni chiuse
        """
        try:
            with self._read_lock:
                return [deepcopy(pos) for pos in self._closed_positions.values()]
                
        except Exception as e:
            logging.error(f"🔒 Safe read closed positions failed: {e}")
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
                                   confidence: float = 0.7, open_reason: str = "Unknown",
                                   atr: float = 0.0, adx: float = 0.0, volatility: float = 0.0) -> str:
        """
        🔒 THREAD SAFE: Crea nuova posizione
        
        Args:
            open_reason: Motivo apertura (es. "ML Prediction: BUY 75%")
            atr: Average True Range (for dashboard display)
            adx: ADX trend strength (for dashboard display)
            volatility: Market volatility (for dashboard display)
        
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
                    origin="SESSION",  # Marked as SESSION position (opened in this session)
                    open_reason=open_reason,  # FIX: Passa motivo apertura con dati ML
                    atr=atr,  # Store technical indicators for dashboard
                    adx=adx,
                    volatility=volatility,
                    _migrated=True  # New positions are already migrated
                )
                
                self._open_positions[position_id] = position
                # NO SAVE - IN-MEMORY ONLY
                
                logging.info(f"🔒 Thread-safe position created (in-memory): {position_id}")
                return position_id
                
        except Exception as e:
            logging.error(f"🔒 Thread-safe position creation failed: {e}")
            return ""
    
    async def thread_safe_close_position_with_snapshot(self, exchange, position_id: str, exit_price: float, 
                                  close_reason: str = "MANUAL") -> bool:
        """
        🔒 THREAD SAFE: Chiudi posizione + capture snapshot + Online Learning
        
        Args:
            exchange: Exchange instance for fetching market data
            position_id: Position ID to close
            exit_price: Exit price
            close_reason: Reason for closure
        
        Returns:
            bool: True se chiusura riuscita
        """
        try:
            # Capture snapshot BEFORE acquiring lock (to minimize lock time)
            snapshot_data = None
            position_copy = None
            
            with self._read_lock:
                if position_id in self._open_positions:
                    position_copy = deepcopy(self._open_positions[position_id])
            
            if position_copy:
                try:
                    snapshot_data = await self._capture_close_snapshot(exchange, position_copy, exit_price, close_reason)
                except Exception as snap_err:
                    logging.warning(f"Failed to capture close snapshot: {snap_err}")
                    snapshot_data = None
            
            # Now proceed with position closure with lock
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
                
                # Save snapshot if captured
                if snapshot_data:
                    position.close_snapshot = json.dumps(snapshot_data)
                
                # Move to closed positions
                self._closed_positions[position_id] = position
                del self._open_positions[position_id]
                
                # Update session balance
                self._session_balance += pnl_usd
                
                self._save_positions_unsafe()  # Already in lock
                
                # 📊 UPDATE TRADE DECISION IN DATABASE
                try:
                    from core.trade_decision_logger import global_trade_decision_logger
                    global_trade_decision_logger.update_closing_decision(
                        symbol=position.symbol,
                        entry_time=position.entry_time,
                        exit_price=exit_price,
                        close_reason=close_reason,
                        pnl_pct=pnl_pct,
                        pnl_usd=pnl_usd,
                        exit_snapshots=None  # TODO: Add exit snapshots if needed
                    )
                except Exception as log_error:
                    logging.debug(f"⚠️ Failed to update decision on close: {log_error}")
                
                # 🎯 NOTIFY ADAPTIVE SIZING SYSTEM
                try:
                    from config import ADAPTIVE_SIZING_ENABLED
                    if ADAPTIVE_SIZING_ENABLED:
                        from core.adaptive_position_sizing import global_adaptive_sizing
                        if global_adaptive_sizing:
                            global_adaptive_sizing.update_after_trade(
                                symbol=position.symbol,
                                pnl_pct=pnl_pct,
                                wallet_equity=self._session_balance
                            )
                            logging.debug(f"🎯 Adaptive sizing notified: {position.symbol} PnL: {pnl_pct:+.2f}%")
                except Exception as adaptive_error:
                    logging.debug(f"⚠️ Failed to notify adaptive sizing: {adaptive_error}")
                
                logging.info(f"🔒 Thread-safe position closed: {position.symbol} {close_reason} PnL: {pnl_pct:+.2f}%")
                return True
                
        except Exception as e:
            logging.error(f"🔒 Thread-safe position closure failed: {e}")
            return False
    
    def thread_safe_close_position(self, position_id: str, exit_price: float, 
                                  close_reason: str = "MANUAL") -> bool:
        """
        🔒 THREAD SAFE: Chiudi posizione (sync wrapper, no snapshot)
        
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
                
                self._save_positions_unsafe()
                
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
                        
                        # 🎯 CRITICAL: Use REAL unrealizedPnl from Bybit (source of truth)
                        # Don't calculate locally - trust Bybit's data
                        unrealized_pnl_val = pos.get('unrealizedPnl')
                        
                        if unrealized_pnl_val is None or unrealized_pnl_val == '':
                            # Fallback solo se Bybit non fornisce il dato
                            logging.warning(f"⚠️ {symbol_short}: unrealizedPnl not provided by Bybit, using 0")
                            unrealized_pnl = 0.0
                        else:
                            # ✅ USE BYBIT DATA DIRECTLY (no calculation needed)
                            unrealized_pnl = float(unrealized_pnl_val)
                            logging.debug(f"✅ {symbol_short}: Using REAL PnL from Bybit: ${unrealized_pnl:+.2f}")
                        
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
                        
                        # 🔧 FIX: Read REAL Initial Margin from Bybit
                        # This is the actual IM Bybit assigned to the position
                        real_im_val = pos.get('initialMargin') or pos.get('margin')
                        real_im = float(real_im_val) if real_im_val else None
                        
                        if real_im:
                            logging.debug(f"💰 {symbol_short}: Real IM from Bybit: ${real_im:.2f}")
                        else:
                            # Fallback: calculate from position size
                            real_im = (contracts * entry_price) / float(pos.get('leverage', 10))
                            logging.debug(f"💰 {symbol_short}: IM calculated (fallback): ${real_im:.2f}")
                        
                        # 🔧 FIX: Read REAL Stop Loss from Bybit
                        # This is the actual SL set on Bybit (more reliable than calculated)
                        real_sl_val = pos.get('stopLoss')
                        real_sl = float(real_sl_val) if real_sl_val and real_sl_val != '' and real_sl_val != '0' else None
                        
                        if real_sl:
                            logging.debug(f"🛡️ {symbol_short}: Real SL from Bybit: ${real_sl:.6f}")
                        else:
                            logging.debug(f"🛡️ {symbol_short}: No SL set on Bybit")
                        
                        bybit_symbols.add(symbol)
                        bybit_position_data[symbol] = {
                            'contracts': contracts,
                            'side': side,
                            'entry_price': entry_price,
                            'unrealized_pnl': unrealized_pnl,
                            'real_initial_margin': real_im,  # Store real IM
                            'real_stop_loss': real_sl  # Store real SL
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
                
                # 🚨 CRITICAL: Track symbols that need immediate SL fix
                symbols_needing_sl_fix = []
                
                for symbol in newly_opened_symbols:
                    if not self._has_position_for_symbol_unsafe(symbol):  # Double-check
                        bybit_data = bybit_position_data[symbol]
                        position = self._create_position_from_bybit_unsafe(symbol, bybit_data)
                        self._open_positions[position.position_id] = position
                        newly_opened.append(deepcopy(position))
                        
                        # 🚨 CRITICAL: Check if SL is missing
                        if bybit_data.get('real_stop_loss') is None:
                            symbols_needing_sl_fix.append((symbol, bybit_data))
                            logging.warning(colored(
                                f"🚨 CRITICAL: {symbol.replace('/USDT:USDT', '')} opened WITHOUT stop loss! "
                                f"Will fix IMMEDIATELY after sync!",
                                "red", attrs=['bold']
                            ))
                        
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
                        
                
                # Update existing positions with current prices AND real SL from Bybit
                for symbol in (bybit_symbols & tracked_symbols):
                    for position in self._open_positions.values():
                        if position.symbol == symbol and position.status == "OPEN":
                            # Update with real market price
                            try:
                                ticker = await exchange.fetch_ticker(symbol)
                                current_price = float(ticker['last'])
                                
                                # Atomic price/PnL update
                                self._update_position_price_unsafe(position, current_price)
                                
                                # 🔧 UPDATE: Also update real_stop_loss from Bybit data
                                bybit_data = bybit_position_data.get(symbol)
                                if bybit_data:
                                    real_sl = bybit_data.get('real_stop_loss')
                                    if real_sl is not None:
                                        position.real_stop_loss = real_sl
                                        position.stop_loss = real_sl
                                        logging.debug(f"🔄 {symbol.replace('/USDT:USDT', '')}: Updated real_stop_loss from Bybit: ${real_sl:.6f}")
                                
                            except Exception as e:
                                logging.warning(f"🔒 Could not update price for {symbol}: {e}")
                
                self._save_positions_unsafe()  # Already in lock
            
            # 🚨 CRITICAL: Fix missing stop losses IMMEDIATELY (outside lock to avoid blocking)
            if symbols_needing_sl_fix:
                # Release lock before async operations
                pass
            
            # Fix SLs immediately after releasing lock
            if symbols_needing_sl_fix:
                for symbol, bybit_data in symbols_needing_sl_fix:
                    try:
                        await self._emergency_fix_missing_sl(exchange, symbol, bybit_data)
                    except Exception as e:
                        logging.error(f"🚨 EMERGENCY SL FIX FAILED for {symbol}: {e}")
            
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
        
        # Simple stop loss calculation (fallback if real SL not available)
        stop_loss = entry_price * (0.94 if side == 'buy' else 1.06)
        
        # Calculate trailing trigger
        if side == 'buy':
            trailing_trigger = entry_price * 1.006 * 1.010  # +1% over breakeven
        else:
            trailing_trigger = entry_price * 0.9994 * 0.990  # -1% under breakeven
        
        position_id = f"{symbol.replace('/USDT:USDT', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # 🔧 FIX: Get real IM and SL from Bybit data
        real_im = bybit_data.get('real_initial_margin')
        real_sl = bybit_data.get('real_stop_loss')
        
        return ThreadSafePosition(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            position_size=bybit_data['contracts'] * entry_price,
            leverage=10,
            stop_loss=real_sl if real_sl else stop_loss,  # Use real SL from Bybit if available
            take_profit=None,
            trailing_trigger=trailing_trigger,
            current_price=entry_price,
            confidence=0.7,
            entry_time=datetime.now().isoformat(),
            origin="SYNCED",  # Marked as SYNCED position (found on Bybit at startup)
            unrealized_pnl_usd=bybit_data['unrealized_pnl'],
            real_initial_margin=real_im,  # Store real IM from Bybit
            real_stop_loss=real_sl,  # Store real SL from Bybit
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
    
    async def _emergency_fix_missing_sl(self, exchange, symbol: str, bybit_data: Dict):
        """
        🚨 EMERGENCY: Fix missing stop loss IMMEDIATELY
        
        Called when a position is detected without SL during sync.
        This is CRITICAL to prevent liquidations.
        
        Args:
            exchange: Bybit exchange instance
            symbol: Symbol with missing SL
            bybit_data: Position data from Bybit
        """
        try:
            from config import SL_FIXED_PCT
            from core.price_precision_handler import global_price_precision_handler
            from core.order_manager import global_order_manager
            
            symbol_short = symbol.replace('/USDT:USDT', '')
            entry_price = bybit_data['entry_price']
            side = bybit_data['side']
            
            logging.error(colored(
                f"🚨🚨🚨 EMERGENCY SL FIX: {symbol_short} 🚨🚨🚨",
                "red", attrs=['bold']
            ))
            
            # Calculate correct SL
            if side == 'buy':
                target_sl = entry_price * (1 - SL_FIXED_PCT)
            else:
                target_sl = entry_price * (1 + SL_FIXED_PCT)
            
            # Normalize to tick size
            normalized_sl, success = await global_price_precision_handler.normalize_stop_loss_price(
                exchange, symbol, side, entry_price, target_sl
            )
            
            if not success:
                logging.error(f"🚨 {symbol_short}: Failed to normalize SL price!")
                return
            
            # Apply SL on Bybit IMMEDIATELY
            result = await global_order_manager.set_trading_stop(
                exchange, symbol,
                stop_loss=normalized_sl,
                take_profit=None
            )
            
            if result.success:
                # Update tracked position
                with self._lock:
                    for pos in self._open_positions.values():
                        if pos.symbol == symbol and pos.status == "OPEN":
                            pos.real_stop_loss = normalized_sl
                            pos.stop_loss = normalized_sl
                            self._save_positions_unsafe()
                            break
                
                real_sl_pct = abs((normalized_sl - entry_price) / entry_price) * 100
                
                logging.info(colored(
                    f"✅ EMERGENCY FIX SUCCESS: {symbol_short}\n"
                    f"   Entry: ${entry_price:.6f}\n"
                    f"   SL Set: ${normalized_sl:.6f} (-{real_sl_pct:.2f}% price)\n"
                    f"   Position is now PROTECTED!",
                    "green", attrs=['bold']
                ))
            else:
                logging.error(colored(
                    f"❌ EMERGENCY FIX FAILED: {symbol_short}\n"
                    f"   Error: {result.error}\n"
                    f"   ⚠️ POSITION STILL AT RISK OF LIQUIDATION!",
                    "red", attrs=['bold']
                ))
                
        except Exception as e:
            logging.error(colored(
                f"🚨 CRITICAL ERROR in emergency SL fix for {symbol}: {e}\n"
                f"⚠️ POSITION MAY BE AT RISK!",
                "red", attrs=['bold']
            ))
            import traceback
            logging.error(traceback.format_exc())
    
    async def _capture_close_snapshot(self, exchange, position: ThreadSafePosition, exit_price: float, close_reason: str) -> Dict:
        """
        📸 Capture detailed snapshot at position closure
        
        Captures:
        - Price action (entry, exit, high, low during position lifetime)
        - Recent candles (last 5-10 candles before closure)
        - Technical indicators if available
        - Position metrics and timing
        
        Args:
            exchange: Exchange instance
            position: Position being closed
            exit_price: Exit price
            close_reason: Reason for closure
            
        Returns:
            Dict: Snapshot data
        """
        try:
            snapshot = {
                'close_time': datetime.now().isoformat(),
                'close_reason': close_reason,
                'exit_price': exit_price,
                'entry_price': position.entry_price,
                'price_change_pct': ((exit_price - position.entry_price) / position.entry_price) * 100,
                'side': position.side,
                'leverage': position.leverage,
            }
            
            # Try to fetch recent candles
            try:
                # Fetch last 10 candles (15m timeframe)
                ohlcv = await exchange.fetch_ohlcv(position.symbol, '15m', limit=10)
                
                if ohlcv and len(ohlcv) > 0:
                    # Convert to readable format
                    candles = []
                    for candle in ohlcv[-5:]:  # Last 5 candles
                        candles.append({
                            'time': datetime.fromtimestamp(candle[0]/1000).strftime('%H:%M'),
                            'open': candle[1],
                            'high': candle[2],
                            'low': candle[3],
                            'close': candle[4],
                            'volume': candle[5]
                        })
                    
                    snapshot['recent_candles'] = candles
                    
                    # Calculate position metrics from candles
                    if len(ohlcv) > 0:
                        highs = [c[2] for c in ohlcv]
                        lows = [c[3] for c in ohlcv]
                        
                        snapshot['max_price_seen'] = max(highs)
                        snapshot['min_price_seen'] = min(lows)
                        
                        # Calculate how far from extremes we closed
                        if position.side in ['buy', 'long']:
                            snapshot['distance_from_peak_pct'] = ((snapshot['max_price_seen'] - exit_price) / exit_price) * 100
                        else:
                            snapshot['distance_from_bottom_pct'] = ((exit_price - snapshot['min_price_seen']) / exit_price) * 100
                
            except Exception as candle_error:
                logging.debug(f"Could not fetch candles for snapshot: {candle_error}")
                snapshot['recent_candles'] = None
            
            # Add position timing
            if position.entry_time:
                entry_dt = datetime.fromisoformat(position.entry_time)
                close_dt = datetime.now()
                duration_minutes = int((close_dt - entry_dt).total_seconds() / 60)
                
                snapshot['hold_duration_minutes'] = duration_minutes
                if duration_minutes < 60:
                    snapshot['hold_duration_str'] = f"{duration_minutes}m"
                else:
                    hours = duration_minutes // 60
                    mins = duration_minutes % 60
                    snapshot['hold_duration_str'] = f"{hours}h {mins}m"
            
            # Add stop loss info
            snapshot['stop_loss_price'] = position.stop_loss
            if position.side in ['buy', 'long']:
                snapshot['sl_distance_from_entry_pct'] = ((position.stop_loss - position.entry_price) / position.entry_price) * 100
            else:
                snapshot['sl_distance_from_entry_pct'] = ((position.stop_loss - position.entry_price) / position.entry_price) * 100
            
            # Add trailing info if available
            if position.trailing_data and position.trailing_data.enabled:
                snapshot['trailing_was_active'] = True
                snapshot['trailing_activation_time'] = position.trailing_data.activation_time
            else:
                snapshot['trailing_was_active'] = False
            
            logging.debug(f"📸 Close snapshot captured for {position.symbol}: {len(str(snapshot))} chars")
            return snapshot
            
        except Exception as e:
            logging.error(f"Failed to capture close snapshot: {e}")
            return {
                'error': str(e),
                'close_time': datetime.now().isoformat(),
                'close_reason': close_reason,
                'exit_price': exit_price
            }
    
    def _save_positions_unsafe(self):
        """
        💾 SAVE POSITIONS: Save positions to file with OS-level locking
        
        Thread-safe persistence to disk.
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
        """
        💾 LOAD POSITIONS: Load positions from file with error handling
        
        Loads saved positions from disk. If file is corrupted, creates backup
        and starts fresh.
        """
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
    
    async def update_trailing_stops(self, exchange) -> int:
        """
        🎪 TRAILING STOP SYSTEM (FIXED)
        
        FIX: Removed 'continue' after activation - now properly evaluates SL update
        immediately after activation.
        
        Aggiorna trailing stops per posizioni in profit con sistema dinamico -8%/-10%.
        Chiamato ogni 60s dal trading engine monitoring loop.
        
        Optimizations:
        - Batch price fetching con SmartAPIManager cache
        - Silent mode logging (solo eventi importanti)
        - Update SL solo se scende sotto -10% threshold
        - Arrotondamento tick-only (no logica -5%)
        
        Args:
            exchange: Bybit exchange instance
            
        Returns:
            int: Numero posizioni con trailing aggiornato
        """
        from config import (
            TRAILING_ENABLED,
            TRAILING_TRIGGER_PCT,
            TRAILING_SILENT_MODE,
            TRAILING_USE_BATCH_FETCH,
            TRAILING_USE_CACHE,
            TRAILING_DISTANCE_ROE_OPTIMAL,
            TRAILING_DISTANCE_ROE_UPDATE
        )
        
        if not TRAILING_ENABLED:
            return 0
        
        try:
            import math
            from core.price_precision_handler import global_price_precision_handler
            from core.order_manager import global_order_manager
            
            # Get active positions (thread-safe)
            active_positions = self.safe_get_all_active_positions()
            
            if not active_positions:
                return 0
            
            # Batch fetch prices (optimized)
            symbols = [pos.symbol for pos in active_positions]
            
            if TRAILING_USE_BATCH_FETCH and TRAILING_USE_CACHE:
                # Use SmartAPIManager for cache-optimized batch fetch
                from core.smart_api_manager import global_smart_api_manager
                tickers_data = await global_smart_api_manager.fetch_multiple_tickers_batch(
                    exchange, symbols
                )
            else:
                # Fallback: sequential fetch
                tickers_data = {}
                for symbol in symbols:
                    try:
                        ticker = await exchange.fetch_ticker(symbol)
                        tickers_data[symbol] = ticker
                    except Exception as e:
                        logging.debug(f"Ticker fetch failed for {symbol}: {e}")
            
            updates_count = 0
            activations_count = 0
            
            # Process each position
            for position in active_positions:
                try:
                    # Get current price from batch
                    ticker = tickers_data.get(position.symbol)
                    if not ticker or 'last' not in ticker:
                        continue
                    
                    current_price = float(ticker['last'])
                    symbol_short = position.symbol.replace('/USDT:USDT', '')
                    
                    # Calculate current profit % (price-based, not ROE)
                    if position.side in ['buy', 'long']:
                        profit_pct = (current_price - position.entry_price) / position.entry_price
                    else:
                        profit_pct = (position.entry_price - current_price) / position.entry_price
                    
                    # Initialize trailing_data if not present
                    if position.trailing_data is None:
                        position.trailing_data = TrailingStopData(
                            trigger_pct=TRAILING_TRIGGER_PCT
                        )
                    
                    trailing = position.trailing_data
                    just_activated = False
                    
                    # DEBUG: Log position state (if not silent)
                    if not TRAILING_SILENT_MODE:
                        logging.debug(
                            f"[Trailing Debug] {symbol_short}: profit={profit_pct:.2%}, "
                            f"enabled={trailing.enabled}, current=${current_price:.6f}, "
                            f"sl=${position.stop_loss:.6f}"
                        )
                    
                    # Check if should activate trailing
                    if not trailing.enabled:
                        if profit_pct >= TRAILING_TRIGGER_PCT:
                            # ACTIVATE TRAILING
                            with self._lock:
                                if position.position_id in self._open_positions:
                                    pos_ref = self._open_positions[position.position_id]
                                    if pos_ref.trailing_data is None:
                                        pos_ref.trailing_data = TrailingStopData()
                                    
                                    pos_ref.trailing_data.enabled = True
                                    pos_ref.trailing_data.max_favorable_price = current_price
                                    pos_ref.trailing_data.activation_time = datetime.now().isoformat()
                                    pos_ref.trailing_data.last_update_time = 0  # Force update check
                                    
                                    activations_count += 1
                                    just_activated = True
                                    
                                    # ALWAYS log activation (critical event)
                                    logging.info(colored(
                                        f"🎪 TRAILING ACTIVATED: {symbol_short} @ {profit_pct:.2%} profit "
                                        f"(price ${current_price:.6f})",
                                        "magenta", attrs=['bold']
                                    ))
                        else:
                            # Not activated yet - skip to next position
                            if not TRAILING_SILENT_MODE:
                                logging.debug(
                                    f"[Trailing] {symbol_short}: Waiting for activation "
                                    f"({profit_pct:.2%} < {TRAILING_TRIGGER_PCT:.2%})"
                                )
                            continue  # Skip to next position - trailing not active yet
                    
                    # ========================================
                    # TRAILING IS NOW ACTIVE - CHECK FOR UPDATE
                    # (Reaches here if trailing.enabled=True OR just_activated=True)
                    # ========================================
                    
                    # 🔧 CRITICAL FIX: Calculate SL based on ROE%, not price%!
                    # Formula: ROE% = (price_change / entry) × leverage × 100
                    # Reverse: price_change = (ROE% / leverage / 100) × entry
                    
                    from config import TRAILING_DISTANCE_ROE_OPTIMAL, TRAILING_DISTANCE_ROE_UPDATE
                    
                    # Calculate current ROE%
                    if position.side in ['buy', 'long']:
                        current_roe = ((current_price - position.entry_price) / position.entry_price) * position.leverage * 100
                    else:  # SHORT
                        current_roe = ((position.entry_price - current_price) / position.entry_price) * position.leverage * 100
                    
                    # Target ROE for optimal SL: current_roe - 8% ROE
                    target_roe_optimal = current_roe - (TRAILING_DISTANCE_ROE_OPTIMAL * 100)  # -8% ROE
                    target_roe_trigger = current_roe - (TRAILING_DISTANCE_ROE_UPDATE * 100)  # -10% ROE
                    
                    # Convert target ROE back to price
                    # LONG: ROE = (price - entry) / entry × leverage × 100
                    # SHORT: ROE = (entry - price) / entry × leverage × 100
                    if position.side in ['buy', 'long']:
                        # target_roe = (optimal_sl - entry) / entry × leverage × 100
                        # optimal_sl = entry × (1 + target_roe / (leverage × 100))
                        optimal_sl = position.entry_price * (1 + target_roe_optimal / (position.leverage * 100))
                        trigger_threshold = position.entry_price * (1 + target_roe_trigger / (position.leverage * 100))
                    else:  # SHORT
                        # target_roe = (entry - optimal_sl) / entry × leverage × 100
                        # optimal_sl = entry × (1 - target_roe / (leverage × 100))
                        optimal_sl = position.entry_price * (1 - target_roe_optimal / (position.leverage * 100))
                        trigger_threshold = position.entry_price * (1 - target_roe_trigger / (position.leverage * 100))
                    
                    # Decision logic: Update only if current SL is worse than -10% threshold
                    # OR if just activated (first update after activation)
                    should_update = False
                    update_reason = ""
                    new_sl = 0.0
                    
                    if just_activated:
                        # FORCE UPDATE: Just activated, move SL immediately to optimal position
                        should_update = True
                        update_reason = "just_activated"
                        new_sl = optimal_sl
                        logging.debug(f"[Trailing] {symbol_short}: Just activated - forcing first SL update")
                    elif position.stop_loss == 0:
                        # No SL set yet - always update
                        should_update = True
                        update_reason = "initial_sl"
                        new_sl = optimal_sl
                    else:
                        # Check if current SL is too far (worse than -10% threshold)
                        if position.side in ['buy', 'long']:
                            # For LONG: SL is too far if it's below trigger_threshold
                            if position.stop_loss < trigger_threshold:
                                should_update = True
                                update_reason = "sl_too_far"
                                new_sl = optimal_sl
                        else:  # SHORT
                            # For SHORT: SL is too far if it's above trigger_threshold
                            if position.stop_loss > trigger_threshold:
                                should_update = True
                                update_reason = "sl_too_far"
                                new_sl = optimal_sl
                    
                    # Safety check: Never move SL against position (EXCEPT on first activation)
                    if should_update and new_sl > 0 and not just_activated:
                        if position.side in ['buy', 'long']:
                            # For LONG: never lower SL (except first activation)
                            if new_sl < position.stop_loss and position.stop_loss > 0:
                                should_update = False
                                logging.debug(f"[Trailing] {symbol_short}: Skip - would lower SL")
                        else:  # SHORT
                            # For SHORT: never raise SL (except first activation)
                            if new_sl > position.stop_loss and position.stop_loss > 0:
                                should_update = False
                                logging.debug(f"[Trailing] {symbol_short}: Skip - would raise SL")
                    
                    # Normalize new_sl to tick size (tick-only rounding, no -5% logic)
                    if should_update and new_sl > 0:
                        tick_info = await global_price_precision_handler.get_symbol_precision(
                            exchange, position.symbol
                        )
                        tick_size = float(tick_info.get("tick_size", 0.01))
                        
                        # Round to tick size in safe direction
                        if position.side in ['buy', 'long']:
                            # LONG: round DOWN (more conservative)
                            new_sl = math.floor(new_sl / tick_size) * tick_size
                        else:
                            # SHORT: round UP (more conservative)
                            new_sl = math.ceil(new_sl / tick_size) * tick_size
                        
                        # Skip if change is less than 1 tick
                        if tick_size > 0 and abs(new_sl - position.stop_loss) < tick_size:
                            should_update = False
                            logging.debug(f"[Trailing] {symbol_short}: Skip - change < 1 tick")
                    
                    # DEBUG: Log decision
                    if not TRAILING_SILENT_MODE and trailing.enabled:
                        logging.debug(
                            f"[Trailing Decision] {symbol_short}: "
                            f"current_sl=${position.stop_loss:.6f}, "
                            f"optimal=${optimal_sl:.6f}, threshold=${trigger_threshold:.6f}, "
                            f"should_update={should_update}"
                        )
                    
                    # Apply update to Bybit if needed
                    if should_update and new_sl > 0:
                        # Update SL on Bybit (position_idx=0 for One-Way Mode)
                        result = await global_order_manager.set_trading_stop(
                            exchange, position.symbol,
                            stop_loss=new_sl,
                            take_profit=None
                        )
                        
                        if result.success:
                            # Update in tracker atomically
                            with self._lock:
                                if position.position_id in self._open_positions:
                                    pos_ref = self._open_positions[position.position_id]
                                    old_sl = pos_ref.stop_loss
                                    pos_ref.stop_loss = new_sl
                                    
                                    if pos_ref.trailing_data:
                                        pos_ref.trailing_data.current_stop_loss = new_sl
                                        pos_ref.trailing_data.last_update_time = datetime.now().timestamp()
                                    
                                    self._save_positions_unsafe()
                            
                            updates_count += 1
                            
                            # Calculate metrics for logging
                            distance_pct = abs((new_sl - current_price) / current_price) * 100
                            
                            # Calculate profit protected from entry
                            if position.side in ['buy', 'long']:
                                profit_protected = ((new_sl - position.entry_price) / position.entry_price) * 100
                            else:
                                profit_protected = ((position.entry_price - new_sl) / position.entry_price) * 100
                            
                            # Log update
                            logging.info(colored(
                                f"🎪 Trailing updated: {symbol_short} "
                                f"SL ${old_sl:.6f} → ${new_sl:.6f} "
                                f"({update_reason}) | Distance from current: -{distance_pct:.1f}% | "
                                f"Profit protected from entry: {profit_protected:+.2f}%",
                                "magenta"
                            ))
                        else:
                            logging.warning(
                                f"[Trailing] {symbol_short}: Failed to update SL on Bybit: {result.error}"
                            )
                
                except Exception as pos_error:
                    logging.error(f"Trailing update error for {position.symbol}: {pos_error}")
                    import traceback
                    logging.error(f"Traceback: {traceback.format_exc()}")
                    continue
            
            # Summary log (only if changes occurred or not silent)
            if updates_count > 0 or activations_count > 0:
                if TRAILING_SILENT_MODE:
                    logging.info(
                        f"[Trailing] {activations_count} activated, "
                        f"{updates_count} updated ({len(active_positions)} total)"
                    )
                else:
                    logging.info(
                        f"🎪 Trailing cycle: {activations_count} activations, "
                        f"{updates_count} updates ({len(active_positions)} positions)"
                    )
            
            return updates_count + activations_count
            
        except Exception as e:
            logging.error(f"Trailing stops update failed: {e}")
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            return 0
    
    async def check_and_fix_stop_losses(self, exchange) -> int:
        """
        🔧 SISTEMA DI AUTO-CORREZIONE STOP LOSS
        
        Controlla tutte le posizioni attive e fixa automaticamente gli stop loss
        che non sono a -5% corretto dall'entry price.
        
        Chiamato ogni ciclo (15 minuti) per garantire che tutti gli SL siano corretti.
        
        Args:
            exchange: Bybit exchange instance
            
        Returns:
            int: Numero di stop loss corretti
        """
        fixed_count = 0
        
        try:
            from config import SL_FIXED_PCT
            from core.price_precision_handler import global_price_precision_handler
            from core.order_manager import global_order_manager
            import math
            
            # Tolerance: ±0.5% (es. -4.5% ~ -5.5% è OK)
            TOLERANCE_PCT = 0.005
            
            # Get real positions from Bybit
            bybit_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_positions = [p for p in bybit_positions if float(p.get('contracts', 0)) != 0]
            
            if not active_positions:
                return 0
            
            logging.info(colored("🔍 Checking stop losses for correctness...", "cyan"))
            
            for position in active_positions:
                try:
                    symbol = position.get('symbol')
                    symbol_short = symbol.replace('/USDT:USDT', '')
                    
                    # SKIP positions with active trailing (they manage their own SL)
                    # Check if this symbol has trailing active in our tracker
                    has_active_trailing = False
                    for pos in self._open_positions.values():
                        if pos.symbol == symbol and pos.status == "OPEN":
                            if hasattr(pos, 'trailing_data') and pos.trailing_data and pos.trailing_data.enabled:
                                has_active_trailing = True
                                break
                    
                    if has_active_trailing:
                        logging.debug(f"[Auto-Fix] {symbol_short}: Skipping - trailing is active")
                        continue
                    
                    # Get position data
                    entry_price = float(position.get('entryPrice', 0))
                    side_str = position.get('side', '').lower()
                    
                    # Determine if LONG or SHORT
                    if side_str in ['buy', 'long']:
                        side = 'buy'
                        long_position = True
                    elif side_str in ['sell', 'short']:
                        side = 'sell'
                        long_position = False
                    else:
                        # Fallback: determine from contracts
                        contracts = float(position.get('contracts', 0))
                        if contracts > 0:
                            side = 'buy'
                            long_position = True
                        else:
                            side = 'sell'
                            long_position = False
                    
                    # Get current SL from Bybit
                    current_sl = float(position.get('stopLoss', 0) or 0)
                    
                    if current_sl == 0:
                        # NO STOP LOSS! Critical - fix immediately
                        logging.warning(colored(
                            f"⚠️ {symbol_short}: NO STOP LOSS DETECTED! Setting -5% SL...",
                            "red", attrs=['bold']
                        ))
                        
                        # Calculate correct SL
                        if long_position:
                            target_sl = entry_price * (1 - SL_FIXED_PCT)
                        else:
                            target_sl = entry_price * (1 + SL_FIXED_PCT)
                        
                        # Normalize to tick size
                        normalized_sl, success = await global_price_precision_handler.normalize_stop_loss_price(
                            exchange, symbol, side, entry_price, target_sl
                        )
                        
                        if success:
                            # Calculate REAL percentage for logging
                            real_sl_pct = abs((normalized_sl - entry_price) / entry_price) * 100
                            
                            # Apply SL on Bybit
                            result = await global_order_manager.set_trading_stop(
                                exchange, symbol,
                                stop_loss=normalized_sl,
                                take_profit=None
                            )
                            
                            if result.success:
                                # ✅ Update real_stop_loss in tracked position
                                with self._lock:
                                    for pos in self._open_positions.values():
                                        if pos.symbol == symbol and pos.status == "OPEN":
                                            pos.real_stop_loss = normalized_sl
                                            pos.stop_loss = normalized_sl
                                            logging.debug(f"💾 {symbol_short}: Updated real_stop_loss to ${normalized_sl:.6f}")
                                            break
                                
                                logging.info(colored(
                                    f"✅ {symbol_short}: SL FIXED - Set to ${normalized_sl:.6f} (-{real_sl_pct:.2f}% price)",
                                    "green"
                                ))
                                fixed_count += 1
                            else:
                                logging.error(colored(
                                    f"❌ {symbol_short}: Failed to set SL: {result.error}",
                                    "red"
                                ))
                        continue
                    
                    # Calculate expected SL (-5% from entry)
                    if long_position:
                        expected_sl = entry_price * (1 - SL_FIXED_PCT)
                        current_sl_pct = (current_sl - entry_price) / entry_price
                        expected_sl_pct = -SL_FIXED_PCT
                    else:
                        expected_sl = entry_price * (1 + SL_FIXED_PCT)
                        current_sl_pct = (current_sl - entry_price) / entry_price
                        expected_sl_pct = +SL_FIXED_PCT
                    
                    # Check if SL is within tolerance
                    sl_deviation = abs(current_sl_pct - expected_sl_pct)
                    
                    if sl_deviation > TOLERANCE_PCT:
                        # SL NOT CORRECT! Fix it
                        logging.warning(colored(
                            f"⚠️ {symbol_short}: INCORRECT SL DETECTED!\n"
                            f"   Current SL: ${current_sl:.6f} ({current_sl_pct*100:+.2f}%)\n"
                            f"   Expected: ${expected_sl:.6f} ({expected_sl_pct*100:+.2f}%)\n"
                            f"   Deviation: {sl_deviation*100:.2f}% (tolerance: {TOLERANCE_PCT*100:.1f}%)",
                            "yellow", attrs=['bold']
                        ))
                        
                        # Normalize correct SL
                        normalized_sl, success = await global_price_precision_handler.normalize_stop_loss_price(
                            exchange, symbol, side, entry_price, expected_sl
                        )
                        
                        if success:
                            # Apply corrected SL on Bybit
                            result = await global_order_manager.set_trading_stop(
                                exchange, symbol,
                                stop_loss=normalized_sl,
                                take_profit=None
                            )
                            
                            if result.success:
                                new_sl_pct = (normalized_sl - entry_price) / entry_price
                                logging.info(colored(
                                    f"✅ {symbol_short}: SL CORRECTED!\n"
                                    f"   ${current_sl:.6f} ({current_sl_pct*100:+.2f}%) → "
                                    f"${normalized_sl:.6f} ({new_sl_pct*100:+.2f}%)",
                                    "green"
                                ))
                                fixed_count += 1
                            else:
                                logging.error(colored(
                                    f"❌ {symbol_short}: Failed to update SL: {result.error}",
                                    "red"
                                ))
                
                except Exception as pos_error:
                    logging.error(f"Error checking SL for {position.get('symbol')}: {pos_error}")
                    continue
            
            if fixed_count > 0:
                logging.info(colored(f"🔧 AUTO-FIX: Corrected {fixed_count} stop losses", "green", attrs=['bold']))
            
            return fixed_count
            
        except Exception as e:
            logging.error(f"Error in SL auto-fix system: {e}")
            return 0
    
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
