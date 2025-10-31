#!/usr/bin/env python3
"""
🔒 POSITION CORE OPERATIONS

Core CRUD operations with thread-safe atomic updates.
Handles position lifecycle, balance management, and session summaries.
"""

import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from copy import deepcopy

from .position_data import ThreadSafePosition, TrailingStopData
from .position_io import PositionIO


class PositionCore:
    """Core position management with thread-safe operations"""
    
    def __init__(self, io: Optional[PositionIO] = None):
        # Thread safety locks
        self._lock = threading.RLock()
        self._read_lock = threading.RLock()
        
        # Position storage
        self._open_positions: Dict[str, ThreadSafePosition] = {}
        self._closed_positions: Dict[str, ThreadSafePosition] = {}
        
        # Balance tracking
        self._session_balance = 1000.0
        self._session_start_balance = 1000.0
        self._real_balance_cache = 1000.0
        
        # Performance tracking
        self._operation_count = 0
        self._lock_contention_count = 0
        
        # Memory management
        self.MAX_CLOSED_POSITIONS = 100  # Keep only last 100 closed positions
        
        # I/O handler
        self.io = io or PositionIO()
        
        # Load existing positions
        self._load_positions()
        
        logging.debug("🔒 PositionCore initialized")
    
    # ========================================
    # ATOMIC WRITE OPERATIONS
    # ========================================
    
    def atomic_update_position(self, position_id: str, updates: Dict[str, Any]) -> bool:
        """Atomic update of position fields"""
        try:
            with self._lock:
                self._operation_count += 1
                
                if position_id not in self._open_positions:
                    logging.warning(f"Position {position_id} not found for update")
                    return False
                
                position = self._open_positions[position_id]
                
                for field, value in updates.items():
                    if hasattr(position, field):
                        setattr(position, field, value)
                        logging.debug(f"Updated {position_id}.{field} = {value}")
                
                self._save_positions()
                return True
                
        except Exception as e:
            logging.error(f"Atomic update failed: {e}")
            return False
    
    def atomic_update_price_and_pnl(self, position_id: str, current_price: float) -> bool:
        """Atomic update of price and calculated PnL"""
        try:
            with self._lock:
                if position_id not in self._open_positions:
                    return False
                
                position = self._open_positions[position_id]
                
                # Calculate PnL
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
                
                return True
                
        except Exception as e:
            logging.error(f"Price/PnL update failed: {e}")
            return False
    
    # ========================================
    # SAFE READ OPERATIONS
    # ========================================
    
    def safe_get_position(self, position_id: str) -> Optional[ThreadSafePosition]:
        """Get deep copy of position (read-only)"""
        try:
            with self._read_lock:
                if position_id in self._open_positions:
                    return deepcopy(self._open_positions[position_id])
                return None
        except Exception as e:
            logging.error(f"Safe read failed: {e}")
            return None
    
    def safe_get_all_active_positions(self) -> List[ThreadSafePosition]:
        """Get all active positions (deep copies)"""
        try:
            with self._read_lock:
                return [deepcopy(pos) for pos in self._open_positions.values() 
                       if pos.status == "OPEN"]
        except Exception as e:
            logging.error(f"Safe read all failed: {e}")
            return []
    
    def safe_get_positions_by_origin(self, origin: str) -> List[ThreadSafePosition]:
        """Get positions filtered by origin"""
        try:
            with self._read_lock:
                return [deepcopy(pos) for pos in self._open_positions.values() 
                       if pos.status == "OPEN" and pos.origin == origin]
        except Exception as e:
            logging.error(f"Safe read by origin failed: {e}")
            return []
    
    def safe_get_closed_positions(self) -> List[ThreadSafePosition]:
        """Get all closed positions"""
        try:
            with self._read_lock:
                return [deepcopy(pos) for pos in self._closed_positions.values()]
        except Exception as e:
            logging.error(f"Safe read closed failed: {e}")
            return []
    
    def safe_has_position_for_symbol(self, symbol: str) -> bool:
        """Check if position exists for symbol"""
        try:
            with self._read_lock:
                return any(pos.symbol == symbol and pos.status == "OPEN" 
                          for pos in self._open_positions.values())
        except Exception as e:
            logging.error(f"Symbol check failed: {e}")
            return False
    
    def safe_get_position_count(self) -> int:
        """Count active positions"""
        try:
            with self._read_lock:
                return len([pos for pos in self._open_positions.values() 
                          if pos.status == "OPEN"])
        except Exception as e:
            logging.error(f"Position count failed: {e}")
            return 0
    
    def safe_get_session_summary(self) -> Dict:
        """Get session statistics"""
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
            logging.error(f"Session summary failed: {e}")
            return {'balance': 0.0, 'active_positions': 0, 'closed_positions': 0}
    
    # ========================================
    # POSITION LIFECYCLE
    # ========================================
    
    def create_position(self, symbol: str, side: str, entry_price: float,
                       position_size: float, leverage: int = 10, 
                       confidence: float = 0.7, open_reason: str = "Unknown",
                       atr: float = 0.0, adx: float = 0.0, volatility: float = 0.0) -> str:
        """Create new position"""
        try:
            with self._lock:
                position_id = f"{symbol.replace('/USDT:USDT', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                
                stop_loss = entry_price * (0.94 if side.lower() == 'buy' else 1.06)
                
                if side.lower() == 'buy':
                    trailing_trigger = entry_price * 1.006 * 1.010
                else:
                    trailing_trigger = entry_price * 0.9994 * 0.990
                
                position = ThreadSafePosition(
                    position_id=position_id,
                    symbol=symbol,
                    side=side.lower(),
                    entry_price=entry_price,
                    position_size=position_size,
                    leverage=leverage,
                    stop_loss=stop_loss,
                    take_profit=None,
                    trailing_trigger=trailing_trigger,
                    current_price=entry_price,
                    confidence=confidence,
                    entry_time=datetime.now().isoformat(),
                    origin="SESSION",
                    open_reason=open_reason,
                    atr=atr,
                    adx=adx,
                    volatility=volatility,
                    _migrated=True
                )
                
                self._open_positions[position_id] = position
                
                logging.info(f"✅ Position created: {position_id}")
                return position_id
                
        except Exception as e:
            logging.error(f"Position creation failed: {e}")
            return ""
    
    def close_position(self, position_id: str, exit_price: float, 
                      close_reason: str = "MANUAL") -> bool:
        """Close position"""
        try:
            with self._lock:
                if position_id not in self._open_positions:
                    return False
                
                position = self._open_positions[position_id]
                
                # Calculate final PnL
                if position.side == 'buy':
                    pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100 * position.leverage
                else:
                    pnl_pct = ((position.entry_price - exit_price) / position.entry_price) * 100 * position.leverage
                
                initial_margin = position.position_size / position.leverage
                pnl_usd = (pnl_pct / 100) * initial_margin
                
                # Update position
                position.status = f"CLOSED_{close_reason}"
                position.close_time = datetime.now().isoformat()
                position.unrealized_pnl_pct = pnl_pct
                position.unrealized_pnl_usd = pnl_usd
                position.current_price = exit_price
                position.exit_price = exit_price  # Set exit price for closed position
                
                # Set aliases for dashboard compatibility
                position.pnl_pct = pnl_pct
                position.pnl_usd = pnl_usd
                
                # Move to closed
                self._closed_positions[position_id] = position
                del self._open_positions[position_id]
                
                # MEMORY CLEANUP: Keep only last N closed positions
                self._cleanup_old_closed_positions()
                
                # Update balance
                self._session_balance += pnl_usd
                
                self._save_positions()
                
                # Notify adaptive sizing
                self._notify_adaptive_sizing(position.symbol, pnl_pct)
                
                logging.info(f"✅ Position closed: {position.symbol} PnL: {pnl_pct:+.2f}%")
                return True
                
        except Exception as e:
            logging.error(f"Position closure failed: {e}")
            return False
    
    # ========================================
    # BALANCE OPERATIONS
    # ========================================
    
    def update_balance(self, new_balance: float):
        """Update session balance"""
        try:
            with self._lock:
                old_balance = self._real_balance_cache
                self._real_balance_cache = new_balance
                self._session_balance = new_balance
                
                if self._session_start_balance == 1000.0:
                    self._session_start_balance = new_balance
                
                logging.debug(f"Balance: ${old_balance:.2f} → ${new_balance:.2f}")
        except Exception as e:
            logging.error(f"Balance update failed: {e}")
    
    def get_available_balance(self) -> float:
        """Get available balance for new positions"""
        try:
            with self._read_lock:
                used_margin = sum(pos.position_size / pos.leverage 
                                for pos in self._open_positions.values() 
                                if pos.status == "OPEN")
                return max(0, self._session_balance - used_margin)
        except Exception as e:
            logging.error(f"Available balance calc failed: {e}")
            return 0.0
    
    def reset_session(self):
        """Reset session - clear all positions and reset balance"""
        try:
            with self._lock:
                self._open_positions.clear()
                self._closed_positions.clear()
                self._session_balance = 1000.0
                self._session_start_balance = 1000.0
                self._real_balance_cache = 1000.0
                self._operation_count = 0
                self._lock_contention_count = 0
                
                self._save_positions()
                logging.info("🔄 Session reset complete")
        except Exception as e:
            logging.error(f"Session reset failed: {e}")
    
    # ========================================
    # INTERNAL HELPERS
    # ========================================
    
    def _load_positions(self):
        """Load positions from file"""
        try:
            open_pos, closed_pos, balance, start_balance = self.io.load_positions()
            
            with self._lock:
                self._open_positions = open_pos
                self._closed_positions = closed_pos
                self._session_balance = balance
                self._session_start_balance = start_balance
                
        except Exception as e:
            logging.error(f"Load positions failed: {e}")
    
    def _save_positions(self):
        """Save positions to file"""
        try:
            self.io.save_positions(
                self._open_positions,
                self._closed_positions,
                self._session_balance,
                self._session_start_balance,
                self._operation_count,
                self._lock_contention_count
            )
        except Exception as e:
            logging.error(f"Save positions failed: {e}")
    
    def _notify_adaptive_sizing(self, symbol: str, pnl_pct: float):
        """Notify adaptive sizing system"""
        try:
            from config import ADAPTIVE_SIZING_ENABLED
            if ADAPTIVE_SIZING_ENABLED:
                from core.adaptive_position_sizing import global_adaptive_sizing
                if global_adaptive_sizing:
                    global_adaptive_sizing.update_after_trade(
                        symbol=symbol,
                        pnl_pct=pnl_pct,
                        wallet_equity=self._session_balance
                    )
        except Exception as e:
            logging.debug(f"Adaptive sizing notification failed: {e}")
    
    def _cleanup_old_closed_positions(self):
        """Remove oldest closed positions if limit exceeded"""
        try:
            if len(self._closed_positions) <= self.MAX_CLOSED_POSITIONS:
                return
            
            # Sort by close_time (oldest first)
            sorted_positions = sorted(
                self._closed_positions.items(),
                key=lambda x: x[1].close_time or "0"
            )
            
            # Keep only last MAX_CLOSED_POSITIONS
            to_remove = len(self._closed_positions) - self.MAX_CLOSED_POSITIONS
            removed_count = 0
            
            for pos_id, _ in sorted_positions[:to_remove]:
                del self._closed_positions[pos_id]
                removed_count += 1
            
            if removed_count > 0:
                logging.info(f"🧹 Memory cleanup: Removed {removed_count} old closed positions (keeping last {self.MAX_CLOSED_POSITIONS})")
                
        except Exception as e:
            logging.error(f"Cleanup failed: {e}")
    
    # ========================================
    # DIRECT ACCESS (for internal use)
    # ========================================
    
    def _get_open_positions_unsafe(self) -> Dict[str, ThreadSafePosition]:
        """Direct access to open positions (use with lock!)"""
        return self._open_positions
    
    def _get_closed_positions_unsafe(self) -> Dict[str, ThreadSafePosition]:
        """Direct access to closed positions (use with lock!)"""
        return self._closed_positions
    
    def get_lock(self) -> threading.RLock:
        """Get lock for external atomic operations"""
        return self._lock
