#!/usr/bin/env python3
"""
💾 POSITION I/O OPERATIONS

Handles loading, saving, and serialization of positions.
Includes OS-level file locking and corrupted file recovery.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Tuple, Any
from dataclasses import asdict

from .position_data import ThreadSafePosition, TrailingStopData

# OS-level file locking
if sys.platform == 'win32':
    import msvcrt
else:
    import fcntl


class PositionIO:
    """Handles all file I/O operations for positions"""
    
    def __init__(self, storage_file: str = "thread_safe_positions.json"):
        self.storage_file = storage_file
    
    def load_positions(self) -> Tuple[Dict[str, ThreadSafePosition], Dict[str, ThreadSafePosition], float, float]:
        """
        Load positions from JSON file
        
        Returns:
            Tuple: (open_positions, closed_positions, session_balance, session_start_balance)
        """
        open_positions = {}
        closed_positions = {}
        session_balance = 1000.0
        session_start_balance = 1000.0
        
        try:
            with open(self.storage_file, 'r') as f:
                data = json.load(f)
            
            # Load open positions
            for pos_id, pos_data in data.get('open_positions', {}).items():
                # Remove old trailing_data if present
                if 'trailing_data' in pos_data:
                    pos_data.pop('trailing_data', None)
                
                position = ThreadSafePosition(**pos_data)
                self._migrate_position(position)
                open_positions[pos_id] = position
            
            # Load closed positions
            for pos_id, pos_data in data.get('closed_positions', {}).items():
                if 'trailing_data' in pos_data:
                    pos_data.pop('trailing_data', None)
                
                position = ThreadSafePosition(**pos_data)
                
                # Migrate old closed positions: set pnl_* and exit_price if missing
                if position.pnl_pct == 0.0 and position.unrealized_pnl_pct != 0.0:
                    position.pnl_pct = position.unrealized_pnl_pct
                if position.pnl_usd == 0.0 and position.unrealized_pnl_usd != 0.0:
                    position.pnl_usd = position.unrealized_pnl_usd
                if position.exit_price is None and position.current_price != 0.0:
                    position.exit_price = position.current_price
                
                closed_positions[pos_id] = position
            
            # Load balance data
            session_balance = data.get('session_balance', 1000.0)
            session_start_balance = data.get('session_start_balance', 1000.0)
            
            logging.debug(f"💾 Loaded: {len(open_positions)} open, {len(closed_positions)} closed")
            
        except FileNotFoundError:
            logging.info("💾 No position file found, starting fresh")
        except json.JSONDecodeError as json_error:
            logging.warning(f"💾 Corrupted position file: {json_error}")
            self._backup_corrupted_file()
            logging.info("💾 Fresh session after corruption recovery")
        except Exception as e:
            logging.error(f"💾 Error loading positions: {e}")
        
        return open_positions, closed_positions, session_balance, session_start_balance
    
    def save_positions(self, open_positions: Dict[str, ThreadSafePosition],
                      closed_positions: Dict[str, ThreadSafePosition],
                      session_balance: float,
                      session_start_balance: float,
                      operation_count: int = 0,
                      lock_contention_count: int = 0) -> bool:
        """
        Save positions to JSON file with OS-level locking
        
        Returns:
            bool: True if save successful
        """
        try:
            # Convert to serializable format
            open_dict = {pos_id: asdict(pos) for pos_id, pos in open_positions.items()}
            closed_dict = {pos_id: asdict(pos) for pos_id, pos in closed_positions.items()}
            
            data = {
                'open_positions': open_dict,
                'closed_positions': closed_dict,
                'session_balance': session_balance,
                'session_start_balance': session_start_balance,
                'last_save': datetime.now().isoformat(),
                'operation_count': operation_count,
                'lock_contention_count': lock_contention_count
            }
            
            # Write with OS-level file locking
            with open(self.storage_file, 'w') as f:
                try:
                    # Acquire exclusive lock
                    if sys.platform == 'win32':
                        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                    
                    logging.debug(f"💾 Saved: {len(open_positions)} open, {len(closed_positions)} closed")
                    return True
                    
                except (IOError, OSError) as lock_error:
                    logging.warning(f"💾 File lock conflict: {lock_error}")
                    return False
            
        except Exception as e:
            logging.error(f"💾 Save failed: {e}")
            return False
    
    def _backup_corrupted_file(self):
        """Create backup of corrupted file"""
        try:
            import shutil
            backup_name = f"{self.storage_file}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(self.storage_file, backup_name)
            logging.info(f"💾 Corrupted file backed up as: {backup_name}")
        except Exception as e:
            logging.error(f"💾 Could not backup corrupted file: {e}")
    
    def _migrate_position(self, position: ThreadSafePosition):
        """Migrate position to new logic if needed"""
        try:
            if position._migrated:
                return
            
            entry_price = position.entry_price
            side = position.side
            
            # Simple stop loss calculation
            position.stop_loss = entry_price * (0.94 if side == 'buy' else 1.06)
            
            # Calculate trailing trigger
            if side == 'buy':
                position.trailing_trigger = entry_price * 1.006 * 1.010
            else:
                position.trailing_trigger = entry_price * 0.9994 * 0.990
            
            position.take_profit = None
            position._migrated = True
            position._needs_sl_update_on_bybit = True
            
            logging.debug(f"💾 Position migrated: {position.symbol}")
            
        except Exception as e:
            logging.error(f"💾 Position migration failed: {e}")
    
    def serialize_object(self, obj: Any) -> Any:
        """
        Recursively convert object to JSON-serializable format
        
        Args:
            obj: Object to serialize
            
        Returns:
            JSON-serializable value
        """
        try:
            if obj is None:
                return None
            
            # Basic JSON-serializable types
            if isinstance(obj, (str, int, float, bool)):
                return obj
            
            # Lists and tuples
            if isinstance(obj, (list, tuple)):
                return [self.serialize_object(item) for item in obj]
            
            # Dictionaries
            if isinstance(obj, dict):
                return {str(k): self.serialize_object(v) for k, v in obj.items()}
            
            # Objects with __dict__
            if hasattr(obj, '__dict__'):
                result = {}
                for key, value in obj.__dict__.items():
                    if not key.startswith('_') and not callable(value):
                        try:
                            result[key] = self.serialize_object(value)
                        except Exception:
                            continue
                return result
            
            # Fallback to string
            return str(obj)
            
        except Exception as e:
            logging.warning(f"💾 Serialization failed: {e}")
            return None
