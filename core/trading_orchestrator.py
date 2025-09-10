#!/usr/bin/env python3
"""
🚀 TRADING ORCHESTRATOR

SINGLE RESPONSIBILITY: Coordinamento trading workflow
- Orchestrate signal execution
- Coordinate risk management  
- Manage position lifecycle
- Handle existing position protection
- Clean error handling and logging

GARANTISCE: Flusso trading semplice e affidabile
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from termcolor import colored

# Import new clean modules
from core.order_manager import global_order_manager, OrderExecutionResult
from core.risk_calculator import global_risk_calculator, MarketData, PositionLevels
from core.smart_position_manager import global_smart_position_manager, Position
from core.trailing_stop_manager import TrailingStopManager

class TradingResult:
    """Simple result for trading operations"""
    def __init__(self, success: bool, position_id: str = "", error: str = "", 
                 order_ids: Dict = None):
        self.success = success
        self.position_id = position_id
        self.error = error
        self.order_ids = order_ids or {}

class TradingOrchestrator:
    """
    Clean trading workflow coordinator
    
    PHILOSOPHY: Simple orchestration, clear results, minimal complexity
    """
    
    def __init__(self):
        self.order_manager = global_order_manager
        self.risk_calculator = global_risk_calculator
        self.position_manager = global_smart_position_manager  # Use consolidated smart position manager
        self.smart_position_manager = global_smart_position_manager  # Keep for sync (same instance)
        
        # Initialize trailing stop manager
        self.trailing_manager = TrailingStopManager(self.order_manager, self.position_manager)
        
    async def execute_new_trade(self, exchange, signal_data: Dict, market_data: MarketData, 
                               balance: float) -> TradingResult:
        """
        Execute complete new trade with protection
        
        Args:
            exchange: Bybit exchange instance
            signal_data: ML signal information
            market_data: Market data for calculations
            balance: Account balance
            
        Returns:
            TradingResult: Complete execution result
        """
        try:
            symbol = signal_data['symbol']
            side = signal_data['signal_name'].lower()  # 'buy' or 'sell'
            confidence = signal_data.get('confidence', 0.7)
            
            logging.info(colored(f"🎯 EXECUTING NEW TRADE: {symbol} {side.upper()}", "cyan", attrs=['bold']))
            
            # 1. ENHANCED: Check if position already exists for symbol (both tracker and real Bybit)
            if self.position_manager.has_position_for_symbol(symbol):
                error = f"Position already exists for {symbol} in tracker"
                logging.warning(colored(f"⚠️ {error}", "yellow"))
                return TradingResult(False, "", error)
            
            # 2. ADDITIONAL: Check Bybit directly for existing positions
            try:
                bybit_positions = await exchange.fetch_positions([symbol])
                for pos in bybit_positions:
                    contracts = float(pos.get('contracts', 0))
                    if abs(contracts) > 0:  # Position exists on Bybit
                        error = f"Position already exists for {symbol} on Bybit ({contracts:+.4f} contracts)"
                        logging.warning(colored(f"⚠️ BYBIT CHECK: {error}", "yellow"))
                        return TradingResult(False, "", error)
            except Exception as bybit_check_error:
                logging.warning(f"Could not verify Bybit positions for {symbol}: {bybit_check_error}")
            
            # 2. Calculate position levels
            levels = self.risk_calculator.calculate_position_levels(
                market_data, side, confidence, balance
            )
            
            # 3. Validate portfolio margin
            existing_margins = [pos.position_size / pos.leverage for pos in self.position_manager.get_active_positions()]
            margin_approved, margin_reason = self.risk_calculator.validate_portfolio_margin(
                existing_margins, levels.margin, balance
            )
            
            if not margin_approved:
                logging.warning(colored(f"⚠️ {margin_reason}", "yellow"))
                return TradingResult(False, "", margin_reason)
            
            # 4. Log calculated levels
            logging.info(colored(f"💰 CALCULATED LEVELS for {symbol}:", "white"))
            logging.info(colored(f"   Margin: ${levels.margin:.2f} | Size: {levels.position_size:.4f} | Notional: ${levels.margin * 10:.2f}", "white"))
            logging.info(colored(f"   SL: ${levels.stop_loss:.6f} (-{levels.risk_pct:.1f}%) | TP: ${levels.take_profit:.6f} (+{levels.reward_pct:.1f}%)", "white"))
            logging.info(colored(f"   Risk:Reward = 1:{levels.risk_reward_ratio:.1f}", "white"))
            
            # 5. Execute main order
            market_result = await self.order_manager.place_market_order(
                exchange, symbol, side, levels.position_size
            )
            
            if not market_result.success:
                return TradingResult(False, "", f"Market order failed: {market_result.error}")
            
            # 6. NEW: Create catastrophic stop on exchange (backup only)
            catastrophic_sl_id = await self.trailing_manager.create_catastrophic_stop(
                exchange, symbol, side, market_data.price
            )
            
            if catastrophic_sl_id is None:
                logging.warning(colored("⚠️ Failed to create catastrophic stop, continuing with internal tracking only", "yellow"))
            
            # 7. Create position with trailing system (NO fixed TP/SL)
            position_id = self.position_manager.create_trailing_position(
                symbol=symbol,
                side=side,
                entry_price=market_data.price,
                position_size=levels.position_size * market_data.price,  # Convert to USD
                atr=market_data.atr,
                catastrophic_sl_id=catastrophic_sl_id,
                leverage=10,
                confidence=confidence
            )
            
            # 8. Return result (no TP/SL orders, only market + catastrophic stop)
            order_ids = {
                'main': market_result.order_id,
                'catastrophic_stop': catastrophic_sl_id,
                'note': 'Trailing system active - no fixed TP/SL'
            }
            
            logging.info(colored(f"✅ TRADE COMPLETE: {symbol} | Position: {position_id}", "green", attrs=['bold']))
            
            return TradingResult(True, position_id, "", order_ids)
            
        except Exception as e:
            error_msg = f"Trade execution failed: {str(e)}"
            logging.error(colored(f"❌ {error_msg}", "red"))
            return TradingResult(False, "", error_msg)
    
    async def protect_existing_positions(self, exchange) -> Dict[str, TradingResult]:
        """
        Display existing Bybit positions and sync with tracking
        
        Args:
            exchange: Bybit exchange instance
            
        Returns:
            Dict[str, TradingResult]: Results for each position
        """
        results = {}
        
        try:
            logging.info(colored("🛡️ BYBIT POSITION SYNC", "yellow", attrs=['bold']))
            
            # 1. Fetch real positions from Bybit
            real_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_positions = [p for p in real_positions if float(p.get('contracts', 0)) > 0]
            
            if not active_positions:
                logging.info(colored("🆕 No existing positions on Bybit - starting fresh", "green"))
                return {}
            
            # 2. ENHANCED DISPLAY WITH PERFECT CELL FORMATTING + LEVERAGE COLUMN
            print(colored("\n🏦 POSIZIONI APERTE SU BYBIT", "cyan", attrs=['bold']))
            print(colored("┌" + "─" * 3 + "┬" + "─" * 8 + "┬" + "─" * 6 + "┬" + "─" * 6 + "┬" + "─" * 12 + "┬" + "─" * 12 + "┬" + "─" * 8 + "┬" + "─" * 10 + "┬" + "─" * 20 + "┬" + "─" * 20 + "┬" + "─" * 10 + "┬" + "─" * 8 + "┐", "cyan"))
            print(colored(f"│{'#':<3}│{'SYMBOL':<8}│{'SIDE':<6}│{'LEV':<6}│{'ENTRY':<12}│{'CURRENT':<12}│{'SIZE':<8}│{'VALUE':<10}│{'STOP LOSS':<20}│{'TAKE PROFIT':<20}│{'PNL $':<10}│{'PNL%':<8}│", "white", attrs=['bold']))
            print(colored("├" + "─" * 3 + "┼" + "─" * 8 + "┼" + "─" * 6 + "┼" + "─" * 6 + "┼" + "─" * 12 + "┼" + "─" * 12 + "┼" + "─" * 8 + "┼" + "─" * 10 + "┼" + "─" * 20 + "┼" + "─" * 20 + "┼" + "─" * 10 + "┼" + "─" * 8 + "┤", "cyan"))
            
            total_value = 0.0
            total_pnl = 0.0
            
            for i, pos in enumerate(active_positions, 1):
                # Clean symbol format: "HYPE/USDT:USDT" → "HYPE"
                symbol_raw = pos.get('symbol', 'N/A')
                symbol = symbol_raw.replace('/USDT:USDT', '').replace('USDT', '')
                
                contracts = float(pos.get('contracts', 0))
                side = 'LONG' if contracts > 0 else 'SHORT'
                entry_price = float(pos.get('entryPrice', 0))
                mark_price = float(pos.get('markPrice', entry_price))
                unrealized_pnl = float(pos.get('unrealizedPnl', 0))
                leverage = float(pos.get('leverage', 10))  # Get real leverage from Bybit
                
                # Calculate position value and PnL percentage
                position_value = abs(contracts) * entry_price
                pnl_pct = (unrealized_pnl / position_value) * 100 if position_value > 0 else 0
                
                # Accumulate totals
                total_value += position_value
                total_pnl += unrealized_pnl
                
                # Get stop loss/take profit info with VALIDATION and CORRECTION
                stop_loss = pos.get('stopLossPrice', None)
                take_profit = pos.get('takeProfitPrice', None)
                
                # VALIDATE and CORRECT stop loss if illogical
                if stop_loss and entry_price > 0:
                    sl_price = float(stop_loss)
                    price_change_pct = ((sl_price - entry_price) / entry_price) * 100
                    
                    # VALIDATION: Check if SL is in wrong direction (CRITICAL FIX!)
                    sl_wrong_direction = False
                    if side == 'LONG' and sl_price > entry_price:  # SL above entry for LONG = WRONG
                        sl_wrong_direction = True
                        logging.warning(colored(f"🚨 INVALID SL for {symbol_raw} LONG: ${sl_price:.4f} > ${entry_price:.4f} (above entry!)", "red"))
                    elif side == 'SHORT' and sl_price < entry_price:  # SL below entry for SHORT = WRONG  
                        sl_wrong_direction = True
                        logging.warning(colored(f"🚨 INVALID SL for {symbol_raw} SHORT: ${sl_price:.4f} < ${entry_price:.4f} (below entry!)", "red"))
                    
                    if sl_wrong_direction:
                        # Calculate CORRECTED stop loss (5% emergency)
                        if side == 'LONG':
                            corrected_sl = entry_price * 0.95  # 5% below for LONG
                        else:
                            corrected_sl = entry_price * 1.05  # 5% above for SHORT
                        
                        corrected_pct = ((corrected_sl - entry_price) / entry_price) * 100
                        sl_text = f"${corrected_sl:.4f} ({corrected_pct:+.1f}%) [CORRECTED]"
                        
                        # Log correction suggestion
                        logging.warning(colored(f"💡 SUGGESTED CORRECTION for {symbol_raw}: ${corrected_sl:.4f} ({corrected_pct:+.1f}%)", "yellow"))
                    else:
                        # Valid SL - show as is
                        sl_text = f"${sl_price:.4f} ({price_change_pct:+.1f}%)"
                else:
                    sl_text = "Not Set"
                
                # TP calculation (no changes needed)
                if take_profit and entry_price > 0:
                    tp_price = float(take_profit)
                    price_change_pct = ((tp_price - entry_price) / entry_price) * 100
                    tp_text = f"${tp_price:.4f} ({price_change_pct:+.1f}%)"
                else:
                    tp_text = "Not Set"
                
                # Format other values
                size_text = f"{abs(contracts):.1f}"
                entry_text = f"${entry_price:.6f}"
                current_text = f"${mark_price:.6f}"
                value_text = f"${position_value:,.0f}"
                pnl_usd_text = f"+{unrealized_pnl:.2f}$" if unrealized_pnl >= 0 else f"{unrealized_pnl:.2f}$"
                pnl_pct_text = f"+{pnl_pct:.2f}%" if pnl_pct >= 0 else f"{pnl_pct:.2f}%"
                
                # Color based on PnL
                pnl_color = "green" if unrealized_pnl > 0 else "red" if unrealized_pnl < 0 else "white"
                side_color = "green" if side == "LONG" else "red"
                
                # PERFECT CELL FORMATTING WITH LEVERAGE COLUMN
                leverage_text = f"{leverage:.0f}x"
                print(colored(f"│{i:<3}│{symbol:<8}│", "white") + 
                      colored(f"{side:<6}", side_color) + colored("│", "white") +
                      colored(f"{leverage_text:<6}", "yellow") + colored("│", "white") +
                      colored(f"{entry_text:<12}│{current_text:<12}│{size_text:<8}│{value_text:<10}│{sl_text:<20}│{tp_text:<20}│", "white") +
                      colored(f"{pnl_usd_text:<10}", pnl_color) + colored("│", "white") +
                      colored(f"{pnl_pct_text:<8}", pnl_color) + colored("│", "white"))
            
            # Total summary row with cells
            total_pnl_pct = (total_pnl / total_value) * 100 if total_value > 0 else 0
            total_pnl_color = "green" if total_pnl > 0 else "red" if total_pnl < 0 else "white"
            
            print(colored("├" + "─" * 3 + "┼" + "─" * 8 + "┼" + "─" * 6 + "┼" + "─" * 6 + "┼" + "─" * 12 + "┼" + "─" * 12 + "┼" + "─" * 8 + "┼" + "─" * 10 + "┼" + "─" * 20 + "┼" + "─" * 20 + "┼" + "─" * 10 + "┼" + "─" * 8 + "┤", "cyan"))
            print(colored(f"│{'TOT':<3}│{'':<8}│{'':<6}│{'':<6}│{'':<12}│{'':<12}│{'':<8}│", "white") +
                  colored(f"${total_value:,.0f}".ljust(10), "white") + colored("│", "white") +
                  colored(f"{'':<20}│{'':<20}│", "white") +
                  colored(f"{total_pnl:+.2f}$".ljust(10), total_pnl_color) + colored("│", "white") +
                  colored(f"{total_pnl_pct:+.2f}%".ljust(8), total_pnl_color) + colored("│", "white"))
            print(colored("└" + "─" * 3 + "┴" + "─" * 8 + "┴" + "─" * 6 + "┴" + "─" * 6 + "┴" + "─" * 12 + "┴" + "─" * 12 + "┴" + "─" * 8 + "┴" + "─" * 10 + "┴" + "─" * 20 + "┴" + "─" * 20 + "┴" + "─" * 10 + "┴" + "─" * 8 + "┘", "cyan"))
            print(colored(f"📊 SUMMARY: {len(active_positions)} positions | Total Value: ${total_value:,.0f} | Total P&L: {total_pnl:+.2f}$ ({total_pnl_pct:+.2f}%)", "green"))
            print()
            
            # 3. Use SMART POSITION MANAGER for sync (FIXED!)
            newly_opened, newly_closed = await self.smart_position_manager.sync_with_bybit(exchange)
            
            # Convert to expected result format
            for position in newly_opened:
                results[position.symbol] = TradingResult(True, position.position_id, "", {
                    'tracking_type': 'smart_sync',
                    'note': 'Position synced via SmartPositionManager'
                })
            
            tracked = len(newly_opened)
            logging.info(colored(f"📊 SMART SYNC COMPLETE: {tracked} positions imported (deduplication active)", "cyan"))
            
            return results
            
        except Exception as e:
            error_msg = f"Error in position sync: {str(e)}"
            logging.error(colored(f"❌ {error_msg}", "red"))
            return {'error': TradingResult(False, "", error_msg)}
    
    async def update_trailing_positions(self, exchange) -> List[Position]:
        """
        NEW: Update all trailing positions and execute exits when hit
        
        Args:
            exchange: Exchange instance
            
        Returns:
            List[Position]: Positions that were closed via trailing
        """
        closed_positions = []
        
        try:
            # Get all positions that need trailing monitoring
            trailing_positions = self.position_manager.get_trailing_positions()
            
            if not trailing_positions:
                return closed_positions
            
            logging.debug(f"🔄 Monitoring {len(trailing_positions)} trailing positions")
            
            # Fetch current prices for all tracked symbols
            current_prices = {}
            for position in trailing_positions:
                try:
                    ticker = await exchange.fetch_ticker(position.symbol)
                    current_prices[position.symbol] = ticker.get('last', 0)
                except Exception as price_error:
                    logging.debug(f"Could not get price for {position.symbol}: {price_error}")
                    continue
            
            # Process each position
            for position in trailing_positions:
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
                
                # Check activation conditions if not already trailing
                if not position.trailing_attivo:
                    if self.trailing_manager.check_activation_conditions(
                        self.trailing_manager.initialize_trailing_data(
                            position.symbol, position.side, position.entry_price, 
                            position.atr_value, position.sl_catastrofico_id
                        ), current_price, position.side
                    ):
                        # Activate trailing
                        self.trailing_manager.activate_trailing(
                            self.trailing_manager.initialize_trailing_data(
                                position.symbol, position.side, position.entry_price,
                                position.atr_value, position.sl_catastrofico_id
                            ), current_price, position.side, position.atr_value
                        )
                        position.trailing_attivo = True
                        position.best_price = current_price
                        position.sl_corrente = current_price - position.atr_value * 2.0 if position.side == 'buy' else current_price + position.atr_value * 2.0
                
                # Update trailing if active
                if position.trailing_attivo and position.sl_corrente is not None:
                    # Update best price (monotone)
                    if position.side == 'buy':
                        new_best = max(position.best_price or current_price, current_price)
                    else:
                        new_best = min(position.best_price or current_price, current_price)
                    
                    if new_best != position.best_price:
                        position.best_price = new_best
                        # Calculate new trailing stop
                        trail_distance = position.atr_value * 2.0
                        
                        if position.side == 'buy':
                            new_sl = new_best - trail_distance
                            position.sl_corrente = max(position.sl_corrente, new_sl)  # Monotone
                        else:
                            new_sl = new_best + trail_distance
                            position.sl_corrente = min(position.sl_corrente, new_sl)  # Monotone
                        
                        logging.debug(f"🔄 Trailing update {position.symbol}: Best ${new_best:.6f} | SL ${position.sl_corrente:.6f}")
                    
                    # Check if trailing hit
                    if position.side == 'buy' and current_price <= position.sl_corrente:
                        # Execute trailing exit
                        exit_success = await self.trailing_manager.execute_trailing_exit(
                            exchange, position.symbol, position.side, 
                            position.position_size / current_price, current_price
                        )
                        
                        if exit_success:
                            position.status = 'CLOSED_TRAILING'
                            closed_positions.append(position)
                            self.position_manager.close_position(position.position_id, current_price, 'TRAILING')
                            
                    elif position.side == 'sell' and current_price >= position.sl_corrente:
                        # Execute trailing exit
                        exit_success = await self.trailing_manager.execute_trailing_exit(
                            exchange, position.symbol, position.side,
                            position.position_size / current_price, current_price
                        )
                        
                        if exit_success:
                            position.status = 'CLOSED_TRAILING'
                            closed_positions.append(position)
                            self.position_manager.close_position(position.position_id, current_price, 'TRAILING')
            
            # Save updated positions
            self.position_manager.save_positions()
            
            if closed_positions:
                logging.info(colored(f"🎯 {len(closed_positions)} positions closed via trailing", "yellow"))
                for pos in closed_positions:
                    logging.info(colored(f"   🔒 {pos.symbol} TRAILING: {pos.unrealized_pnl_pct:+.2f}%", "cyan"))
            
            return closed_positions
            
        except Exception as e:
            logging.error(f"Error updating trailing positions: {e}")
            return closed_positions

    async def update_positions_with_current_prices(self, exchange, symbols: List[str]) -> List[Position]:
        """
        DEPRECATED: Use update_trailing_positions instead
        
        Args:
            exchange: Exchange instance
            symbols: List of symbols to get prices for
            
        Returns:
            List[Position]: Positions that hit TP/SL and should be closed
        """
        # Delegate to new trailing system
        return await self.update_trailing_positions(exchange)
    
    def get_trading_summary(self) -> Dict:
        """Get comprehensive trading summary"""
        try:
            session = self.position_manager.get_session_summary()
            order_summary = self.order_manager.get_placed_orders_summary()
            
            return {
                'positions': {
                    'active_count': session['active_positions'],
                    'used_margin': session['used_margin'],
                    'total_pnl_usd': session['total_pnl_usd'],
                    'available_balance': session['available_balance']
                },
                'orders': {
                    'total_placed': order_summary['total_orders'],
                    'stop_losses': order_summary['stop_losses'],
                    'take_profits': order_summary['take_profits']
                },
                'session': {
                    'balance': session['balance'],
                    'pnl_pct': session['total_pnl_pct']
                }
            }
            
        except Exception as e:
            logging.error(f"Error getting trading summary: {e}")
            return {}
    
    def can_open_new_position(self, symbol: str, balance: float) -> Tuple[bool, str]:
        """
        Check if new position can be opened
        
        Args:
            symbol: Trading symbol
            balance: Account balance
            
        Returns:
            Tuple[bool, str]: (can_open, reason)
        """
        try:
            # Import from config to avoid hardcoding
            from config import MAX_CONCURRENT_POSITIONS
            
            # 1. Check symbol uniqueness
            if self.position_manager.has_position_for_symbol(symbol):
                return False, f"Position already exists for {symbol}"
            
            # 2. Check position count limit (now uses config value)
            current_positions = self.position_manager.get_position_count()
            if current_positions >= MAX_CONCURRENT_POSITIONS:
                return False, f"Maximum {MAX_CONCURRENT_POSITIONS} positions reached (current: {current_positions})"
            
            # 3. Check available balance
            if self.position_manager.get_available_balance() < 20.0:  # Min margin
                return False, "Insufficient available balance"
            
            return True, f"Position can be opened ({current_positions}/{MAX_CONCURRENT_POSITIONS} slots used)"
            
        except Exception as e:
            return False, f"Validation error: {e}"

# Global trading orchestrator instance
global_trading_orchestrator = TradingOrchestrator()
