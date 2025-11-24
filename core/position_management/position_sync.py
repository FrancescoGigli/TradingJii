#!/usr/bin/env python3
"""
🔄 POSITION SYNC WITH BYBIT

Handles synchronization between local positions and Bybit exchange.
Detects newly opened/closed positions and emergency SL fixes.
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set, Optional
from termcolor import colored

from .position_data import ThreadSafePosition
from .position_core import PositionCore

# Import trade history logger
try:
    from core.trade_history_logger import log_trade_opened_from_position, log_trade_closed_from_position
    TRADE_HISTORY_LOGGER_AVAILABLE = True
except ImportError:
    TRADE_HISTORY_LOGGER_AVAILABLE = False
    logging.warning("⚠️ Trade History Logger not available")



class PositionSync:
    """Handles Bybit synchronization operations"""
    
    def __init__(self, core: PositionCore):
        self.core = core
    
    async def sync_with_bybit(self, exchange) -> Tuple[List[ThreadSafePosition], List[ThreadSafePosition]]:
        """
        Synchronize positions with Bybit
        
        Returns:
            Tuple: (newly_opened, newly_closed)
        """
        try:
            # Fetch Bybit positions
            bybit_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_bybit = [p for p in bybit_positions if float(p.get('contracts', 0)) != 0]
            
            # Parse Bybit data
            bybit_symbols, bybit_data = self._parse_bybit_positions(active_bybit)
            
            # Atomic sync operation
            newly_opened = []
            newly_closed = []
            symbols_needing_sl = []
            
            with self.core.get_lock():
                # Get tracked symbols
                tracked_symbols = set(
                    pos.symbol for pos in self.core._get_open_positions_unsafe().values()
                    if pos.status == "OPEN"
                )
                
                # Detect newly opened
                new_symbols = bybit_symbols - tracked_symbols
                
                for symbol in new_symbols:
                    data = bybit_data[symbol]
                    position = self._create_position_from_bybit(symbol, data)
                    
                    self.core._get_open_positions_unsafe()[position.position_id] = position
                    newly_opened.append(position)
                    
                    # 📝 LOG TRADE OPENED
                    if TRADE_HISTORY_LOGGER_AVAILABLE:
                        try:
                            log_trade_opened_from_position(position)
                        except Exception as log_err:
                            logging.warning(f"⚠️ Failed to log trade opened: {log_err}")
                    
                    # Check if SL is missing
                    if data.get('real_stop_loss') is None:
                        symbols_needing_sl.append((symbol, data))
                        logging.warning(colored(
                            f"🚨 {symbol.replace('/USDT:USDT', '')} opened WITHOUT stop loss!",
                            "red", attrs=['bold']
                        ))
                    
                    side_display = "🟢 LONG" if data['side'] == 'buy' else "🔴 SHORT"
                    logging.info(f"🔄 Sync: NEW position {symbol} {side_display}")
                
                # Detect newly closed
                closed_symbols = tracked_symbols - bybit_symbols
                
                for symbol in closed_symbols:
                    positions_to_close = [
                        pos for pos in self.core._get_open_positions_unsafe().values()
                        if pos.symbol == symbol and pos.status == "OPEN"
                    ]
                    
                    for position in positions_to_close:
                        # 🆕 NEW: Fetch real PnL from trade history with ALL fees included
                        await self._close_position_from_bybit(exchange, position)
                        newly_closed.append(position)
                        
                        # 📝 LOG TRADE CLOSED
                        if TRADE_HISTORY_LOGGER_AVAILABLE:
                            try:
                                exit_price = position.current_price
                                close_reason = "SYNC_CLOSED"
                                log_trade_closed_from_position(position, exit_price, close_reason)
                            except Exception as log_err:
                                logging.warning(f"⚠️ Failed to log trade closed: {log_err}")
                        
                        logging.info(f"🔄 Sync: CLOSED {symbol} PnL: {position.unrealized_pnl_pct:+.2f}%")
                
                # Update existing positions
                for symbol in (bybit_symbols & tracked_symbols):
                    await self._update_existing_position(exchange, symbol, bybit_data.get(symbol))
                
                self.core._save_positions()
            
            # Fix missing SLs (outside lock)
            if symbols_needing_sl:
                for symbol, data in symbols_needing_sl:
                    try:
                        await self._emergency_fix_missing_sl(exchange, symbol, data)
                    except Exception as e:
                        logging.error(f"🚨 Emergency SL fix failed for {symbol}: {e}")
            
            return newly_opened, newly_closed
            
        except Exception as e:
            logging.error(f"Bybit sync failed: {e}")
            return [], []
    
    def _parse_bybit_positions(self, positions: List) -> Tuple[Set[str], Dict]:
        """Parse Bybit position data"""
        bybit_symbols = set()
        bybit_data = {}
        
        for pos in positions:
            try:
                symbol = pos.get('symbol')
                if not symbol:
                    continue
                
                symbol_short = symbol.replace('/USDT:USDT', '')
                
                # Validate critical fields
                contracts_val = pos.get('contracts')
                entry_price_val = pos.get('entryPrice')
                
                if contracts_val is None or contracts_val == '' or entry_price_val is None or entry_price_val == '':
                    logging.warning(f"⚠️ {symbol_short}: Missing critical data, skipping")
                    continue
                
                # Parse position data
                contracts_raw = float(contracts_val)
                contracts = abs(contracts_raw)
                entry_price = float(entry_price_val)
                
                # Get PnL directly from Bybit
                unrealized_pnl_val = pos.get('unrealizedPnl')
                if unrealized_pnl_val is None or unrealized_pnl_val == '':
                    # FIX #2: Reduce noise - this is normal for newly opened positions
                    logging.debug(f"📊 {symbol_short}: unrealizedPnl not yet available, using 0 (normal for new positions)")
                    unrealized_pnl = 0.0
                else:
                    unrealized_pnl = float(unrealized_pnl_val)
                    logging.debug(f"✅ {symbol_short}: Real PnL from Bybit: ${unrealized_pnl:+.2f}")
                
                # Determine side
                explicit_side = pos.get('side', '').lower()
                if explicit_side in ['buy', 'long']:
                    side = 'buy'
                elif explicit_side in ['sell', 'short']:
                    side = 'sell'
                else:
                    side = 'buy' if contracts_raw > 0 else 'sell'
                
                # Get leverage, IM and SL from Bybit
                leverage_val = pos.get('leverage', 10)
                leverage = float(leverage_val)
                
                real_im_val = pos.get('initialMargin') or pos.get('margin')
                real_im = float(real_im_val) if real_im_val else (contracts * entry_price) / leverage
                
                real_sl_val = pos.get('stopLoss')
                real_sl = float(real_sl_val) if real_sl_val and real_sl_val != '' and real_sl_val != '0' else None
                
                bybit_symbols.add(symbol)
                bybit_data[symbol] = {
                    'contracts': contracts,
                    'side': side,
                    'entry_price': entry_price,
                    'unrealized_pnl': unrealized_pnl,
                    'real_initial_margin': real_im,
                    'real_stop_loss': real_sl,
                    'leverage': leverage
                }
                
                # 🆕 LOG RAW JSON for debugging
                logging.debug(f"📊 RAW BYBIT DATA for {symbol_short}:")
                logging.debug(json.dumps(pos, indent=2, default=str))
                
            except (ValueError, TypeError) as e:
                logging.warning(f"⚠️ Invalid Bybit data for {pos.get('symbol')}: {e}")
                continue
        
        return bybit_symbols, bybit_data
    
    def _create_position_from_bybit(self, symbol: str, data: Dict) -> ThreadSafePosition:
        """Create position from Bybit data"""
        from config import LEVERAGE, STOP_LOSS_PCT
        
        entry_price = data['entry_price']
        side = data['side']
        
        # FIX #5: Use correct SL from config instead of hardcoded values
        if side == 'buy':
            stop_loss = entry_price * (1 - STOP_LOSS_PCT)
            trailing_trigger = entry_price * (1 + STOP_LOSS_PCT) * 1.010
        else:
            stop_loss = entry_price * (1 + STOP_LOSS_PCT)
            trailing_trigger = entry_price * (1 - STOP_LOSS_PCT) * 0.990
        
        position_id = f"{symbol.replace('/USDT:USDT', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        real_im = data.get('real_initial_margin')
        real_sl = data.get('real_stop_loss')
        real_leverage = data.get('leverage', LEVERAGE)
        
        return ThreadSafePosition(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            position_size=data['contracts'] * entry_price,
            leverage=int(real_leverage),  # Uses real leverage from Bybit
            stop_loss=real_sl if real_sl else stop_loss,
            take_profit=None,
            trailing_trigger=trailing_trigger,
            current_price=entry_price,
            confidence=0.7,
            entry_time=datetime.now().isoformat(),
            origin="SYNCED",
            unrealized_pnl_usd=data['unrealized_pnl'],
            real_initial_margin=real_im,
            real_stop_loss=real_sl,
            _migrated=True
        )
    
    async def _close_position_from_bybit(self, exchange, position: ThreadSafePosition):
        """
        Close position with REAL PnL from Bybit closed-pnl endpoint
        
        🆕 FIX: Uses correct Bybit endpoint for accurate realized PnL
        This ensures 100% accuracy including all fees and funding
        """
        symbol_short = position.symbol.replace('/USDT:USDT', '')
        
        # 🆕 STEP 1: Try to fetch REAL PnL from Bybit closed-pnl endpoint
        trade_data_found = False
        
        try:
            logging.info(f"🔍 Fetching closed PnL data for {symbol_short}...")
            
            # ✅ FIX: Use correct Bybit endpoint for closed positions
            # This endpoint has the REAL realized PnL with all fees included
            closed_pnl_data = await exchange.privateGetV5PositionClosedPnl({
                'category': 'linear',
                'symbol': position.symbol.replace('/', ''),
                'limit': 1
            })
            
            if closed_pnl_data and 'result' in closed_pnl_data:
                result_list = closed_pnl_data['result'].get('list', [])
                
                if result_list:
                    closed_position = result_list[0]
                    
                    # 🆕 Get REAL closed PnL (includes ALL fees)
                    closed_pnl = closed_position.get('closedPnl')
                    if closed_pnl:
                        pnl_usd = float(closed_pnl)
                        position.unrealized_pnl_usd = pnl_usd
                        
                        # Calculate % from USD using REAL initial margin
                        # Use real_initial_margin if available, otherwise calculate
                        if hasattr(position, 'real_initial_margin') and position.real_initial_margin:
                            initial_margin = position.real_initial_margin
                        else:
                            initial_margin = position.position_size / position.leverage
                        
                        if initial_margin > 0:
                            pnl_pct = (pnl_usd / initial_margin) * 100
                            position.unrealized_pnl_pct = pnl_pct
                        
                        logging.info(f"✅ {symbol_short}: REAL PnL from Bybit: ${pnl_usd:+.2f} ({pnl_pct:+.2f}%) [includes ALL fees]")
                        trade_data_found = True
                    
                    # 🆕 Get REAL exit price
                    avg_exit_price = closed_position.get('avgExitPrice')
                    if avg_exit_price:
                        position.current_price = float(avg_exit_price)
                        logging.info(f"✅ {symbol_short}: Real exit price: ${position.current_price:.6f}")
                    
                    # 🆕 Get REAL close timestamp
                    updated_time = closed_position.get('updatedTime')
                    if updated_time:
                        # Bybit returns timestamp in milliseconds
                        position.close_time = datetime.fromtimestamp(int(updated_time)/1000).isoformat()
                        logging.info(f"✅ {symbol_short}: Real close time: {position.close_time}")
                    
                    # 🆕 Log raw data for debugging
                    logging.debug(f"📊 RAW CLOSED PNL DATA for {symbol_short}:")
                    logging.debug(json.dumps(closed_position, indent=2, default=str))
                    
        except Exception as e:
            logging.warning(f"⚠️ Could not fetch closed PnL from Bybit for {symbol_short}: {e}")
            
            # FALLBACK: Try old method with trade history
            try:
                logging.info(f"🔄 Trying fallback: trade history for {symbol_short}...")
                trades = await exchange.fetch_my_trades(symbol=position.symbol, limit=5)
                
                if trades:
                    # Sort by timestamp descending
                    trades.sort(key=lambda t: t.get('timestamp', 0), reverse=True)
                    last_trade = trades[0]
                    
                    # Get exit price
                    exit_price = last_trade.get('price')
                    if exit_price:
                        position.current_price = float(exit_price)
                        logging.info(f"✅ {symbol_short}: Exit price from trades: ${exit_price:.6f}")
                    
                    # Get timestamp
                    close_timestamp = last_trade.get('timestamp')
                    if close_timestamp:
                        position.close_time = datetime.fromtimestamp(close_timestamp/1000).isoformat()
                        
            except Exception as trade_error:
                logging.warning(f"⚠️ Fallback trade history also failed for {symbol_short}: {trade_error}")
        
        # FALLBACK: Use last known unrealizedPnl or calculate
        if not trade_data_found:
            logging.warning(f"⚠️ {symbol_short}: Using fallback PnL calculation")
            
            # Try last known PnL from Bybit position data
            if hasattr(position, 'unrealized_pnl_usd') and position.unrealized_pnl_usd != 0:
                pnl_usd = position.unrealized_pnl_usd
                initial_margin = position.position_size / position.leverage
                if initial_margin > 0:
                    pnl_pct = (pnl_usd / initial_margin) * 100
                    position.unrealized_pnl_pct = pnl_pct
                logging.info(f"💰 {symbol_short}: Using last known PnL: ${pnl_usd:+.2f} (may not include final fees)")
            else:
                # Final fallback: calculate
                logging.warning(f"⚠️ {symbol_short}: Calculating PnL (NO FEES INCLUDED)")
                
                if position.side == 'buy':
                    pnl_pct = ((position.current_price - position.entry_price) / position.entry_price) * 100 * position.leverage
                else:
                    pnl_pct = ((position.entry_price - position.current_price) / position.entry_price) * 100 * position.leverage
                
                initial_margin = position.position_size / position.leverage
                pnl_usd = (pnl_pct / 100) * initial_margin
                
                position.unrealized_pnl_pct = pnl_pct
                position.unrealized_pnl_usd = pnl_usd
                
                logging.warning(f"❌ CALCULATED PnL: ${pnl_usd:+.2f} (DOES NOT INCLUDE FEES)")
            
            # Set close time to now if not set
            if not position.close_time or position.close_time == "":
                position.close_time = datetime.now().isoformat()
        
        # 🔍 INFER CLOSE REASON intelligently
        exit_price = position.current_price
        close_reason = self._infer_close_reason(position, exit_price)
        
        # Call close_position which will trigger trade analysis
        self.core.close_position(
            position_id=position.position_id,
            exit_price=exit_price,
            close_reason=close_reason
        )
        
        logging.info(f"✅ {symbol_short}: Closed with reason: {close_reason}")
    
    def _infer_close_reason(self, position: ThreadSafePosition, exit_price: float) -> str:
        """
        Intelligently infer why the position was closed based on:
        - Exit price vs Stop Loss
        - PnL amount and direction
        - Trailing stop status
        """
        try:
            pnl_usd = position.unrealized_pnl_usd or 0.0
            sl_price = position.real_stop_loss or position.stop_loss
            had_trailing = (
                hasattr(position, 'trailing_data') and 
                position.trailing_data and 
                position.trailing_data.enabled
            )
            
            symbol_short = position.symbol.replace('/USDT:USDT', '')
            
            # Check if exit price is close to SL (within 0.5%)
            if sl_price and exit_price > 0:
                price_diff_pct = abs((exit_price - sl_price) / sl_price) * 100.0
                
                if price_diff_pct < 0.5:
                    # Exit price matches SL - Stop Loss hit
                    logging.debug(f"🔍 {symbol_short}: Detected STOP_LOSS (exit ${exit_price:.6f} ≈ SL ${sl_price:.6f})")
                    return "STOP_LOSS_HIT"
            
            # Analyze based on PnL
            if pnl_usd > 1.0:  # Profitable
                if had_trailing:
                    logging.debug(f"🔍 {symbol_short}: Detected TRAILING_STOP (profit ${pnl_usd:.2f} with trailing)")
                    return "TRAILING_STOP_HIT"
                else:
                    logging.debug(f"🔍 {symbol_short}: Detected MANUAL_CLOSE (profit ${pnl_usd:.2f})")
                    return "MANUAL_CLOSE"
                    
            elif pnl_usd < -1.0:  # Loss
                # If significant loss but not at SL price - early exit
                if sl_price and exit_price > 0:
                    price_diff_pct = abs((exit_price - sl_price) / sl_price) * 100.0
                    if price_diff_pct >= 0.5:  # Not at SL
                        logging.debug(f"🔍 {symbol_short}: Detected EARLY_EXIT_LOSS (loss but not at SL)")
                        return "EARLY_EXIT_LOSS"
                
                # Significant loss, likely SL
                logging.debug(f"🔍 {symbol_short}: Detected STOP_LOSS (significant loss ${pnl_usd:.2f})")
                return "STOP_LOSS_HIT"
                
            else:  # Breakeven
                logging.debug(f"🔍 {symbol_short}: Detected BREAKEVEN close")
                return "BREAKEVEN"
                
        except Exception as e:
            logging.debug(f"Error inferring close reason: {e}")
            return "SYNC_CLOSED"  # Fallback
    
    async def _update_existing_position(self, exchange, symbol: str, data: Optional[Dict]):
        """Update existing position with current price and track for AI analysis"""
        if not data:
            return
        
        try:
            ticker = await exchange.fetch_ticker(symbol)
            current_price = float(ticker['last'])
            current_volume = float(ticker.get('quoteVolume', 0))
            
            for position in self.core._get_open_positions_unsafe().values():
                if position.symbol == symbol and position.status == "OPEN":
                    # Update price and PnL
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
                    
                    # Update real SL from Bybit
                    real_sl = data.get('real_stop_loss')
                    if real_sl is not None:
                        position.real_stop_loss = real_sl
                        position.stop_loss = real_sl
                    
                    
                    break
                    
        except Exception as e:
            logging.warning(f"Could not update price for {symbol}: {e}")
    
    async def _emergency_fix_missing_sl(self, exchange, symbol: str, data: Dict):
        """Emergency fix for positions without stop loss"""
        try:
            from config import STOP_LOSS_PCT
            from core.price_precision_handler import global_price_precision_handler
            from core.order_manager import global_order_manager
            
            symbol_short = symbol.replace('/USDT:USDT', '')
            entry_price = data['entry_price']
            side = data['side']
            
            logging.error(colored(
                f"🚨🚨🚨 EMERGENCY SL FIX: {symbol_short} 🚨🚨🚨",
                "red", attrs=['bold']
            ))
            
            # Calculate correct SL
            if side == 'buy':
                target_sl = entry_price * (1 - STOP_LOSS_PCT)
            else:
                target_sl = entry_price * (1 + STOP_LOSS_PCT)
            
            # Normalize to tick size
            normalized_sl, success = await global_price_precision_handler.normalize_stop_loss_price(
                exchange, symbol, side, entry_price, target_sl
            )
            
            if not success:
                logging.error(f"🚨 {symbol_short}: Failed to normalize SL price!")
                return
            
            # Apply SL on Bybit
            result = await global_order_manager.set_trading_stop(
                exchange, symbol,
                stop_loss=normalized_sl,
                take_profit=None
            )
            
            if result.success:
                # Update tracked position
                with self.core.get_lock():
                    for pos in self.core._get_open_positions_unsafe().values():
                        if pos.symbol == symbol and pos.status == "OPEN":
                            pos.real_stop_loss = normalized_sl
                            pos.stop_loss = normalized_sl
                            self.core._save_positions()
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
                    f"   ⚠️ POSITION STILL AT RISK!",
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
