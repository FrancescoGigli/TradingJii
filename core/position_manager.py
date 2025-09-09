#!/usr/bin/env python3
"""
📊 CLEAN POSITION MANAGER

SINGLE RESPONSIBILITY: Position tracking & management
- Track active positions
- Calculate real-time PnL  
- Handle position lifecycle
- Sync with Bybit positions
- Zero order execution, solo tracking

GARANTISCE: Position state sempre aggiornato e accurato
"""

import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class Position:
    """Clean position data structure"""
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
    
    # Metadata
    confidence: float = 0.7
    entry_time: str = ""
    status: str = "OPEN"

class PositionManager:
    """
    Clean position tracking and management
    
    PHILOSOPHY: Simple state management, clear APIs
    """
    
    def __init__(self, storage_file: str = "positions_clean.json"):
        self.storage_file = storage_file
        self.positions: Dict[str, Position] = {}
        self.session_balance = 1000.0
        self.load_positions()
        
    def create_position(self, symbol: str, side: str, entry_price: float, 
                       position_size: float, stop_loss: float, take_profit: float,
                       leverage: int = 10, confidence: float = 0.7) -> str:
        """
        Create new position in tracker
        
        Returns:
            str: Position ID
        """
        try:
            position_id = f"{symbol.replace('/USDT:USDT', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Calculate trailing trigger (+/-1%)
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
            
            self.positions[position_id] = position
            self.save_positions()
            
            logging.debug(f"📊 Position created: {position_id}")
            return position_id
            
        except Exception as e:
            logging.error(f"Error creating position: {e}")
            return ""
    
    def update_position_orders(self, position_id: str, sl_order_id: Optional[str], 
                              tp_order_id: Optional[str]) -> bool:
        """
        Update position with placed order IDs
        
        Args:
            position_id: Position ID
            sl_order_id: Stop loss order ID  
            tp_order_id: Take profit order ID
            
        Returns:
            bool: Success
        """
        try:
            if position_id in self.positions:
                self.positions[position_id].sl_order_id = sl_order_id
                self.positions[position_id].tp_order_id = tp_order_id
                self.save_positions()
                
                logging.debug(f"📊 Position {position_id} updated with orders: SL={sl_order_id}, TP={tp_order_id}")
                return True
            else:
                logging.error(f"Position {position_id} not found for order update")
                return False
                
        except Exception as e:
            logging.error(f"Error updating position orders: {e}")
            return False
    
    def update_prices(self, current_prices: Dict[str, float]) -> List[Position]:
        """
        Update all positions with current prices
        
        Args:
            current_prices: Dict of symbol -> current price
            
        Returns:
            List[Position]: Positions that should be closed (hit TP/SL)
        """
        positions_to_close = []
        
        for position in self.positions.values():
            if position.symbol not in current_prices:
                continue
                
            current_price = current_prices[position.symbol]
            position.current_price = current_price
            
            # Calculate PnL
            if position.side == 'buy':
                pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            else:
                pnl_pct = ((position.entry_price - current_price) / position.entry_price) * 100
            
            position.unrealized_pnl_pct = pnl_pct
            position.unrealized_pnl_usd = (pnl_pct / 100) * position.position_size
            
            # Track max favorable move
            if pnl_pct > position.max_favorable_pnl:
                position.max_favorable_pnl = pnl_pct
            
            # Check trailing activation
            if not position.trailing_active:
                if position.side == 'buy' and current_price >= position.trailing_trigger:
                    position.trailing_active = True
                    logging.info(f"🎪 Trailing activated for {position.symbol}")
                elif position.side == 'sell' and current_price <= position.trailing_trigger:
                    position.trailing_active = True
                    logging.info(f"🎪 Trailing activated for {position.symbol}")
            
            # Update trailing stop
            if position.trailing_active:
                atr_estimate = current_price * 0.02  # 2% ATR estimate
                trailing_distance = atr_estimate * 1.5
                
                if position.side == 'buy':
                    new_sl = current_price - trailing_distance
                    position.stop_loss = max(position.stop_loss, new_sl)  # Never lower
                else:
                    new_sl = current_price + trailing_distance  
                    position.stop_loss = min(position.stop_loss, new_sl)  # Never higher
            
            # Check exit conditions
            if position.side == 'buy':
                if current_price >= position.take_profit:
                    position.status = 'CLOSED_TP'
                    positions_to_close.append(position)
                elif current_price <= position.stop_loss:
                    position.status = 'CLOSED_SL'
                    positions_to_close.append(position)
            else:  # sell
                if current_price <= position.take_profit:
                    position.status = 'CLOSED_TP'
                    positions_to_close.append(position)
                elif current_price >= position.stop_loss:
                    position.status = 'CLOSED_SL'
                    positions_to_close.append(position)
        
        self.save_positions()
        return positions_to_close
    
    def close_position(self, position_id: str, exit_price: float, reason: str) -> bool:
        """
        Close position and update session balance
        
        Args:
            position_id: Position to close
            exit_price: Exit price
            reason: Close reason (TP/SL/Manual)
            
        Returns:
            bool: Success
        """
        try:
            if position_id not in self.positions:
                return False
            
            position = self.positions[position_id]
            
            # Calculate final PnL
            if position.side == 'buy':
                pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100
            else:
                pnl_pct = ((position.entry_price - exit_price) / position.entry_price) * 100
            
            pnl_usd = (pnl_pct / 100) * position.position_size
            
            # Update session balance
            self.session_balance += pnl_usd
            
            logging.info(f"🔒 Position closed: {position.symbol} {reason} PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})")
            
            # Remove from active positions
            del self.positions[position_id]
            self.save_positions()
            
            return True
            
        except Exception as e:
            logging.error(f"Error closing position: {e}")
            return False
    
    def get_active_positions(self) -> List[Position]:
        """Get all active positions"""
        return list(self.positions.values())
    
    def get_position_count(self) -> int:
        """Get number of active positions"""
        return len(self.positions)
    
    def get_used_margin(self) -> float:
        """Get total margin currently in use"""
        return sum(pos.position_size / pos.leverage for pos in self.positions.values())
    
    def get_available_balance(self) -> float:
        """Get available balance for new positions"""
        used_margin = self.get_used_margin()
        return max(0, self.session_balance - used_margin)
    
    def get_total_pnl(self) -> Tuple[float, float]:
        """
        Get total unrealized PnL
        
        Returns:
            Tuple[float, float]: (pnl_pct, pnl_usd)
        """
        total_pnl_usd = sum(pos.unrealized_pnl_usd for pos in self.positions.values())
        total_invested = sum(pos.position_size for pos in self.positions.values())
        
        total_pnl_pct = (total_pnl_usd / total_invested) * 100 if total_invested > 0 else 0
        return total_pnl_pct, total_pnl_usd
    
    def has_position_for_symbol(self, symbol: str) -> bool:
        """Check if position already exists for symbol"""
        return any(pos.symbol == symbol for pos in self.positions.values())
    
    def get_session_summary(self) -> Dict:
        """Get clean session summary"""
        pnl_pct, pnl_usd = self.get_total_pnl()
        
        return {
            'balance': self.session_balance,
            'active_positions': len(self.positions),
            'used_margin': self.get_used_margin(),
            'available_balance': self.get_available_balance(),
            'total_pnl_usd': pnl_usd,
            'total_pnl_pct': pnl_pct,
            'positions': self.get_active_positions()
        }
    
    def load_positions(self):
        """Load positions from storage"""
        try:
            with open(self.storage_file, 'r') as f:
                data = json.load(f)
                
                # Convert dict back to Position objects
                for pos_id, pos_data in data.get('positions', {}).items():
                    position = Position(**pos_data)
                    self.positions[pos_id] = position
                
                self.session_balance = data.get('session_balance', 1000.0)
                
            logging.debug(f"📁 Positions loaded: {len(self.positions)} active")
            
        except FileNotFoundError:
            logging.debug("📂 No position file found, starting fresh")
        except Exception as e:
            logging.error(f"Error loading positions: {e}")
    
    def save_positions(self):
        """Save positions to storage"""
        try:
            # Convert Position objects to dict for JSON
            positions_dict = {}
            for pos_id, position in self.positions.items():
                positions_dict[pos_id] = {
                    'position_id': position.position_id,
                    'symbol': position.symbol,
                    'side': position.side,
                    'entry_price': position.entry_price,
                    'position_size': position.position_size,
                    'leverage': position.leverage,
                    'stop_loss': position.stop_loss,
                    'take_profit': position.take_profit,
                    'trailing_trigger': position.trailing_trigger,
                    'sl_order_id': position.sl_order_id,
                    'tp_order_id': position.tp_order_id,
                    'current_price': position.current_price,
                    'unrealized_pnl_pct': position.unrealized_pnl_pct,
                    'unrealized_pnl_usd': position.unrealized_pnl_usd,
                    'max_favorable_pnl': position.max_favorable_pnl,
                    'trailing_active': position.trailing_active,
                    'confidence': position.confidence,
                    'entry_time': position.entry_time,
                    'status': position.status
                }
            
            data = {
                'positions': positions_dict,
                'session_balance': self.session_balance,
                'last_save': datetime.now().isoformat()
            }
            
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logging.debug(f"💾 Positions saved: {len(self.positions)} active")
            
        except Exception as e:
            logging.error(f"Error saving positions: {e}")

# Global position manager instance  
global_position_manager = PositionManager()
