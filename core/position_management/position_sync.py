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

# Import Trade Analyzer for price tracking
# NOTE: Import dynamically to avoid None issue with initialization order
TRADE_ANALYZER_AVAILABLE = True
try:
    from core.trade_analyzer import TradeAnalyzer
except ImportError:
    TRADE_ANALYZER_AVAILABLE = False
    logging.debug("⚠️ Trade Analyzer not available in sync")


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
                    
                    # 🤖 NEW: Save trade snapshot for synced positions too!
                    # This enables GPT analysis even for positions opened directly on Bybit
                    if TRADE_ANALYZER_AVAILABLE:
                        try:
                            from core.trade_analyzer import global_trade_analyzer, TradeSnapshot
                            if global_trade_analyzer and global_trade_analyzer.enabled:
                                # Create snapshot with SYNCED origin
                                snapshot = TradeSnapshot(
                                    symbol=symbol,
                                    timestamp=datetime.now().isoformat(),
                                    prediction_signal="SYNCED",  # Mark as synced (unknown ML prediction)
                                    ml_confidence=0.0,  # Unknown confidence
                                    ensemble_votes={},  # No ensemble data
                                    entry_price=data['entry_price'],
                                    entry_features={},  # No ML features available
                                    expected_target=0.10,  # Default target
                                    expected_risk=0.025  # Default risk
                                )
                                global_trade_analyzer.save_trade_snapshot(position.position_id, snapshot)
                                logging.info(f"📸 Trade snapshot saved for SYNCED position: {symbol.replace('/USDT:USDT', '')}")
                        except Exception as e:
                            logging.warning(f"⚠️ Failed to save trade snapshot for synced position: {e}")
                    
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
                    logging.warning(f"⚠️ {symbol_short}: unrealizedPnl not provided, using 0")
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
                
                # Get real IM and SL from Bybit
                real_im_val = pos.get('initialMargin') or pos.get('margin')
                real_im = float(real_im_val) if real_im_val else (contracts * entry_price) / float(pos.get('leverage', 10))
                
                real_sl_val = pos.get('stopLoss')
                real_sl = float(real_sl_val) if real_sl_val and real_sl_val != '' and real_sl_val != '0' else None
                
                bybit_symbols.add(symbol)
                bybit_data[symbol] = {
                    'contracts': contracts,
                    'side': side,
                    'entry_price': entry_price,
                    'unrealized_pnl': unrealized_pnl,
                    'real_initial_margin': real_im,
                    'real_stop_loss': real_sl
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
        entry_price = data['entry_price']
        side = data['side']
        
        # Fallback SL calculation
        stop_loss = entry_price * (0.94 if side == 'buy' else 1.06)
        
        # Trailing trigger
        if side == 'buy':
            trailing_trigger = entry_price * 1.006 * 1.010
        else:
            trailing_trigger = entry_price * 0.9994 * 0.990
        
        position_id = f"{symbol.replace('/USDT:USDT', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        real_im = data.get('real_initial_margin')
        real_sl = data.get('real_stop_loss')
        
        return ThreadSafePosition(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            position_size=data['contracts'] * entry_price,
            leverage=10,
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
        Close position with REAL PnL from Bybit trade history
        
        🆕 NEW: Fetches actual realized PnL, exit price, and timestamp from trade history
        This ensures 100% accuracy including all fees and funding
        """
        symbol_short = position.symbol.replace('/USDT:USDT', '')
        
        # 🆕 STEP 1: Try to fetch REAL trade data from Bybit
        trade_data_found = False
        
        try:
            logging.info(f"🔍 Fetching trade history for {symbol_short}...")
            trades = await exchange.fetch_my_trades(symbol=position.symbol, limit=10)
            
            if trades:
                # Sort by timestamp descending to get most recent
                trades.sort(key=lambda t: t.get('timestamp', 0), reverse=True)
                last_trade = trades[0]
                
                # 🆕 Get REAL exit price
                exit_price = last_trade.get('price')
                if exit_price:
                    position.current_price = float(exit_price)
                    logging.info(f"✅ {symbol_short}: Real exit price: ${exit_price:.6f}")
                    trade_data_found = True
                
                # 🆕 Get REAL realized PnL (includes ALL fees and funding)
                realized_pnl = None
                if 'info' in last_trade and last_trade['info']:
                    realized_pnl = last_trade['info'].get('realizedPnl') or last_trade['info'].get('closedPnl')
                
                if realized_pnl not in (None, '', '0', 0):
                    pnl_usd = float(realized_pnl)
                    position.unrealized_pnl_usd = pnl_usd
                    
                    # Calculate % from USD
                    initial_margin = position.position_size / position.leverage
                    if initial_margin > 0:
                        pnl_pct = (pnl_usd / initial_margin) * 100
                        position.unrealized_pnl_pct = pnl_pct
                    
                    logging.info(f"✅ {symbol_short}: REAL PnL from trade history: ${pnl_usd:+.2f} (includes ALL fees)")
                    trade_data_found = True
                
                # 🆕 Get REAL timestamp
                close_timestamp = last_trade.get('timestamp')
                if close_timestamp:
                    position.close_time = datetime.fromtimestamp(close_timestamp/1000).isoformat()
                    logging.info(f"✅ {symbol_short}: Real close time: {position.close_time}")
                
                # 🆕 Log raw trade data for debugging
                logging.debug(f"📊 RAW TRADE DATA for {symbol_short}:")
                logging.debug(json.dumps(last_trade, indent=2, default=str))
                
        except Exception as e:
            logging.warning(f"⚠️ Could not fetch trade history for {symbol_short}: {e}")
        
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
        
        # Use close_position to trigger analysis and proper cleanup
        # Extract exit price and close reason
        exit_price = position.current_price
        close_reason = "SYNC_CLOSED"
        
        # Call close_position which will trigger trade analysis
        self.core.close_position(
            position_id=position.position_id,
            exit_price=exit_price,
            close_reason=close_reason
        )
    
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
                    
                    # 🤖 NEW: Save price snapshot for AI analysis
                    # This tracks how price moved during trade lifecycle
                    if TRADE_ANALYZER_AVAILABLE:
                        try:
                            from core.trade_analyzer import global_trade_analyzer
                            if global_trade_analyzer and global_trade_analyzer.enabled:
                                global_trade_analyzer.add_price_snapshot(
                                    position_id=position.position_id,
                                    price=current_price,
                                    volume=current_volume,
                                    timestamp=datetime.now().isoformat()
                                )
                                logging.debug(f"📸 Price snapshot saved for {symbol.replace('/USDT:USDT', '')}: ${current_price:.6f}")
                        except Exception as snapshot_err:
                            logging.debug(f"⚠️ Failed to save price snapshot: {snapshot_err}")
                    
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
