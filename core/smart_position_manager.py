#!/usr/bin/env python3
"""
🚀 SMART POSITION MANAGER

ENHANCED VERSION: Intelligent Bybit sync + Dual tracking
- Track OPEN positions (real on Bybit)
- Track CLOSED positions (session history with P&L)
- Smart deduplication
- Real-time sync with Bybit positions
- Dual table display system

GARANTISCE: Accurate position tracking senza duplicati
"""

import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from termcolor import colored

@dataclass
class Position:
    """Enhanced position data structure"""
    position_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    entry_price: float
    position_size: float  # USD value
    leverage: int
    
    # Protection levels
    stop_loss: float
    take_profit: float
    trailing_trigger: float
    
    # Order IDs for cleanup
    sl_order_id: Optional[str] = None
    tp_order_id: Optional[str] = None
    
    # Runtime data
    current_price: float = 0.0
    unrealized_pnl_pct: float = 0.0
    unrealized_pnl_usd: float = 0.0
    max_favorable_pnl: float = 0.0
    trailing_active: bool = False
    
    # Enhanced metadata
    confidence: float = 0.7
    entry_time: str = ""
    close_time: Optional[str] = None
    status: str = "OPEN"  # OPEN, CLOSED_TP, CLOSED_SL, CLOSED_MANUAL
    close_reason: Optional[str] = None
    final_pnl_pct: Optional[float] = None
    final_pnl_usd: Optional[float] = None

class SmartPositionManager:
    """
    Intelligent position manager with Bybit sync and dual tracking
    
    FEATURES:
    - Smart deduplication 
    - Real-time Bybit sync
    - Separate OPEN/CLOSED tracking
    - Session P&L history
    """
    
    def __init__(self, storage_file: str = "smart_positions.json"):
        self.storage_file = storage_file
        self.open_positions: Dict[str, Position] = {}
        self.closed_positions: Dict[str, Position] = {}
        self.session_balance = 1000.0
        self.session_start_balance = 1000.0
        self.load_positions()
        
    def _create_position_from_bybit(self, symbol: str, bybit_data: Dict) -> Position:
        """Create Position object from Bybit data"""
        entry_price = bybit_data['entry_price']
        side = bybit_data['side']
        
        # Calculate protective levels (40% SL, 20% TP)
        if side == 'buy':
            sl_price = entry_price * 0.6  # 40% below
            tp_price = entry_price * 1.2  # 20% above
            trailing_trigger = entry_price * 1.01  # 1% above
        else:
            sl_price = entry_price * 1.4  # 40% above
            tp_price = entry_price * 0.8  # 20% below
            trailing_trigger = entry_price * 0.99  # 1% below
        
        position_id = f"{symbol.replace('/USDT:USDT', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        position_size = bybit_data['contracts'] * entry_price
        
        return Position(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            position_size=position_size,
            leverage=10,
            stop_loss=sl_price,
            take_profit=tp_price,
            trailing_trigger=trailing_trigger,
            current_price=entry_price,
            confidence=0.7,
            entry_time=datetime.now().isoformat(),
            unrealized_pnl_usd=bybit_data['unrealized_pnl']
        )
        
    async def sync_with_bybit(self, exchange) -> Tuple[List[Position], List[Position]]:
        """
        🚀 SMART SYNC: Sync tracked positions with real Bybit positions
        
        Args:
            exchange: Bybit exchange instance
            
        Returns:
            Tuple[List[Position], List[Position]]: (newly_opened, newly_closed)
        """
        newly_opened = []
        newly_closed = []
        
        try:
            logging.debug("🔄 SMART SYNC: Confronto posizioni tracked vs reali")
            
            # 1. Get real positions from Bybit
            bybit_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_bybit_positions = [p for p in bybit_positions if float(p.get('contracts', 0)) > 0]
            
            # 2. Create mapping of Bybit positions
            bybit_symbols = set()
            bybit_position_data = {}
            
            for pos in active_bybit_positions:
                symbol = pos.get('symbol')
                if symbol:
                    bybit_symbols.add(symbol)
                    bybit_position_data[symbol] = {
                        'contracts': abs(float(pos.get('contracts', 0))),
                        'side': 'buy' if float(pos.get('contracts', 0)) > 0 else 'sell',
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'unrealized_pnl': float(pos.get('unrealizedPnl', 0))
                    }
            
            # 3. Get currently tracked symbols
            tracked_symbols = set(pos.symbol for pos in self.open_positions.values())
            
            logging.debug(f"📊 Bybit: {len(bybit_symbols)}, Tracked: {len(tracked_symbols)}")
            
            # 4. Find newly opened positions (on Bybit but not tracked)  
            newly_opened_symbols = bybit_symbols - tracked_symbols
            
            for symbol in newly_opened_symbols:
                try:
                    # CRITICAL FIX: Check if position already exists for this symbol (deduplication)
                    if self.has_position_for_symbol(symbol):
                        logging.debug(f"🔄 SKIP: {symbol} already tracked (deduplication)")
                        continue
                    
                    bybit_data = bybit_position_data[symbol]
                    position = self._create_position_from_bybit(symbol, bybit_data)
                    self.open_positions[position.position_id] = position
                    newly_opened.append(position)
                    logging.info(colored(f"📥 NEW: {symbol} {bybit_data['side'].upper()}", "green"))
                except Exception as e:
                    logging.error(f"Error creating position for {symbol}: {e}")
            
            # 5. Find newly closed positions (tracked but not on Bybit)
            newly_closed_symbols = tracked_symbols - bybit_symbols
            
            for symbol in newly_closed_symbols:
                # Find tracked position for this symbol
                positions_to_close = [pos for pos in self.open_positions.values() if pos.symbol == symbol]
                
                for position in positions_to_close:
                    # Mark as closed and move to closed_positions
                    position.status = "CLOSED_MANUAL"
                    position.close_time = datetime.now().isoformat()
                    position.close_reason = "Position closed on Bybit"
                    position.final_pnl_pct = position.unrealized_pnl_pct
                    position.final_pnl_usd = position.unrealized_pnl_usd
                    
                    # Move to closed positions
                    self.closed_positions[position.position_id] = position
                    newly_closed.append(position)
                    
                    # Remove from open positions
                    del self.open_positions[position.position_id]
                    
                    # Update session balance
                    self.session_balance += position.final_pnl_usd
                    
                    logging.info(colored(f"🔒 CLOSED: {symbol} P&L: {position.final_pnl_pct:+.2f}%", "yellow"))
            
            # 6. Update existing positions with current data
            for symbol in (bybit_symbols & tracked_symbols):
                bybit_data = bybit_position_data[symbol]
                
                # Find tracked position and update
                for position in self.open_positions.values():
                    if position.symbol == symbol:
                        # Update current price from Bybit
                        current_price = bybit_data['entry_price']  # Bybit doesn't give current price directly
                        unrealized_pnl = bybit_data['unrealized_pnl']
                        
                        position.current_price = current_price
                        position.unrealized_pnl_usd = unrealized_pnl
                        
                        # Calculate PnL percentage
                        if position.position_size > 0:
                            position.unrealized_pnl_pct = (unrealized_pnl / position.position_size) * 100
                        
                        break
            
            self.save_positions()
            
            if newly_opened or newly_closed:
                logging.info(f"🔄 Sync result: +{len(newly_opened)} opened, +{len(newly_closed)} closed")
            
            return newly_opened, newly_closed
            
        except Exception as e:
            logging.error(f"Error in Bybit sync: {e}")
            return [], []
    
    def create_position(self, symbol: str, side: str, entry_price: float, 
                       position_size: float, stop_loss: float, take_profit: float,
                       leverage: int = 10, confidence: float = 0.7) -> str:
        """Create new position in tracker"""
        try:
            position_id = f"{symbol.replace('/USDT:USDT', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            trailing_trigger = entry_price * (1.01 if side.lower() == 'buy' else 0.99)
            
            position = Position(
                position_id=position_id,
                symbol=symbol,
                side=side.lower(),
                entry_price=entry_price,
                position_size=position_size,
                leverage=leverage,
                stop_loss=stop_loss,
                take_profit=take_profit,
                trailing_trigger=trailing_trigger,
                current_price=entry_price,
                confidence=confidence,
                entry_time=datetime.now().isoformat()
            )
            
            self.open_positions[position_id] = position
            self.save_positions()
            
            logging.debug(f"📊 Position created: {position_id}")
            return position_id
            
        except Exception as e:
            logging.error(f"Error creating position: {e}")
            return ""
    
    def close_position_manual(self, position_id: str, exit_price: float, reason: str = "MANUAL") -> bool:
        """Manually close a position"""
        try:
            if position_id not in self.open_positions:
                return False
            
            position = self.open_positions[position_id]
            
            # Calculate final PnL
            if position.side == 'buy':
                pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100
            else:
                pnl_pct = ((position.entry_price - exit_price) / position.entry_price) * 100
            
            pnl_usd = (pnl_pct / 100) * position.position_size
            
            # Update position as closed
            position.status = f"CLOSED_{reason}"
            position.close_time = datetime.now().isoformat()
            position.close_reason = reason
            position.final_pnl_pct = pnl_pct
            position.final_pnl_usd = pnl_usd
            position.current_price = exit_price
            
            # Move to closed positions
            self.closed_positions[position_id] = position
            del self.open_positions[position_id]
            
            # Update session balance
            self.session_balance += pnl_usd
            
            logging.info(f"🔒 Position closed: {position.symbol} {reason} PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})")
            self.save_positions()
            
            return True
            
        except Exception as e:
            logging.error(f"Error closing position: {e}")
            return False
    
    # Standard interface methods for compatibility
    def get_active_positions(self) -> List[Position]:
        """Get only OPEN positions"""
        return [pos for pos in self.open_positions.values() if pos.status == "OPEN"]
    
    def get_closed_positions(self) -> List[Position]:
        """Get positions closed during this session"""
        return list(self.closed_positions.values())
    
    def get_position_count(self) -> int:
        """Get number of OPEN positions only"""
        return len([pos for pos in self.open_positions.values() if pos.status == "OPEN"])
    
    def has_position_for_symbol(self, symbol: str) -> bool:
        """Check if OPEN position exists for symbol"""
        return any(pos.symbol == symbol and pos.status == "OPEN" for pos in self.open_positions.values())
    
    def get_session_pnl(self) -> Tuple[float, float]:
        """
        Get total session P&L (realized + unrealized)
        
        Returns:
            Tuple[float, float]: (total_pnl_pct, total_pnl_usd)
        """
        # Realized P&L from closed positions
        realized_pnl = sum(pos.final_pnl_usd for pos in self.closed_positions.values() if pos.final_pnl_usd)
        
        # Unrealized P&L from open positions  
        unrealized_pnl = sum(pos.unrealized_pnl_usd for pos in self.open_positions.values())
        
        total_pnl_usd = realized_pnl + unrealized_pnl
        
        # Calculate percentage based on initial session balance
        total_pnl_pct = (total_pnl_usd / self.session_start_balance) * 100
        
        return total_pnl_pct, total_pnl_usd
    
    def get_used_margin(self) -> float:
        """Get total margin currently in use"""
        return sum(pos.position_size / pos.leverage for pos in self.open_positions.values())
    
    def get_available_balance(self) -> float:
        """Get available balance for new positions"""
        used_margin = self.get_used_margin()
        return max(0, self.session_balance - used_margin)
    
    def update_position_orders(self, position_id: str, sl_order_id: Optional[str], 
                              tp_order_id: Optional[str]) -> bool:
        """Update position with placed order IDs"""
        try:
            if position_id in self.open_positions:
                self.open_positions[position_id].sl_order_id = sl_order_id
                self.open_positions[position_id].tp_order_id = tp_order_id
                self.save_positions()
                logging.debug(f"📊 Position {position_id} updated with orders")
                return True
            else:
                logging.error(f"Position {position_id} not found for order update")
                return False
        except Exception as e:
            logging.error(f"Error updating position orders: {e}")
            return False
    
    def get_session_summary(self) -> Dict:
        """Get comprehensive session summary"""
        pnl_pct, pnl_usd = self.get_session_pnl()
        
        return {
            'balance': self.session_balance,
            'active_positions': len(self.get_active_positions()),
            'closed_positions': len(self.closed_positions),
            'total_pnl_usd': pnl_usd,
            'total_pnl_pct': pnl_pct,
            'realized_pnl': sum(pos.final_pnl_usd for pos in self.closed_positions.values() if pos.final_pnl_usd),
            'unrealized_pnl': sum(pos.unrealized_pnl_usd for pos in self.open_positions.values())
        }
    
    def load_positions(self):
        """Load positions from storage"""
        try:
            with open(self.storage_file, 'r') as f:
                data = json.load(f)
                
                # Load open positions
                for pos_id, pos_data in data.get('open_positions', {}).items():
                    position = Position(**pos_data)
                    self.open_positions[pos_id] = position
                
                # Load closed positions
                for pos_id, pos_data in data.get('closed_positions', {}).items():
                    position = Position(**pos_data)
                    self.closed_positions[pos_id] = position
                
                self.session_balance = data.get('session_balance', 1000.0)
                self.session_start_balance = data.get('session_start_balance', 1000.0)
                
            total_positions = len(self.open_positions) + len(self.closed_positions)
            logging.debug(f"📁 Positions loaded: {len(self.open_positions)} open, {len(self.closed_positions)} closed")
            
        except FileNotFoundError:
            logging.debug("📂 No position file found, starting fresh session")
        except Exception as e:
            logging.error(f"Error loading positions: {e}")
    
    def save_positions(self):
        """Save positions to storage"""
        try:
            # Convert Position objects to dict for JSON
            open_positions_dict = {}
            for pos_id, position in self.open_positions.items():
                open_positions_dict[pos_id] = asdict(position)
            
            closed_positions_dict = {}
            for pos_id, position in self.closed_positions.items():
                closed_positions_dict[pos_id] = asdict(position)
            
            data = {
                'open_positions': open_positions_dict,
                'closed_positions': closed_positions_dict,
                'session_balance': self.session_balance,
                'session_start_balance': self.session_start_balance,
                'last_save': datetime.now().isoformat()
            }
            
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logging.debug(f"💾 Positions saved: {len(self.open_positions)} open, {len(self.closed_positions)} closed")
            
        except Exception as e:
            logging.error(f"Error saving positions: {e}")
    
    def cleanup_old_closed_positions(self, max_closed: int = 50):
        """Keep only recent closed positions to prevent file bloat"""
        try:
            if len(self.closed_positions) > max_closed:
                # Sort by close_time and keep only recent ones
                sorted_closed = sorted(
                    self.closed_positions.values(),
                    key=lambda pos: pos.close_time or "1970-01-01",
                    reverse=True
                )
                
                # Keep only the most recent
                recent_closed = sorted_closed[:max_closed]
                
                # Update closed_positions dict
                self.closed_positions = {pos.position_id: pos for pos in recent_closed}
                
                removed_count = len(sorted_closed) - len(recent_closed)
                logging.info(f"🧹 Cleanup: Removed {removed_count} old closed positions")
                
                self.save_positions()
                
        except Exception as e:
            logging.error(f"Error cleaning up old positions: {e}")
    
    def reset_session(self):
        """
        🧹 FRESH START: Reset all position tracking for new session
        
        Clears all tracked positions (open and closed) and resets balance.
        Should be called at bot startup to avoid ghost positions.
        """
        try:
            old_open = len(self.open_positions)
            old_closed = len(self.closed_positions)
            
            # Clear all positions
            self.open_positions.clear()
            self.closed_positions.clear()
            
            # Reset session balance to starting amount
            self.session_balance = 1000.0
            self.session_start_balance = 1000.0
            
            # Save clean state to disk
            self.save_positions()
            
            logging.info(f"🧹 SMART POSITION RESET: Cleared {old_open} open + {old_closed} closed positions - fresh session started")
            
        except Exception as e:
            logging.error(f"Error resetting smart session: {e}")

# Global smart position manager instance  
global_smart_position_manager = SmartPositionManager()
