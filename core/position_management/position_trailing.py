#!/usr/bin/env python3
"""
🎪 TRAILING STOP SYSTEM

Manages dynamic trailing stop losses with ROE-based calculations.
Automatically activates and updates SLs to protect profits.
"""

import logging
import math
from datetime import datetime
from termcolor import colored

from .position_core import PositionCore
from .position_data import TrailingStopData


class PositionTrailing:
    """Handles trailing stop operations"""
    
    def __init__(self, core: PositionCore):
        self.core = core
    
    async def update_trailing_stops(self, exchange) -> int:
        """
        Update trailing stops for all positions
        
        Returns:
            int: Number of positions updated
        """
        from config import (
            TRAILING_ENABLED,
            TRAILING_TRIGGER_PCT,
            TRAILING_SILENT_MODE,
            TRAILING_USE_BATCH_FETCH,
            TRAILING_USE_CACHE,
            TRAILING_DISTANCE_ROE_OPTIMAL,
            TRAILING_DISTANCE_ROE_UPDATE
        )
        
        if not TRAILING_ENABLED:
            return 0
        
        try:
            from core.price_precision_handler import global_price_precision_handler
            from core.order_manager import global_order_manager
            
            active_positions = self.core.safe_get_all_active_positions()
            if not active_positions:
                return 0
            
            # Batch fetch prices
            symbols = [pos.symbol for pos in active_positions]
            
            if TRAILING_USE_BATCH_FETCH and TRAILING_USE_CACHE:
                from core.smart_api_manager import global_smart_api_manager
                tickers_data = await global_smart_api_manager.fetch_multiple_tickers_batch(
                    exchange, symbols
                )
            else:
                tickers_data = {}
                for symbol in symbols:
                    try:
                        ticker = await exchange.fetch_ticker(symbol)
                        tickers_data[symbol] = ticker
                    except Exception as e:
                        logging.debug(f"Ticker fetch failed for {symbol}: {e}")
            
            updates_count = 0
            activations_count = 0
            
            # Process each position
            for position in active_positions:
                try:
                    ticker = tickers_data.get(position.symbol)
                    if not ticker or 'last' not in ticker:
                        continue
                    
                    current_price = float(ticker['last'])
                    symbol_short = position.symbol.replace('/USDT:USDT', '')
                    
                    # Calculate current profit %
                    if position.side in ['buy', 'long']:
                        profit_pct = (current_price - position.entry_price) / position.entry_price
                    else:
                        profit_pct = (position.entry_price - current_price) / position.entry_price
                    
                    # Initialize trailing data if needed
                    if position.trailing_data is None:
                        position.trailing_data = TrailingStopData(trigger_pct=TRAILING_TRIGGER_PCT)
                    
                    trailing = position.trailing_data
                    just_activated = False
                    
                    # Check activation
                    if not trailing.enabled:
                        if profit_pct >= TRAILING_TRIGGER_PCT:
                            # ACTIVATE
                            with self.core.get_lock():
                                if position.position_id in self.core._get_open_positions_unsafe():
                                    pos_ref = self.core._get_open_positions_unsafe()[position.position_id]
                                    if pos_ref.trailing_data is None:
                                        pos_ref.trailing_data = TrailingStopData()
                                    
                                    pos_ref.trailing_data.enabled = True
                                    pos_ref.trailing_data.max_favorable_price = current_price
                                    pos_ref.trailing_data.activation_time = datetime.now().isoformat()
                                    pos_ref.trailing_data.last_update_time = 0
                                    
                                    activations_count += 1
                                    just_activated = True
                                    
                                    logging.info(colored(
                                        f"🎪 TRAILING ACTIVATED: {symbol_short} @ {profit_pct:.2%} profit",
                                        "magenta", attrs=['bold']
                                    ))
                        else:
                            continue
                    
                    # Calculate optimal SL
                    if position.side in ['buy', 'long']:
                        current_roe = ((current_price - position.entry_price) / position.entry_price) * position.leverage * 100
                    else:
                        current_roe = ((position.entry_price - current_price) / position.entry_price) * position.leverage * 100
                    
                    target_roe_optimal = current_roe - (TRAILING_DISTANCE_ROE_OPTIMAL * 100)
                    target_roe_trigger = current_roe - (TRAILING_DISTANCE_ROE_UPDATE * 100)
                    
                    # Convert to price
                    if position.side in ['buy', 'long']:
                        optimal_sl = position.entry_price * (1 + target_roe_optimal / (position.leverage * 100))
                        trigger_threshold = position.entry_price * (1 + target_roe_trigger / (position.leverage * 100))
                    else:
                        optimal_sl = position.entry_price * (1 - target_roe_optimal / (position.leverage * 100))
                        trigger_threshold = position.entry_price * (1 - target_roe_trigger / (position.leverage * 100))
                    
                    # Decide if update needed
                    should_update = False
                    update_reason = ""
                    new_sl = 0.0
                    
                    if just_activated:
                        should_update = True
                        update_reason = "just_activated"
                        new_sl = optimal_sl
                    elif position.stop_loss == 0:
                        should_update = True
                        update_reason = "initial_sl"
                        new_sl = optimal_sl
                    else:
                        if position.side in ['buy', 'long']:
                            if position.stop_loss < trigger_threshold:
                                should_update = True
                                update_reason = "sl_too_far"
                                new_sl = optimal_sl
                        else:
                            if position.stop_loss > trigger_threshold:
                                should_update = True
                                update_reason = "sl_too_far"
                                new_sl = optimal_sl
                    
                    # Safety check
                    if should_update and new_sl > 0 and not just_activated:
                        if position.side in ['buy', 'long']:
                            if new_sl < position.stop_loss and position.stop_loss > 0:
                                should_update = False
                        else:
                            if new_sl > position.stop_loss and position.stop_loss > 0:
                                should_update = False
                    
                    # Normalize to tick size
                    if should_update and new_sl > 0:
                        tick_info = await global_price_precision_handler.get_symbol_precision(
                            exchange, position.symbol
                        )
                        tick_size = float(tick_info.get("tick_size", 0.01))
                        
                        if position.side in ['buy', 'long']:
                            new_sl = math.floor(new_sl / tick_size) * tick_size
                        else:
                            new_sl = math.ceil(new_sl / tick_size) * tick_size
                        
                        if tick_size > 0 and abs(new_sl - position.stop_loss) < tick_size:
                            should_update = False
                    
                    # Apply update
                    if should_update and new_sl > 0:
                        result = await global_order_manager.set_trading_stop(
                            exchange, position.symbol,
                            stop_loss=new_sl,
                            take_profit=None
                        )
                        
                        if result.success:
                            with self.core.get_lock():
                                if position.position_id in self.core._get_open_positions_unsafe():
                                    pos_ref = self.core._get_open_positions_unsafe()[position.position_id]
                                    old_sl = pos_ref.stop_loss
                                    pos_ref.stop_loss = new_sl
                                    
                                    if pos_ref.trailing_data:
                                        pos_ref.trailing_data.current_stop_loss = new_sl
                                        pos_ref.trailing_data.last_update_time = datetime.now().timestamp()
                                    
                                    self.core._save_positions()
                            
                            updates_count += 1
                            
                            distance_pct = abs((new_sl - current_price) / current_price) * 100
                            
                            if position.side in ['buy', 'long']:
                                profit_protected = ((new_sl - position.entry_price) / position.entry_price) * 100
                            else:
                                profit_protected = ((position.entry_price - new_sl) / position.entry_price) * 100
                            
                            logging.info(colored(
                                f"🎪 Trailing updated: {symbol_short} "
                                f"SL ${old_sl:.6f} → ${new_sl:.6f} "
                                f"({update_reason}) | Distance: -{distance_pct:.1f}% | "
                                f"Profit protected: {profit_protected:+.2f}%",
                                "magenta"
                            ))
                
                except Exception as pos_error:
                    logging.error(f"Trailing update error for {position.symbol}: {pos_error}")
                    continue
            
            if updates_count > 0 or activations_count > 0:
                if TRAILING_SILENT_MODE:
                    logging.info(
                        f"[Trailing] {activations_count} activated, "
                        f"{updates_count} updated ({len(active_positions)} total)"
                    )
                else:
                    logging.info(
                        f"🎪 Trailing cycle: {activations_count} activations, "
                        f"{updates_count} updates ({len(active_positions)} positions)"
                    )
            
            return updates_count + activations_count
            
        except Exception as e:
            logging.error(f"Trailing stops update failed: {e}")
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            return 0
