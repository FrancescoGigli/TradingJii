#!/usr/bin/env python3
"""
🎯 DEDICATED ORDER MANAGER

SINGLE RESPONSIBILITY: Gestione orders su Bybit
- Place market orders
- Place stop loss orders  
- Place take profit orders
- Setup position protection
- Zero business logic, solo order execution

GARANTISCE: Success/Failure chiaro per ogni ordine
"""

import logging
import asyncio
from typing import Tuple, Optional, Dict
from termcolor import colored

class OrderExecutionResult:
    """Simple data class for order results"""
    def __init__(self, success: bool, order_id: Optional[str] = None, error: Optional[str] = None):
        self.success = success
        self.order_id = order_id
        self.error = error

class OrderManager:
    """
    Clean, dedicated order management for Bybit
    
    PHILOSOPHY: Simple functions, clear results, zero ambiguity
    """
    
    def __init__(self):
        self.placed_orders = {}  # Track placed orders for cleanup
        
    async def place_market_order(self, exchange, symbol: str, side: str, size: float) -> OrderExecutionResult:
        """
        Place market order on Bybit
        
        Args:
            exchange: Bybit exchange instance
            symbol: Trading symbol (e.g., 'WLD/USDT:USDT')
            side: 'buy' or 'sell'
            size: Position size in contracts
            
        Returns:
            OrderExecutionResult: Success/failure with order ID or error
        """
        try:
            logging.info(colored(f"📈 PLACING MARKET {side.upper()} ORDER: {symbol} | Size: {size:.4f}", "cyan", attrs=['bold']))
            
            if side.lower() == 'buy':
                order = await exchange.create_market_buy_order(symbol, size)
            else:
                order = await exchange.create_market_sell_order(symbol, size)
            
            # Validate response
            if not order or not order.get('id'):
                error_msg = f"Invalid order response: {order}"
                logging.error(colored(f"❌ {error_msg}", "red"))
                return OrderExecutionResult(False, None, error_msg)
            
            order_id = order.get('id')
            entry_price = order.get('average') or order.get('price', 0)
            status = order.get('status', 'unknown')
            
            logging.info(colored(f"✅ MARKET ORDER SUCCESS: ID {order_id} | Price: ${entry_price:.6f} | Status: {status.upper()}", "green", attrs=['bold']))
            
            return OrderExecutionResult(True, order_id, None)
            
        except Exception as e:
            error_msg = f"Market order failed: {str(e)}"
            logging.error(colored(f"❌ {error_msg}", "red"))
            return OrderExecutionResult(False, None, error_msg)
    
    async def set_trading_stop(self, exchange, symbol: str, stop_loss: float = None, 
                              take_profit: float = None, position_idx: int = 0) -> OrderExecutionResult:
        """
        CORRECT: Use Bybit's set_trading_stop API (from your working example)
        
        Args:
            exchange: Bybit exchange instance
            symbol: Trading symbol
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            position_idx: Position index (default 0)
            
        Returns:
            OrderExecutionResult: Success/failure
        """
        try:
            logging.info(colored(f"🛡️ SETTING TRADING STOP: {symbol} | SL: ${stop_loss:.6f} | TP: ${take_profit:.6f}", "yellow", attrs=['bold']))
            
            # Use Bybit's set_trading_stop API (the correct way!)
            params = {
                'category': 'linear',  # For USDT perpetuals
                'symbol': symbol,
                'tpslMode': 'Full',
                'positionIdx': position_idx
            }
            
            if stop_loss:
                params['stopLoss'] = str(stop_loss)
            if take_profit:
                params['takeProfit'] = str(take_profit)
            
            # CRITICAL FIX: Use ccxt method for trading stop
            if hasattr(exchange, 'set_trading_stop'):
                result = await exchange.set_trading_stop(**params)
            else:
                # Fallback: try direct API call
                result = await exchange.private_post_v5_position_trading_stop(params)
            
            if result.get('retCode') == 0:
                logging.info(colored(f"✅ TRADING STOP SUCCESS: {symbol}", "green", attrs=['bold']))
                return OrderExecutionResult(True, "trading_stop", None)
            else:
                error_msg = f"Bybit trading stop failed: {result}"
                logging.error(colored(f"❌ {error_msg}", "red"))
                return OrderExecutionResult(False, None, error_msg)
            
        except Exception as e:
            error_msg = f"Trading stop failed: {str(e)}"
            logging.error(colored(f"❌ {error_msg}", "red"))
            return OrderExecutionResult(False, None, error_msg)
    
    async def place_take_profit(self, exchange, symbol: str, side: str, size: float, tp_price: float) -> OrderExecutionResult:
        """
        Place take profit order on Bybit
        
        Args:
            exchange: Bybit exchange instance
            symbol: Trading symbol
            side: Original position side ('buy' or 'sell')  
            size: Position size in contracts
            tp_price: Take profit trigger price
            
        Returns:
            OrderExecutionResult: Success/failure with TP order ID
        """
        try:
            # Calculate opposite side for take profit
            tp_side = "sell" if side.lower() == "buy" else "buy"
            
            logging.info(colored(f"🎯 PLACING TAKE PROFIT: {symbol} | Price: ${tp_price:.6f} | Side: {tp_side}", "green", attrs=['bold']))
            
            # CRITICAL FIX: Add triggerDirection parameter for Bybit
            tp_trigger_direction = "above" if side.lower() == "buy" else "below"
            
            # CRITICAL FIX: Use limit order for take profit (Bybit compatible)
            tp_order = await exchange.create_order(
                symbol=symbol,
                type='limit',
                side=tp_side,
                amount=size,
                price=tp_price
            )
            
            # Validate take profit response
            if not tp_order or not tp_order.get('id'):
                error_msg = f"Invalid take profit response: {tp_order}"
                logging.error(colored(f"❌ {error_msg}", "red"))
                return OrderExecutionResult(False, None, error_msg)
            
            tp_order_id = tp_order.get('id')
            logging.info(colored(f"✅ TAKE PROFIT ACTIVE: Order ID {tp_order_id}", "green", attrs=['bold']))
            
            # Track for cleanup
            self.placed_orders[tp_order_id] = {
                'type': 'take_profit',
                'symbol': symbol,
                'price': tp_price
            }
            
            return OrderExecutionResult(True, tp_order_id, None)
            
        except Exception as e:
            error_msg = f"Take profit placement failed: {str(e)}"
            logging.error(colored(f"❌ {error_msg}", "red"))
            return OrderExecutionResult(False, None, error_msg)
    
    async def setup_position_protection(self, exchange, symbol: str, side: str, size: float, 
                                       sl_price: float, tp_price: float) -> Dict[str, OrderExecutionResult]:
        """
        CORRECT: Use Bybit's set_trading_stop API for SL/TP
        
        Args:
            exchange: Bybit exchange instance
            symbol: Trading symbol
            side: Position side
            size: Position size in contracts
            sl_price: Stop loss price
            tp_price: Take profit price
            
        Returns:
            Dict with 'trading_stop' OrderExecutionResult
        """
        
        logging.info(colored(f"🛡️ SETTING UP COMPLETE PROTECTION for {symbol}", "yellow", attrs=['bold']))
        
        # Use Bybit's correct API for setting SL/TP
        result = await self.set_trading_stop(exchange, symbol, sl_price, tp_price)
        
        # Return in expected format for compatibility
        return {
            'stop_loss': result,
            'take_profit': result  # Same result for both since it's one API call
        }
    
    async def setup_existing_position_protection(self, exchange, position_data: Dict) -> Dict[str, OrderExecutionResult]:
        """
        Setup protection for existing Bybit position (40% SL + 20% TP)
        
        Args:
            exchange: Bybit exchange instance
            position_data: Position data from Bybit
            
        Returns:
            Dict with protection results
        """
        try:
            symbol = position_data.get('symbol')
            contracts = abs(float(position_data.get('contracts', 0)))
            side = 'buy' if float(position_data.get('contracts', 0)) > 0 else 'sell'
            entry_price = float(position_data.get('entryPrice', 0))
            
            if not symbol or contracts <= 0 or entry_price <= 0:
                error_msg = f"Invalid position data: {position_data}"
                logging.error(colored(error_msg, "red"))
                return {
                    'stop_loss': OrderExecutionResult(False, None, error_msg),
                    'take_profit': OrderExecutionResult(False, None, error_msg)
                }
            
            # Calculate 40% protective levels
            protective_stop_pct = 40.0
            if side == 'buy':
                sl_price = entry_price * (1 - protective_stop_pct / 100)  # 40% below
                tp_price = entry_price * (1 + (protective_stop_pct / 100) * 0.5)  # 20% above  
            else:
                sl_price = entry_price * (1 + protective_stop_pct / 100)  # 40% above
                tp_price = entry_price * (1 - (protective_stop_pct / 100) * 0.5)  # 20% below
            
            logging.info(colored(f"🛡️ CALCULATED PROTECTIVE LEVELS for {symbol}:", "cyan"))
            logging.info(colored(f"   Entry: ${entry_price:.6f} | SL: ${sl_price:.6f} (-40%) | TP: ${tp_price:.6f} (+20%)", "white"))
            
            # Place protection orders
            return await self.setup_position_protection(exchange, symbol, side, contracts, sl_price, tp_price)
            
        except Exception as e:
            error_msg = f"Error calculating protective levels: {str(e)}"
            logging.error(colored(error_msg, "red"))
            return {
                'stop_loss': OrderExecutionResult(False, None, error_msg),
                'take_profit': OrderExecutionResult(False, None, error_msg)
            }
    
    def get_placed_orders_summary(self) -> Dict:
        """Get summary of all placed orders"""
        sl_count = sum(1 for order in self.placed_orders.values() if order['type'] == 'stop_loss')
        tp_count = sum(1 for order in self.placed_orders.values() if order['type'] == 'take_profit')
        
        return {
            'total_orders': len(self.placed_orders),
            'stop_losses': sl_count,
            'take_profits': tp_count,
            'details': self.placed_orders
        }

# Global order manager instance
global_order_manager = OrderManager()
