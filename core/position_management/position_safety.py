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
        
        Returns:
            int: Number of SLs fixed
        """
        from config import SL_FIXED_PCT
        from core.price_precision_handler import global_price_precision_handler
        from core.order_manager import global_order_manager
        
        TOLERANCE_PCT = 0.005  # ±0.5% tolerance
        fixed_count = 0
        
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
                    
                    # Get position data
                    entry_price = float(position.get('entryPrice', 0))
                    side_str = position.get('side', '').lower()
                    
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
                    
                    # Get current SL
                    current_sl = float(position.get('stopLoss', 0) or 0)
                    
                    if current_sl == 0:
                        # NO STOP LOSS - Critical!
                        logging.warning(colored(
                            f"⚠️ {symbol_short}: NO STOP LOSS! Setting -5% SL...",
                            "red", attrs=['bold']
                        ))
                        
                        if long_position:
                            target_sl = entry_price * (1 - SL_FIXED_PCT)
                        else:
                            target_sl = entry_price * (1 + SL_FIXED_PCT)
                        
                        normalized_sl, success = await global_price_precision_handler.normalize_stop_loss_price(
                            exchange, symbol, side, entry_price, target_sl
                        )
                        
                        if success:
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
                                            break
                                
                                real_sl_pct = abs((normalized_sl - entry_price) / entry_price) * 100
                                logging.info(colored(
                                    f"✅ {symbol_short}: SL FIXED - ${normalized_sl:.6f} (-{real_sl_pct:.2f}%)",
                                    "green"
                                ))
                                fixed_count += 1
                        continue
                    
                    # Check if SL is correct
                    if long_position:
                        expected_sl = entry_price * (1 - SL_FIXED_PCT)
                        current_sl_pct = (current_sl - entry_price) / entry_price
                        expected_sl_pct = -SL_FIXED_PCT
                    else:
                        expected_sl = entry_price * (1 + SL_FIXED_PCT)
                        current_sl_pct = (current_sl - entry_price) / entry_price
                        expected_sl_pct = +SL_FIXED_PCT
                    
                    sl_deviation = abs(current_sl_pct - expected_sl_pct)
                    
                    if sl_deviation > TOLERANCE_PCT:
                        # SL INCORRECT - Fix it
                        logging.warning(colored(
                            f"⚠️ {symbol_short}: INCORRECT SL!\n"
                            f"   Current: ${current_sl:.6f} ({current_sl_pct*100:+.2f}%)\n"
                            f"   Expected: ${expected_sl:.6f} ({expected_sl_pct*100:+.2f}%)",
                            "yellow", attrs=['bold']
                        ))
                        
                        normalized_sl, success = await global_price_precision_handler.normalize_stop_loss_price(
                            exchange, symbol, side, entry_price, expected_sl
                        )
                        
                        if success:
                            result = await global_order_manager.set_trading_stop(
                                exchange, symbol,
                                stop_loss=normalized_sl,
                                take_profit=None
                            )
                            
                            if result.success:
                                new_sl_pct = (normalized_sl - entry_price) / entry_price
                                logging.info(colored(
                                    f"✅ {symbol_short}: SL CORRECTED!\n"
                                    f"   ${current_sl:.6f} ({current_sl_pct*100:+.2f}%) → "
                                    f"${normalized_sl:.6f} ({new_sl_pct*100:+.2f}%)",
                                    "green"
                                ))
                                fixed_count += 1
                
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
        
        Returns:
            int: Number of positions closed
        """
        MIN_POSITION_USD = 100.0
        MIN_IM_USD = 10.0
        closed_count = 0
        
        try:
            # Get real positions from Bybit
            bybit_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_positions = [p for p in bybit_positions if float(p.get('contracts', 0)) != 0]
            
            for position in active_positions:
                try:
                    symbol = position.get('symbol')
                    contracts = abs(float(position.get('contracts', 0)))
                    entry_price = float(position.get('entryPrice', 0))
                    leverage = float(position.get('leverage', 10))
                    
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
