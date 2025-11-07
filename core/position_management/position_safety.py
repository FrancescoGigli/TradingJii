#!/usr/bin/env python3
"""
🛡️ POSITION SAFETY CHECKS

Auto-fixes incorrect stop losses and closes unsafe positions.
Validates position sizes and ensures risk management.
"""

import logging
from termcolor import colored

from .position_core import PositionCore


class PositionSafety:
    """Handles position safety checks and auto-fixes"""
    
    def __init__(self, core: PositionCore):
        self.core = core
    
    async def check_and_fix_stop_losses(self, exchange) -> int:
        """
        Check all positions and fix incorrect stop losses
        
        CRITICAL FIX: Usa SOLO set_trading_stop() per consistenza
        
        Returns:
            int: Number of SLs fixed
        """
        from config import STOP_LOSS_PCT
        from core.order_manager import global_order_manager
        import asyncio
        
        TOLERANCE_PCT = 0.005  # ±0.5% tolerance
        DEBOUNCE_SEC = 300  # 5 minuti invece di 30 secondi
        fixed_count = 0
        
        # Track last fix time per symbol
        if not hasattr(self, '_last_fix_time'):
            self._last_fix_time = {}
        
        try:
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
                    
                    # Skip if trailing is active
                    has_trailing = False
                    for pos in self.core._get_open_positions_unsafe().values():
                        if pos.symbol == symbol and pos.status == "OPEN":
                            if hasattr(pos, 'trailing_data') and pos.trailing_data and pos.trailing_data.enabled:
                                has_trailing = True
                                break
                    
                    if has_trailing:
                        logging.debug(f"[Auto-Fix] {symbol_short}: Skipping - trailing active")
                        continue
                    
                    # Debounce: Skip if recently fixed
                    import time
                    last_fix = self._last_fix_time.get(symbol, 0)
                    if time.time() - last_fix < DEBOUNCE_SEC:
                        logging.debug(f"[Auto-Fix] {symbol_short}: Skipping - fixed {int(time.time() - last_fix)}s ago")
                        continue
                    
                    # Get position data
                    entry_price = float(position.get('entryPrice', 0))
                    side_str = position.get('side', '').lower()
                    position_info = position.get('info', {})
                    position_idx = position_info.get('positionIdx', 0)
                    
                    # Convert position_idx to int
                    try:
                        position_idx = int(position_idx)
                    except:
                        position_idx = 0
                    
                    # Determine side
                    if side_str in ['buy', 'long']:
                        side = 'buy'
                        long_position = True
                    elif side_str in ['sell', 'short']:
                        side = 'sell'
                        long_position = False
                    else:
                        contracts = float(position.get('contracts', 0))
                        if contracts > 0:
                            side = 'buy'
                            long_position = True
                        else:
                            side = 'sell'
                            long_position = False
                    
                    # Get current SL from position field (NOT from orders)
                    current_sl = float(position.get('stopLoss', 0) or 0)
                    
                    if current_sl == 0:
                        # NO STOP LOSS - Critical!
                        logging.warning(colored(
                            f"⚠️ {symbol_short}: NO STOP LOSS! Setting SL with VERIFICATION...",
                            "red", attrs=['bold']
                        ))
                        
                        # Calculate target SL
                        if long_position:
                            target_sl = entry_price * (1 - STOP_LOSS_PCT)
                        else:
                            target_sl = entry_price * (1 + STOP_LOSS_PCT)
                        
                        # DEBUG: Log full position info BEFORE
                        logging.warning(colored(
                            f"🔍 DEBUG PRE-SET: {symbol_short}\n"
                            f"   position_idx={position_idx}, side={side}, long={long_position}\n"
                            f"   target_sl=${target_sl:.6f}, entry=${entry_price:.6f}",
                            "yellow"
                        ))
                        
                        # Use set_trading_stop (NOT stop_market orders!)
                        result = await global_order_manager.set_trading_stop(
                            exchange, symbol,
                            stop_loss=target_sl,
                            take_profit=None,
                            position_idx=position_idx,
                            side=side
                        )
                        
                        logging.warning(colored(
                            f"🔍 DEBUG POST-SET: {symbol_short}\n"
                            f"   result.success={result.success}\n"
                            f"   result.order_id={result.order_id}\n"
                            f"   result.error={result.error}",
                            "yellow"
                        ))
                        
                        if result.success:
                            # CRITICAL: Verify SL was actually set
                            await asyncio.sleep(3)  # Wait 3s instead of 2s
                            
                            # Re-fetch position to verify
                            verify_positions = await exchange.fetch_positions([symbol])
                            verified = False
                            for vpos in verify_positions:
                                if vpos.get('symbol') == symbol and float(vpos.get('contracts', 0)) != 0:
                                    # CRITICAL FIX: Read stopLoss from 'info' dict, not from top-level
                                    vpos_info = vpos.get('info', {})
                                    sl_string = vpos_info.get('stopLoss', '0')
                                    
                                    # Parse SL (handle both string and float)
                                    try:
                                        if isinstance(sl_string, str):
                                            verified_sl = float(sl_string) if sl_string else 0.0
                                        else:
                                            verified_sl = float(sl_string) if sl_string else 0.0
                                    except:
                                        verified_sl = 0.0
                                    
                                    # DEBUG: Log full position after set
                                    logging.warning(colored(
                                        f"🔍 DEBUG VERIFY: {symbol_short}\n"
                                        f"   verified_sl={verified_sl}\n"
                                        f"   positionIdx={vpos_info.get('positionIdx')}\n"
                                        f"   stopLoss_raw={vpos_info.get('stopLoss')}\n"
                                        f"   side={vpos.get('side')}",
                                        "cyan"
                                    ))
                                    
                                    if verified_sl > 0:
                                        verified = True
                                        logging.info(colored(
                                            f"✅ {symbol_short}: SL VERIFIED @ ${verified_sl:.6f}",
                                            "green", attrs=['bold']
                                        ))
                                        
                                        # Update tracked position
                                        with self.core.get_lock():
                                            for pos in self.core._get_open_positions_unsafe().values():
                                                if pos.symbol == symbol and pos.status == "OPEN":
                                                    pos.real_stop_loss = verified_sl
                                                    pos.stop_loss = verified_sl
                                                    break
                                        
                                        # Mark as fixed
                                        self._last_fix_time[symbol] = time.time()
                                        fixed_count += 1
                                        break
                            
                            if not verified:
                                logging.error(colored(
                                    f"❌ {symbol_short}: SL NOT VERIFIED after set! Check position_idx={position_idx}",
                                    "red", attrs=['bold']
                                ))
                        else:
                            logging.error(colored(
                                f"❌ {symbol_short}: SL SET FAILED - {result.error}",
                                "red"
                            ))
                        continue
                    
                    # Check if SL is correct (with tolerance)
                    if long_position:
                        expected_sl = entry_price * (1 - STOP_LOSS_PCT)
                        current_sl_pct = (current_sl - entry_price) / entry_price
                        expected_sl_pct = -STOP_LOSS_PCT
                    else:
                        expected_sl = entry_price * (1 + STOP_LOSS_PCT)
                        current_sl_pct = (current_sl - entry_price) / entry_price
                        expected_sl_pct = +STOP_LOSS_PCT
                    
                    sl_deviation = abs(current_sl_pct - expected_sl_pct)
                    
                    if sl_deviation > TOLERANCE_PCT:
                        # SL INCORRECT - Fix it with verification
                        logging.warning(colored(
                            f"⚠️ {symbol_short}: INCORRECT SL!\n"
                            f"   Current: ${current_sl:.6f} ({current_sl_pct*100:+.2f}%)\n"
                            f"   Expected: ${expected_sl:.6f} ({expected_sl_pct*100:+.2f}%)",
                            "yellow", attrs=['bold']
                        ))
                        
                        result = await global_order_manager.set_trading_stop(
                            exchange, symbol,
                            stop_loss=expected_sl,
                            take_profit=None,
                            position_idx=position_idx,
                            side=side
                        )
                        
                        if result.success:
                            # Verify correction
                            await asyncio.sleep(2)
                            verify_positions = await exchange.fetch_positions([symbol])
                            for vpos in verify_positions:
                                if vpos.get('symbol') == symbol and float(vpos.get('contracts', 0)) != 0:
                                    new_sl = float(vpos.get('stopLoss', 0) or 0)
                                    if new_sl > 0:
                                        new_sl_pct = (new_sl - entry_price) / entry_price
                                        logging.info(colored(
                                            f"✅ {symbol_short}: SL CORRECTED & VERIFIED!\n"
                                            f"   ${current_sl:.6f} ({current_sl_pct*100:+.2f}%) → "
                                            f"${new_sl:.6f} ({new_sl_pct*100:+.2f}%)",
                                            "green"
                                        ))
                                        self._last_fix_time[symbol] = time.time()
                                        fixed_count += 1
                                        break
                
                except Exception as pos_error:
                    logging.error(f"Error checking SL for {position.get('symbol')}: {pos_error}")
                    continue
            
            if fixed_count > 0:
                logging.info(colored(f"🔧 AUTO-FIX: Corrected {fixed_count} stop losses", "green", attrs=['bold']))
            
            return fixed_count
            
        except Exception as e:
            logging.error(f"SL auto-fix system error: {e}")
            return 0
    
    async def check_and_close_unsafe_positions(self, exchange) -> int:
        """
        Check and close positions that are too small or unsafe
        
        CRITICAL FIX: Safe access to all position fields with None handling
        
        Returns:
            int: Number of positions closed
        """
        MIN_POSITION_USD = 100.0
        MIN_IM_USD = 10.0
        closed_count = 0
        
        try:
            # Get real positions from Bybit
            bybit_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            
            # Safe filtering: handle None values in contracts
            active_positions = []
            for p in bybit_positions:
                contracts_raw = p.get('contracts', 0)
                try:
                    contracts_float = float(contracts_raw) if contracts_raw else 0
                    if contracts_float != 0:
                        active_positions.append(p)
                except (ValueError, TypeError):
                    continue
            
            for position in active_positions:
                try:
                    symbol = position.get('symbol')
                    
                    # CRITICAL FIX: Safe access with None handling
                    contracts_raw = position.get('contracts', 0)
                    entry_raw = position.get('entryPrice', 0)
                    leverage_raw = position.get('leverage', 10)
                    
                    # Safe float conversion
                    try:
                        contracts = abs(float(contracts_raw) if contracts_raw else 0)
                        entry_price = float(entry_raw) if entry_raw else 0
                        leverage = float(leverage_raw) if leverage_raw else 10
                    except (ValueError, TypeError) as e:
                        logging.warning(f"⚠️ {symbol}: Invalid position data (contracts={contracts_raw}, entry={entry_raw}) - skipping safety check")
                        continue
                    
                    # Skip if any critical value is zero/invalid
                    if contracts == 0 or entry_price == 0 or leverage == 0:
                        continue
                    
                    # Calculate metrics
                    position_usd = contracts * entry_price
                    initial_margin = position_usd / leverage
                    
                    # Check if unsafe
                    if position_usd < MIN_POSITION_USD or initial_margin < MIN_IM_USD:
                        symbol_short = symbol.replace('/USDT:USDT', '')
                        
                        logging.warning(colored(
                            f"⚠️ UNSAFE POSITION: {symbol_short} "
                            f"(${position_usd:.2f} notional, ${initial_margin:.2f} IM)",
                            "red", attrs=['bold']
                        ))
                        
                        # Close position
                        side = 'sell' if contracts > 0 else 'buy'
                        close_size = abs(contracts)
                        
                        if side == 'sell':
                            order = await exchange.create_market_sell_order(symbol, close_size)
                        else:
                            order = await exchange.create_market_buy_order(symbol, close_size)
                        
                        if order and order.get('id'):
                            logging.info(f"✅ Unsafe position closed: {symbol} | Order: {order['id']}")
                            
                            exit_price = float(order.get('average', 0) or order.get('price', 0))
                            
                            # Update tracked position
                            if self.core.safe_has_position_for_symbol(symbol) and exit_price > 0:
                                for pos_id, pos in list(self.core._get_open_positions_unsafe().items()):
                                    if pos.symbol == symbol:
                                        self.core.close_position(pos_id, exit_price, "SAFETY_CLOSURE")
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
                logging.info(colored(f"🛡️ SAFETY: Closed {closed_count} unsafe positions", "cyan"))
            
            return closed_count
            
        except Exception as e:
            logging.error(f"Position safety check error: {e}")
            return 0
