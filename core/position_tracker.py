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
import time
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
        """Load active positions and session from file with robust JSON handling"""
        try:
            if os.path.exists(self.storage_file):
                # Check file size first
                file_size = os.path.getsize(self.storage_file)
                if file_size == 0:
                    logging.warning(f"📂 Session file {self.storage_file} is empty, starting fresh")
                    return
                
                # MEMORY PROTECTION: Check file size limit (max 10MB)
                MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
                if file_size > MAX_FILE_SIZE:
                    logging.error(f"📂 Session file {self.storage_file} too large ({file_size/1024/1024:.1f}MB > 10MB)")
                    backup_name = f"{self.storage_file}.oversized.{int(time.time())}"
                    try:
                        os.rename(self.storage_file, backup_name)
                        logging.warning(f"🗄️ Oversized file backed up as: {backup_name}")
                        logging.info("🔄 Starting fresh session due to oversized file")
                        return
                    except Exception as backup_error:
                        logging.error(f"Failed to backup oversized file: {backup_error}")
                        return
                
                # Try to read and parse JSON with error recovery
                try:
                    with open(self.storage_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        
                        if not content:
                            logging.warning(f"📂 Session file {self.storage_file} is empty, starting fresh")
                            return
                        
                        # Try to parse JSON
                        data = json.loads(content)
                        
                        # Validate JSON structure
                        if not isinstance(data, dict):
                            raise ValueError("Invalid JSON structure: not a dictionary")
                        
                        # Load data with validation
                        self.active_positions = data.get('positions', {})
                        loaded_session_stats = data.get('session_stats', {})
                        
                        # Validate and merge session stats
                        if isinstance(loaded_session_stats, dict):
                            # Preserve current session structure, update with loaded values
                            for key, value in loaded_session_stats.items():
                                if key in self.session_stats:
                                    self.session_stats[key] = value
                        
                        logging.debug(f"📂 Session loaded: {len(self.active_positions)} active positions, balance: {self.session_stats['current_balance']:.2f}")
                        
                except json.JSONDecodeError as json_error:
                    logging.error(f"❌ JSON parsing error in {self.storage_file}: {json_error}")
                    logging.warning(f"🔄 Backing up corrupted file and starting fresh session")
                    
                    # Backup corrupted file
                    backup_name = f"{self.storage_file}.corrupted.{int(time.time())}"
                    try:
                        os.rename(self.storage_file, backup_name)
                        logging.info(f"💾 Corrupted file backed up as: {backup_name}")
                    except Exception as backup_error:
                        logging.warning(f"Failed to backup corrupted file: {backup_error}")
                        
                except Exception as read_error:
                    logging.error(f"❌ File reading error: {read_error}")
                    logging.warning("🔄 Starting fresh session due to file read error")
                    
            else:
                logging.info("📂 No existing session found, starting fresh")
                
        except Exception as e:
            logging.error(f"❌ Critical error loading session: {e}")
            logging.warning("🔄 Starting fresh session due to critical error")
            # Reset to default values
            self.active_positions = {}
            
    def save_session(self):
        """Save current session to file with robust error handling"""
        try:
            # Prepare data with validation
            data = {
                'positions': self.active_positions or {},
                'session_stats': self.session_stats or {},
                'last_save': datetime.now().isoformat(),
                'format_version': '2.0'  # For future compatibility
            }
            
            # Validate data before saving
            if not isinstance(data['positions'], dict):
                logging.error("Invalid positions data, resetting to empty dict")
                data['positions'] = {}
            
            if not isinstance(data['session_stats'], dict):
                logging.error("Invalid session_stats data, resetting to defaults")
                data['session_stats'] = self.session_stats
            
            # CRITICAL FIX: Convert numpy arrays to lists for JSON serialization
            data = self._convert_numpy_to_serializable(data)
            
            # Try to serialize to JSON first (validation)
            try:
                json_string = json.dumps(data, indent=2, ensure_ascii=False)
            except (TypeError, ValueError) as json_error:
                logging.error(f"❌ JSON serialization failed: {json_error}")
                logging.error(f"❌ Problematic data keys: {list(data.keys())}")
                # Create minimal safe data structure
                data = {
                    'positions': {},
                    'session_stats': {
                        'initial_balance': 1000.0,
                        'current_balance': 1000.0,
                        'total_trades': 0,
                        'winning_trades': 0,
                        'total_pnl': 0.0,
                        'session_start': datetime.now().isoformat(),
                        'last_update': datetime.now().isoformat()
                    },
                    'last_save': datetime.now().isoformat(),
                    'format_version': '2.0'
                }
                json_string = json.dumps(data, indent=2, ensure_ascii=False)
            
            # Atomic write: write to temporary file first, then rename
            temp_file = f"{self.storage_file}.tmp"
            backup_file = f"{self.storage_file}.bak"  # CRITICAL FIX: Initialize backup_file here
            
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(json_string)
                    f.flush()  # Ensure data is written to disk
                    os.fsync(f.fileno())  # Force OS to write to disk
                
                # Atomic move (replace original file)
                if os.path.exists(self.storage_file):
                    os.replace(self.storage_file, backup_file)
                os.replace(temp_file, self.storage_file)
                
                # Clean up backup if save was successful
                if os.path.exists(backup_file):
                    try:
                        os.remove(backup_file)
                    except:
                        pass  # Backup cleanup is not critical
                
                logging.debug(f"💾 Session saved successfully: {len(self.active_positions)} positions")
                
            except Exception as write_error:
                logging.error(f"❌ Failed to write session file: {write_error}")
                # Try to clean up temp file
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
                    
        except Exception as e:
            logging.error(f"❌ Critical error saving session: {e}")
    def _convert_numpy_to_serializable(self, obj):
        """
        CRITICAL FIX: Recursively convert numpy arrays to lists for JSON serialization
        
        Args:
            obj: Object to convert (dict, list, numpy array, or primitive)
            
        Returns:
            JSON-serializable object
        """
        import numpy as np
        
        if isinstance(obj, dict):
            return {key: self._convert_numpy_to_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_to_serializable(item) for item in obj]
        elif isinstance(obj, np.ndarray):
            # Convert numpy array to list
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.floating)):
            # Convert numpy scalars to native Python types
            return obj.item()
        else:
            # Return as-is for primitive types (int, float, str, bool, None)
            return obj
            
    def calculate_tp_sl(self, entry_price: float, side: str, leverage: int, atr: float = None) -> Dict:
        """
        CLEAN: Simple TP/SL calculation
        
        Args:
            entry_price: Entry price of position
            side: 'Buy' or 'Sell' 
            leverage: Trading leverage
            atr: Average True Range (optional)
            
        Returns:
            Dict with 'take_profit', 'stop_loss', 'trailing_trigger' prices
        """
        try:
            # Simple leverage-based calculation
            BASE_RISK_PCT = 3.0
            sl_pct = BASE_RISK_PCT / leverage
            tp_pct = sl_pct * 2
            trailing_trigger_pct = 1.0
            
            if side.upper() == 'BUY' or side.upper() == 'LONG':
                stop_loss = entry_price * (1 - sl_pct / 100)
                take_profit = entry_price * (1 + tp_pct / 100)
                trailing_trigger = entry_price * (1 + trailing_trigger_pct / 100)
            else:  # SELL
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
            
        except Exception as e:
            logging.error(f"Error calculating TP/SL levels: {e}")
            # Safe fallback
            return {
                'take_profit': entry_price * (1.05 if side.upper() in ['BUY', 'LONG'] else 0.95),
                'stop_loss': entry_price * (0.95 if side.upper() in ['BUY', 'LONG'] else 1.05),
                'trailing_trigger': entry_price * (1.01 if side.upper() in ['BUY', 'LONG'] else 0.99),
                'sl_pct': 5.0,
                'tp_pct': 10.0
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
        
        logging.debug(f"✅ Position opened: {symbol} {side} @ {entry_price:.6f}")
        # Detailed TP/SL levels moved to debug level
        logging.debug(f"🎯 TP: {levels['take_profit']:.6f} | SL: {levels['stop_loss']:.6f} | Trailing: {levels['trailing_trigger']:.6f}")
        
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
                    logging.debug(f"🎪 Trailing activated for {symbol} at {current_price:.6f}")
                elif side == 'SELL' and current_price <= position['trailing_trigger']:
                    position['trailing_active'] = True
                    logging.debug(f"🎪 Trailing activated for {symbol} at {current_price:.6f}")
            
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
        
        logging.debug(f"🔒 Position closed: {position['symbol']} {exit_reason} PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})")
        
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
