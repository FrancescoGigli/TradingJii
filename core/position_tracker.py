#!/usr/bin/env python3
"""
Advanced Position Tracking System with Trailing Stop Loss

FEATURES:
- Real-time position monitoring
- Trailing stop loss implementation
- Risk-adjusted TP/SL based on leverage
- Persistent storage in JSON
- Progressive wallet tracking
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from termcolor import colored

class PositionTracker:
    """
    Advanced position tracking with trailing stop loss
    """
    
    def __init__(self, storage_file="active_positions.json"):
        self.storage_file = storage_file
        self.active_positions = {}
        self.session_stats = {
            'initial_balance': 1000.0,
            'current_balance': 1000.0,
            'total_trades': 0,
            'winning_trades': 0,
            'total_pnl': 0.0,
            'session_start': datetime.now().isoformat(),
            'last_update': datetime.now().isoformat()
        }
        self.load_session()
        
    def load_session(self):
        """Load active positions and session from file"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.active_positions = data.get('positions', {})
                    self.session_stats = data.get('session_stats', self.session_stats)
            else:
                logging.info("📂 No existing session found, starting fresh")
        except Exception as e:
            logging.error(f"Error loading session: {e}")
            
    def save_session(self):
        """Save current session to file"""
        try:
            data = {
                'positions': self.active_positions,
                'session_stats': self.session_stats,
                'last_save': datetime.now().isoformat()
            }
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving session: {e}")
            
    def calculate_tp_sl(self, entry_price: float, side: str, leverage: int, atr: float = None) -> Dict:
        """
        Calculate TP/SL using Option C - Risk-Adjusted Logic
        
        Args:
            entry_price: Entry price of position
            side: 'Buy' or 'Sell' 
            leverage: Trading leverage
            atr: Average True Range (optional)
            
        Returns:
            Dict with 'take_profit', 'stop_loss', 'trailing_trigger' prices
        """
        BASE_RISK_PCT = 3.0  # 3% base risk
        
        # Calculate risk-adjusted percentages
        sl_pct = BASE_RISK_PCT / leverage  # 0.3% for 10x leverage
        tp_pct = sl_pct * 2               # 0.6% for 10x leverage (1:2 R:R)
        trailing_trigger_pct = 1.0        # Start trailing at +1%
        
        if side.upper() == 'BUY' or side.upper() == 'LONG':
            stop_loss = entry_price * (1 - sl_pct / 100)
            take_profit = entry_price * (1 + tp_pct / 100)
            trailing_trigger = entry_price * (1 + trailing_trigger_pct / 100)
        else:  # SELL or SHORT
            stop_loss = entry_price * (1 + sl_pct / 100)
            take_profit = entry_price * (1 - tp_pct / 100)
            trailing_trigger = entry_price * (1 - trailing_trigger_pct / 100)
            
        return {
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'trailing_trigger': trailing_trigger,
            'sl_pct': sl_pct,
            'tp_pct': tp_pct
        }
    
    def open_position(self, symbol: str, side: str, entry_price: float, 
                     position_size: float, leverage: int, confidence: float,
                     atr: float = None) -> str:
        """
        Open new position with TP/SL/Trailing logic
        
        Returns: position_id
        """
        position_id = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Calculate TP/SL levels
        levels = self.calculate_tp_sl(entry_price, side, leverage, atr)
        
        position = {
            'position_id': position_id,
            'symbol': symbol,
            'side': side.upper(),
            'entry_price': entry_price,
            'entry_time': datetime.now().isoformat(),
            'position_size': position_size,
            'leverage': leverage,
            'confidence': confidence,
            'atr': atr,
            
            # TP/SL Levels
            'take_profit': levels['take_profit'],
            'stop_loss': levels['stop_loss'],
            'trailing_trigger': levels['trailing_trigger'],
            'initial_stop_loss': levels['stop_loss'],
            'trailing_active': False,
            
            # Performance tracking
            'current_price': entry_price,
            'unrealized_pnl_pct': 0.0,
            'unrealized_pnl_usd': 0.0,
            'max_favorable_pnl': 0.0,
            'status': 'OPEN'
        }
        
        self.active_positions[position_id] = position
        self.session_stats['total_trades'] += 1
        self.session_stats['last_update'] = datetime.now().isoformat()
        
        self.save_session()
        
        logging.info(colored(f"✅ Position opened: {symbol} {side} @ {entry_price:.6f}", "green"))
        logging.info(colored(f"🎯 TP: {levels['take_profit']:.6f} | SL: {levels['stop_loss']:.6f} | Trailing: {levels['trailing_trigger']:.6f}", "cyan"))
        
        return position_id
    
    def update_positions(self, current_prices: Dict[str, float]) -> List[Dict]:
        """
        Update all positions with current prices and check exit conditions
        
        Returns: List of positions that should be closed
        """
        positions_to_close = []
        
        for pos_id, position in list(self.active_positions.items()):
            symbol = position['symbol']
            if symbol not in current_prices:
                continue
                
            current_price = current_prices[symbol]
            side = position['side']
            entry_price = position['entry_price']
            
            # Calculate unrealized PnL
            if side == 'BUY':
                pnl_pct = (current_price - entry_price) / entry_price * 100
            else:  # SELL
                pnl_pct = (entry_price - current_price) / entry_price * 100
                
            position['current_price'] = current_price
            position['unrealized_pnl_pct'] = pnl_pct
            position['unrealized_pnl_usd'] = (pnl_pct / 100) * position['position_size']
            
            # Track max favorable move for trailing
            if pnl_pct > position['max_favorable_pnl']:
                position['max_favorable_pnl'] = pnl_pct
                
            # Check trailing stop activation
            if not position['trailing_active']:
                if side == 'BUY' and current_price >= position['trailing_trigger']:
                    position['trailing_active'] = True
                    logging.info(colored(f"🎪 Trailing activated for {symbol} at {current_price:.6f}", "yellow"))
                elif side == 'SELL' and current_price <= position['trailing_trigger']:
                    position['trailing_active'] = True
                    logging.info(colored(f"🎪 Trailing activated for {symbol} at {current_price:.6f}", "yellow"))
            
            # FIXED: Update trailing stop using ATR for volatility adaptation
            if position['trailing_active']:
                # Use ATR-based trailing instead of fixed percentage
                atr_value = position.get('atr', current_price * 0.02)  # Fallback to 2%
                
                # Calculate dynamic trailing distance
                if atr_value > 0:
                    # ATR-based trailing distance (more adaptive to volatility)
                    trailing_distance = atr_value * 1.5  # 1.5x ATR for trailing
                else:
                    # Fallback to fixed percentage if no ATR
                    sl_pct = 3.0 / position['leverage']
                    trailing_distance = current_price * (sl_pct / 100)
                
                if side == 'BUY':
                    new_trailing_sl = current_price - trailing_distance
                    # Never lower trailing SL
                    position['stop_loss'] = max(position['stop_loss'], new_trailing_sl)
                else:  # SELL
                    new_trailing_sl = current_price + trailing_distance
                    # Never higher trailing SL for shorts
                    position['stop_loss'] = min(position['stop_loss'], new_trailing_sl)
                
                # Log ATR-based update
                logging.debug(f"🎪 ATR trailing update for {position['symbol']}: SL: {position['stop_loss']:.6f} (ATR: {atr_value:.6f})")
            
            # Check exit conditions
            exit_reason = None
            
            if side == 'BUY':
                if current_price >= position['take_profit']:
                    exit_reason = "Take Profit"
                elif current_price <= position['stop_loss']:
                    exit_reason = "Trailing Stop" if position['trailing_active'] else "Stop Loss"
            else:  # SELL
                if current_price <= position['take_profit']:
                    exit_reason = "Take Profit"
                elif current_price >= position['stop_loss']:
                    exit_reason = "Trailing Stop" if position['trailing_active'] else "Stop Loss"
            
            if exit_reason:
                position['exit_reason'] = exit_reason
                position['exit_price'] = current_price
                position['exit_time'] = datetime.now().isoformat()
                position['status'] = 'CLOSED'
                positions_to_close.append(position)
        
        self.save_session()
        return positions_to_close
    
    def close_position(self, position_id: str, exit_price: float, exit_reason: str = "Manual"):
        """Close specific position and update wallet"""
        if position_id not in self.active_positions:
            return False
            
        position = self.active_positions[position_id]
        
        # Calculate final PnL
        side = position['side']
        entry_price = position['entry_price']
        
        if side == 'BUY':
            pnl_pct = (exit_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - exit_price) / entry_price * 100
            
        pnl_usd = (pnl_pct / 100) * position['position_size']
        
        # Update session stats
        self.session_stats['current_balance'] += pnl_usd
        self.session_stats['total_pnl'] += pnl_usd
        
        if pnl_pct > 0:
            self.session_stats['winning_trades'] += 1
            
        # Mark position as closed
        position.update({
            'exit_price': exit_price,
            'exit_time': datetime.now().isoformat(),
            'exit_reason': exit_reason,
            'final_pnl_pct': pnl_pct,
            'final_pnl_usd': pnl_usd,
            'status': 'CLOSED'
        })
        
        # Remove from active positions
        del self.active_positions[position_id]
        
        logging.info(colored(f"🔒 Position closed: {position['symbol']} {exit_reason} PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})", "yellow"))
        
        self.save_session()
        return True
    
    def get_active_positions_count(self) -> int:
        """Get number of active positions"""
        return len(self.active_positions)
    
    def get_available_balance(self) -> float:
        """Get available balance for new trades"""
        invested = sum(pos['position_size'] for pos in self.active_positions.values())
        return self.session_stats['current_balance'] - invested
    
    def get_total_unrealized_pnl(self) -> Tuple[float, float]:
        """Get total unrealized PnL (percentage, USD)"""
        total_pnl_usd = sum(pos['unrealized_pnl_usd'] for pos in self.active_positions.values())
        total_invested = sum(pos['position_size'] for pos in self.active_positions.values())
        
        total_pnl_pct = (total_pnl_usd / total_invested) * 100 if total_invested > 0 else 0
        return total_pnl_pct, total_pnl_usd
    
    def get_session_summary(self) -> Dict:
        """Get complete session summary for display"""
        win_rate = (self.session_stats['winning_trades'] / self.session_stats['total_trades'] * 100) if self.session_stats['total_trades'] > 0 else 0
        
        total_invested = sum(pos['position_size'] for pos in self.active_positions.values())
        unrealized_pnl_pct, unrealized_pnl_usd = self.get_total_unrealized_pnl()
        
        return {
            'wallet_balance': self.session_stats['current_balance'],
            'initial_balance': self.session_stats['initial_balance'],
            'available_balance': self.get_available_balance(),
            'active_positions': len(self.active_positions),
            'total_invested': total_invested,
            'total_trades': self.session_stats['total_trades'],
            'winning_trades': self.session_stats['winning_trades'],
            'win_rate': win_rate,
            'total_realized_pnl': self.session_stats['total_pnl'],
            'unrealized_pnl_usd': unrealized_pnl_usd,
            'unrealized_pnl_pct': unrealized_pnl_pct,
            'session_start': self.session_stats['session_start']
        }


# Global position tracker instance
global_position_tracker = PositionTracker()
