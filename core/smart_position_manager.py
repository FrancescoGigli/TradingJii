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
    """Enhanced position data structure with trailing support"""
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
    
    # TRAILING SYSTEM FIELDS (compatibility with legacy)
    trailing_attivo: bool = False               # Italian field name for compatibility
    best_price: Optional[float] = None          # Best price achieved
    sl_corrente: Optional[float] = None         # Current trailing stop
    atr_value: float = 0.0                      # ATR for calculations
    sl_catastrofico_id: Optional[str] = None    # Catastrophic stop order ID
    
    # Enhanced metadata
    confidence: float = 0.7
    entry_time: str = ""
    close_time: Optional[str] = None
    status: str = "OPEN"  # OPEN, CLOSED_TP, CLOSED_SL, CLOSED_MANUAL
    close_reason: Optional[str] = None
    final_pnl_pct: Optional[float] = None
    final_pnl_usd: Optional[float] = None
    
    # Migration flags (persistenti nel JSON)
    _migrated: bool = False                        # Flag migrazione completata
    _needs_sl_update_on_bybit: bool = False        # Flag update SL necessario

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
        self.session_balance = 1000.0  # Will be updated with real balance
        self.session_start_balance = 1000.0  # Will be updated with real balance  
        self.real_balance_cache = 1000.0  # Cache for real balance from Bybit
        self.load_positions()
        
    def update_real_balance(self, real_balance: float):
        """Update position manager with real balance from Bybit"""
        try:
            self.real_balance_cache = real_balance
            self.session_balance = real_balance
            # Only update start balance if this is the first update of the session
            if self.session_start_balance == 1000.0:
                self.session_start_balance = real_balance
            
            logging.debug(f"💰 Balance sync: Real=${real_balance:.2f}, Session=${self.session_balance:.2f}, Start=${self.session_start_balance:.2f}")
            
        except Exception as e:
            logging.error(f"Error updating real balance: {e}")
        
    def _create_position_from_bybit(self, symbol: str, bybit_data: Dict) -> Position:
        """Create Position object from Bybit data"""
        entry_price = bybit_data['entry_price']
        side = bybit_data['side']
        
        # NUOVA LOGICA: 6% SL (60% del margine con leva 10x), NO TP fisso
        if side == 'buy':
            sl_price = entry_price * 0.94  # 6% below for LONG (era 3%)
            tp_price = None                # NO TAKE PROFIT fisso (era 6% above)
            # 🔧 NUOVO: Trigger corretto (breakeven + buffer per 10% profitto)
            breakeven = entry_price * 1.0006  # entry + commissioni 0.06%
            trailing_trigger = breakeven * 1.010  # +1% sopra breakeven = 10% profitto
        else:
            sl_price = entry_price * 1.06  # 6% above for SHORT (era 3%)
            tp_price = None                # NO TAKE PROFIT fisso (era 6% below)  
            # 🔧 NUOVO: Trigger corretto (breakeven + buffer per 10% profitto)
            breakeven = entry_price * 0.9994  # entry - commissioni 0.06%
            trailing_trigger = breakeven * 0.990  # -1% sotto breakeven = 10% profitto
        
        position_id = f"{symbol.replace('/USDT:USDT', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # CRITICAL FIX: Calculate position_size correctly to ensure minimum IM
        original_position_size = bybit_data['contracts'] * entry_price
        
        # Enforce minimum position size to ensure IM >= $20 (with 10x leverage)
        min_position_size = 200.0  # $200 notional = $20 IM with 10x leverage
        
        if original_position_size < min_position_size:
            # Position too small for proper risk management
            logging.warning(f"⚠️ {symbol}: Original position ${original_position_size:.2f} < ${min_position_size:.2f} minimum")
            
            # Use minimum safe position size  
            position_size = min_position_size
            logging.info(f"🔧 {symbol}: Adjusted position size ${original_position_size:.2f} → ${position_size:.2f} for proper IM")
        else:
            position_size = original_position_size
        
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
            active_bybit_positions = [p for p in bybit_positions if float(p.get('contracts', 0)) != 0]
            
            # 2. Create mapping of Bybit positions
            bybit_symbols = set()
            bybit_position_data = {}
            
            for pos in active_bybit_positions:
                symbol = pos.get('symbol')
                if symbol:
                    raw_side = pos.get('side', '')
                    contracts_raw = pos.get('contracts', 0)
                    entry_price_raw = pos.get('entryPrice', 0)
                    unrealized_pnl_raw = pos.get('unrealizedPnl', 0)
                    
                    # 🔧 VALIDAZIONE ROBUSTA: Evita errori NoneType
                    try:
                        if contracts_raw is None or contracts_raw == '':
                            continue  # Skip posizioni malformate
                        contracts = abs(float(contracts_raw))
                        
                        if entry_price_raw is None or entry_price_raw == '':
                            logging.warning(f"⚠️ {symbol}: Entry price None, skipping")
                            continue
                        entry_price = float(entry_price_raw)
                        
                        if unrealized_pnl_raw is None or unrealized_pnl_raw == '':
                            unrealized_pnl = 0.0  # Default a zero se mancante
                        else:
                            unrealized_pnl = float(unrealized_pnl_raw)
                            
                    except (ValueError, TypeError) as e:
                        logging.warning(f"⚠️ {symbol}: Invalid position data, skipping: {e}")
                        continue

                    # 🔧 SIDE DETECTION: Usa il side da Bybit (corretto e sicuro)
                    if raw_side.lower() in ['buy', 'long']:
                        side = 'buy'
                    elif raw_side.lower() in ['sell', 'short']:  
                        side = 'sell'
                    elif float(contracts_raw) > 0:
                        side = 'buy'  # Fallback: contracts positivi = LONG
                    elif float(contracts_raw) < 0:
                        side = 'sell'  # Fallback: contracts negativi = SHORT
                    else:
                        logging.warning(f"⚠️ Cannot determine position side for {symbol}, skipping")
                        continue

                    bybit_symbols.add(symbol)
                    bybit_position_data[symbol] = {
                        'contracts': contracts,
                        'side': side,
                        'entry_price': entry_price,
                        'unrealized_pnl': unrealized_pnl
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
                        # FIXED: Get REAL current market price, not entry price!
                        try:
                            # Fetch current market price from exchange
                            ticker = await exchange.fetch_ticker(symbol)
                            current_price = float(ticker['last'])  # Real current market price
                        except Exception as e:
                            logging.warning(f"Could not fetch current price for {symbol}: {e}")
                            # Fallback: calculate from unrealized PnL
                            if bybit_data['unrealized_pnl'] != 0 and position.position_size > 0:
                                # Reverse calculate current price from PnL
                                pnl_pct = (bybit_data['unrealized_pnl'] / position.position_size) * 100
                                if position.side == 'buy':
                                    current_price = position.entry_price * (1 + pnl_pct / 100)
                                else:
                                    current_price = position.entry_price * (1 - pnl_pct / 100)
                            else:
                                current_price = position.entry_price  # Last resort fallback
                        
                        # Update with REAL data
                        position.current_price = current_price
                        
                        # 🔧 FIX CRITICO: Calcola PNL correttamente con leva 10x
                        # Calcolo price change percentage
                        price_change_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                        
                        # Applica direzione corretta e leverage
                        if position.side in ['buy', 'long']:
                            # LONG: guadagna se prezzo sale
                            position.unrealized_pnl_pct = price_change_pct * position.leverage
                        else:  # 'sell' o 'short'
                            # SHORT: guadagna se prezzo scende
                            position.unrealized_pnl_pct = -price_change_pct * position.leverage
                        
                        # Calcola PnL USD basato sul margine iniziale
                        initial_margin = position.position_size / position.leverage
                        position.unrealized_pnl_usd = (position.unrealized_pnl_pct / 100) * initial_margin
                        
                        logging.debug(f"💰 PNL Fix - {symbol}: Price {price_change_pct:+.2f}% * Lev {position.leverage}x = {position.unrealized_pnl_pct:+.2f}% PNL")
                        
                        # Update max favorable PnL
                        position.max_favorable_pnl = max(position.max_favorable_pnl, position.unrealized_pnl_pct)
                        
                        break
            
            self.save_positions()
            
            if newly_opened or newly_closed:
                logging.info(f"🔄 Sync result: +{len(newly_opened)} opened, +{len(newly_closed)} closed")
            
            return newly_opened, newly_closed
            
        except Exception as e:
            logging.error(f"Error in Bybit sync: {e}")
            return [], []
    
    def create_position(self, symbol: str, side: str, entry_price: float, 
                       position_size: float, stop_loss: float = None, take_profit: float = None,
                       leverage: int = 10, confidence: float = 0.7) -> str:
        """Create new position in tracker with new 6% SL logic"""
        try:
            position_id = f"{symbol.replace('/USDT:USDT', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # SICUREZZA: FORZA SEMPRE 6% SL (non accetta override)
            if side.lower() == 'buy':
                calculated_sl = entry_price * 0.94  # SEMPRE 6% below - NO OVERRIDE
                calculated_tp = None  # NO TAKE PROFIT fisso
                # 🔧 NUOVO: Trigger corretto (breakeven + buffer per 10% profitto)
                breakeven = entry_price * 1.0006  # entry + commissioni 0.06%
                trailing_trigger = breakeven * 1.010  # +1% sopra breakeven = 10% profitto
            else:
                calculated_sl = entry_price * 1.06  # SEMPRE 6% above - NO OVERRIDE
                calculated_tp = None  # NO TAKE PROFIT fisso
                # 🔧 NUOVO: Trigger corretto (breakeven + buffer per 10% profitto)
                breakeven = entry_price * 0.9994  # entry - commissioni 0.06%
                trailing_trigger = breakeven * 0.990  # -1% sotto breakeven = 10% profitto
            
            position = Position(
                position_id=position_id,
                symbol=symbol,
                side=side.lower(),
                entry_price=entry_price,
                position_size=position_size,
                leverage=leverage,
                stop_loss=calculated_sl,
                take_profit=calculated_tp,
                trailing_trigger=trailing_trigger,
                current_price=entry_price,
                confidence=confidence,
                entry_time=datetime.now().isoformat()
            )
            
            self.open_positions[position_id] = position
            self.save_positions()
            
            logging.debug(f"📊 Position created: {position_id} with 6% SL, no TP")
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
        available = max(0, self.session_balance - used_margin)
        
        # Debug logging per capire il calcolo
        logging.debug(f"💰 Balance calc: Total=${self.session_balance:.2f}, Used margin=${used_margin:.2f}, Available=${available:.2f}")
        
        return available
    
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
        """Load positions from storage with migration support"""
        try:
            with open(self.storage_file, 'r') as f:
                data = json.load(f)
                
                # Load open positions with migration
                for pos_id, pos_data in data.get('open_positions', {}).items():
                    position = Position(**pos_data)
                    # MIGRATE to new 6% SL logic if needed
                    self._migrate_position_to_new_logic(position)
                    self.open_positions[pos_id] = position
                
                # Load closed positions (no migration needed)
                for pos_id, pos_data in data.get('closed_positions', {}).items():
                    position = Position(**pos_data)
                    self.closed_positions[pos_id] = position
                
                self.session_balance = data.get('session_balance', 1000.0)
                self.session_start_balance = data.get('session_start_balance', 1000.0)
                
            total_positions = len(self.open_positions) + len(self.closed_positions)
            migrated = sum(1 for pos in self.open_positions.values() if pos._migrated)
            
            logging.info(f"📁 Positions loaded: {len(self.open_positions)} open, {len(self.closed_positions)} closed")
            if migrated > 0:
                logging.debug(f"🔄 {migrated} positions already migrated to 6% SL logic")
            
        except FileNotFoundError:
            logging.debug("📂 No position file found, starting fresh session")
        except Exception as e:
            logging.error(f"Error loading positions: {e}")
    
    def _migrate_position_to_new_logic(self, position: Position):
        """
        🔄 MIGRATE existing positions to new TRIGGER logic + 6% SL logic
        
        Args:
            position: Position to migrate
        """
        try:
            # Skip if already migrated (ora è un campo della dataclass)
            if position._migrated:
                return
                
            entry_price = position.entry_price
            side = position.side
            old_sl = position.stop_loss
            old_trigger = position.trailing_trigger
            
            # CRITICO: Preserva la direzione originale! (era bug grave)
            if side == 'buy':
                new_sl_6pct = entry_price * 0.94  # 6% below for LONG
                # 🔧 NUOVO: Calcola trigger corretto (breakeven + buffer)
                breakeven = entry_price * 1.0006  # entry + commissioni 0.06%
                new_trigger = breakeven * 1.010  # +1% sopra breakeven = 10% profitto
            else:
                new_sl_6pct = entry_price * 1.06  # 6% above for SHORT  
                # 🔧 NUOVO: Calcola trigger corretto (breakeven + buffer)  
                breakeven = entry_price * 0.9994  # entry - commissioni 0.06%
                new_trigger = breakeven * 0.990  # -1% sotto breakeven = 10% profitto
            
            # SEMPRE aggiorna alla nuova logica (SL + TRIGGER)
            position.stop_loss = new_sl_6pct
            position.take_profit = None  # Remove TP sempre
            position.trailing_trigger = new_trigger  # 🔧 NUOVO TRIGGER CORRETTO
            position._migrated = True  # Mark as migrated
            position._needs_sl_update_on_bybit = True  # FLAG per aggiornare SL su Bybit
            
            # Log solo se il trigger è cambiato significativamente
            if abs(old_trigger - new_trigger) > entry_price * 0.001:  # 0.1% differenza
                logging.debug(f"🔧 {position.symbol}: Updated trigger ${old_trigger:.2f} → ${new_trigger:.2f} (new logic)")
            else:
                logging.debug(f"✅ Position {position.symbol} migrated with correct trigger")
                
        except Exception as e:
            logging.error(f"Error migrating position {position.position_id}: {e}")
    
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
    
    def create_trailing_position(self, symbol: str, side: str, entry_price: float, 
                               position_size: float, atr: float, 
                               catastrophic_sl_id: str, leverage: int = 10, 
                               confidence: float = 0.7) -> str:
        """
        Create new position with trailing system (compatibility method)
        Updated to use new 6% SL logic without catastrophic stop
        
        Args:
            symbol: Trading symbol
            side: Position side
            entry_price: Entry price
            position_size: Position size USD
            atr: Average True Range  
            catastrophic_sl_id: DEPRECATED - no longer used
            leverage: Position leverage
            confidence: ML confidence
            
        Returns:
            str: Position ID
        """
        # NUOVA LOGICA: 6% SL fisso, NO TP, NO stop catastrofico
        # Il parametro catastrophic_sl_id è ignorato (compatibilità legacy)
        
        # Use regular create_position method with new logic
        return self.create_position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            position_size=position_size,
            stop_loss=None,  # Usa la logica automatica del 6%
            take_profit=None,  # NO take profit
            leverage=leverage,
            confidence=confidence
        )
    
    def get_trailing_positions(self) -> List[Position]:
        """Get all positions that need trailing monitoring (compatibility method)"""
        return self.get_active_positions()
    
    async def emergency_update_bybit_stop_losses(self, exchange, order_manager):
        """
        🔧 Verifica e aggiorna stop loss su Bybit se necessario
        
        Args:
            exchange: Bybit exchange instance
            order_manager: Order manager for API calls
        """
        try:
            updated_count = 0
            positions_needing_update = [pos for pos in self.get_active_positions() if pos._needs_sl_update_on_bybit]
            
            if not positions_needing_update:
                logging.debug("✅ All positions have correct stop losses")
                return
            
            for position in positions_needing_update:
                try:
                    # Calculate correct 6% SL
                    if position.side == 'buy':
                        correct_sl = position.entry_price * 0.94  # 6% below
                    else:
                        correct_sl = position.entry_price * 1.06  # 6% above
                    
                    # Update SL on Bybit
                    result = await order_manager.set_trading_stop(
                        exchange, position.symbol, correct_sl, None  # Solo SL, NO TP
                    )
                    
                    if result.success:
                        position._needs_sl_update_on_bybit = False
                        position.sl_order_id = result.order_id
                        updated_count += 1
                        
                        logging.info(f"🔧 {position.symbol}: Stop loss updated on Bybit")
                    else:
                        # Gestisci errori "non preoccupanti"
                        error_msg = str(result.error).lower()
                        if "not modified" in error_msg or "api error 0: ok" in error_msg:
                            position._needs_sl_update_on_bybit = False  # Mark as done
                            logging.debug(f"📝 {position.symbol}: Stop loss already correct on Bybit")
                        else:
                            logging.warning(f"⚠️ Failed to update SL for {position.symbol}: {result.error}")
                        
                except Exception as e:
                    logging.error(f"❌ Error updating SL for {position.symbol}: {e}")
                    continue
            
            if updated_count > 0:
                self.save_positions()
                logging.info(f"🔧 Stop loss updates completed: {updated_count} positions")
                
        except Exception as e:
            logging.error(f"Error in stop loss verification: {e}")
    
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
