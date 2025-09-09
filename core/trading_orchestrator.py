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
from core.position_manager import global_position_manager, Position

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
        self.position_manager = global_position_manager
        
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
            
            # 1. Check if position already exists for symbol
            if self.position_manager.has_position_for_symbol(symbol):
                error = f"Position already exists for {symbol} (max 1 per symbol)"
                logging.warning(colored(f"⚠️ {error}", "yellow"))
                return TradingResult(False, "", error)
            
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
            
            # 6. Create position in tracker
            position_id = self.position_manager.create_position(
                symbol=symbol,
                side=side,
                entry_price=market_data.price,
                position_size=levels.position_size * market_data.price,  # Convert to USD
                stop_loss=levels.stop_loss,
                take_profit=levels.take_profit,
                leverage=10,
                confidence=confidence
            )
            
            # 7. Setup protection orders
            protection_results = await self.order_manager.setup_position_protection(
                exchange, symbol, side, levels.position_size, levels.stop_loss, levels.take_profit
            )
            
            # 8. Update position with order IDs
            sl_id = protection_results['stop_loss'].order_id
            tp_id = protection_results['take_profit'].order_id
            
            self.position_manager.update_position_orders(position_id, sl_id, tp_id)
            
            # 9. Return comprehensive result
            order_ids = {
                'main': market_result.order_id,
                'stop_loss': sl_id,
                'take_profit': tp_id
            }
            
            logging.info(colored(f"✅ TRADE COMPLETE: {symbol} | Position: {position_id}", "green", attrs=['bold']))
            
            return TradingResult(True, position_id, "", order_ids)
            
        except Exception as e:
            error_msg = f"Trade execution failed: {str(e)}"
            logging.error(colored(f"❌ {error_msg}", "red"))
            return TradingResult(False, "", error_msg)
    
    async def protect_existing_positions(self, exchange) -> Dict[str, TradingResult]:
        """
        SIMPLIFIED: Track existing positions without placing orders
        
        Bybit ha regole complesse per ordini su posizioni esistenti.
        Meglio solo tracking software per trailing stops.
        
        Args:
            exchange: Bybit exchange instance
            
        Returns:
            Dict[str, TradingResult]: Results for each position
        """
        results = {}
        
        try:
            logging.info(colored("🛡️ TRACKING EXISTING POSITIONS (Software Only)", "yellow", attrs=['bold']))
            
            # Fetch current positions from Bybit
            positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_positions = [p for p in positions if float(p.get('contracts', 0)) > 0]
            
            if not active_positions:
                logging.info(colored("✅ No existing positions found", "green"))
                return results
            
            # Process each position for SOFTWARE tracking only
            for pos_data in active_positions:
                try:
                    symbol = pos_data.get('symbol')
                    contracts = abs(float(pos_data.get('contracts', 0)))
                    side = 'buy' if float(pos_data.get('contracts', 0)) > 0 else 'sell'
                    entry_price = float(pos_data.get('entryPrice', 0))
                    
                    if not symbol or contracts <= 0:
                        continue
                    
                    # Add to position manager for software tracking
                    position_id = self.position_manager.create_position(
                        symbol=symbol,
                        side=side,
                        entry_price=entry_price,
                        position_size=contracts * entry_price,  # USD value
                        stop_loss=entry_price * (0.6 if side == 'buy' else 1.4),  # 40% SL (software tracking)
                        take_profit=entry_price * (1.2 if side == 'buy' else 0.8),  # 20% TP (software tracking)
                        leverage=10,
                        confidence=0.7
                    )
                    
                    logging.info(colored(f"📊 Tracking: {symbol} {side.upper()} @ ${entry_price:.6f} (Software trailing only)", "cyan"))
                    
                    # Mark as success (software tracking)
                    results[symbol] = TradingResult(True, position_id, "", {
                        'tracking_type': 'software_only',
                        'note': 'Existing position - software trailing stop only'
                    })
                    
                except Exception as pos_error:
                    error_msg = f"Position tracking failed: {str(pos_error)}"
                    logging.error(colored(f"❌ {error_msg}", "red"))
                    results[pos_data.get('symbol', 'unknown')] = TradingResult(False, "", error_msg)
            
            # Summary
            tracked = len(results)
            logging.info(colored(f"📊 TRACKING SUMMARY: {tracked} positions under software management", "cyan"))
            
            return results
            
        except Exception as e:
            error_msg = f"Error tracking existing positions: {str(e)}"
            logging.error(colored(f"❌ {error_msg}", "red"))
            return {'error': TradingResult(False, "", error_msg)}
    
    async def update_positions_with_current_prices(self, exchange, symbols: List[str]) -> List[Position]:
        """
        Update all positions with current market prices
        
        Args:
            exchange: Exchange instance
            symbols: List of symbols to get prices for
            
        Returns:
            List[Position]: Positions that hit TP/SL and should be closed
        """
        try:
            # Fetch current prices
            current_prices = {}
            for symbol in symbols:
                try:
                    ticker = await exchange.fetch_ticker(symbol)
                    current_prices[symbol] = ticker.get('last', 0)
                except Exception as price_error:
                    logging.debug(f"Could not get price for {symbol}: {price_error}")
                    continue
            
            # Update positions
            positions_to_close = self.position_manager.update_prices(current_prices)
            
            if positions_to_close:
                logging.info(colored(f"🎯 {len(positions_to_close)} positions hit TP/SL", "yellow"))
                for pos in positions_to_close:
                    logging.info(colored(f"   🔒 {pos.symbol} {pos.status}: {pos.unrealized_pnl_pct:+.2f}%", "cyan"))
            
            return positions_to_close
            
        except Exception as e:
            logging.error(f"Error updating positions: {e}")
            return []
    
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
            # 1. Check symbol uniqueness
            if self.position_manager.has_position_for_symbol(symbol):
                return False, f"Position already exists for {symbol}"
            
            # 2. Check position count limit
            if self.position_manager.get_position_count() >= 3:
                return False, "Maximum 3 positions reached"
            
            # 3. Check available balance
            if self.position_manager.get_available_balance() < 20.0:  # Min margin
                return False, "Insufficient available balance"
            
            return True, "Position can be opened"
            
        except Exception as e:
            return False, f"Validation error: {e}"

# Global trading orchestrator instance
global_trading_orchestrator = TradingOrchestrator()
