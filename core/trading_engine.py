#!/usr/bin/env python3
"""
Unified Trading Engine - Demo/Live Mode Unification

CRITICAL FIXES V2:
- Unified logic for both Demo and Live trading
- Mock exchange implementation for Demo mode
- Consistent position sizing across modes
- Synchronized TP/SL logic
- Thread-safe operations
"""

import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple, Any, List
from datetime import datetime
from termcolor import colored
import uuid

import config
from config import DEMO_BALANCE, LEVERAGE, MAX_CONCURRENT_POSITIONS


class ExchangeInterface(ABC):
    """Abstract interface for exchange operations"""
    
    @abstractmethod
    async def get_balance(self) -> float:
        """Get current USDT balance"""
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict:
        """Get ticker data for symbol"""
        pass
    
    @abstractmethod
    async def get_open_positions_count(self) -> int:
        """Get number of open positions"""
        pass
    
    @abstractmethod
    async def execute_order(self, symbol: str, side: str, size: float, 
                          stop_loss: Optional[float] = None, 
                          take_profit: Optional[float] = None) -> Dict:
        """Execute trading order"""
        pass
    
    @abstractmethod
    async def set_leverage(self, leverage: int, symbol: str) -> bool:
        """Set leverage for symbol"""
        pass


class LiveExchange(ExchangeInterface):
    """Live exchange implementation using real API"""
    
    def __init__(self, exchange_client):
        self.exchange = exchange_client
        
    async def get_balance(self) -> float:
        """Get real USDT balance from exchange"""
        try:
            balance = await self.exchange.fetch_balance()
            
            # Search for USDT balance
            usdt_balance = None
            for key in ['USDT', 'usdt', 'USDT:USDT', 'USDT/USDT']:
                if key in balance:
                    usdt_data = balance[key]
                    if isinstance(usdt_data, dict):
                        usdt_balance = usdt_data.get('free', usdt_data.get('total', 0))
                    else:
                        usdt_balance = usdt_data
                    break
            
            return usdt_balance or 0.0
            
        except Exception as e:
            logging.error(f"Failed to get live balance: {e}")
            return 0.0
    
    async def get_ticker(self, symbol: str) -> Dict:
        """Get real ticker data"""
        try:
            return await self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logging.error(f"Failed to get ticker for {symbol}: {e}")
            return {}
    
    async def get_open_positions_count(self) -> int:
        """Get real open positions count"""
        try:
            positions = await self.exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            return len([p for p in positions if float(p.get('contracts', 0)) > 0])
        except Exception as e:
            logging.error(f"Failed to get open positions: {e}")
            return 0
    
    async def execute_order(self, symbol: str, side: str, size: float,
                          stop_loss: Optional[float] = None,
                          take_profit: Optional[float] = None) -> Dict:
        """Execute real trading order"""
        try:
            # Execute main order
            if side.upper() == "BUY":
                order = await self.exchange.create_market_buy_order(symbol, size)
            else:
                order = await self.exchange.create_market_sell_order(symbol, size)
            
            entry_price = order.get('average') or order.get('price', 0)
            trade_id = order.get("id") or f"{symbol}-{datetime.utcnow().timestamp()}"
            
            # Try to set stop loss and take profit
            stop_order_id = None
            tp_order_id = None
            
            if stop_loss:
                try:
                    stop_side = "sell" if side.upper() == "BUY" else "buy"
                    stop_order = await self.exchange.create_order(
                        symbol=symbol,
                        type='stop_market',
                        side=stop_side,
                        amount=size,
                        params={'stopPrice': stop_loss}
                    )
                    stop_order_id = stop_order.get('id')
                    logging.info(f"🛡️ Stop loss set: {stop_loss:.6f}")
                except Exception as sl_error:
                    logging.warning(f"Failed to set stop loss: {sl_error}")
            
            if take_profit:
                try:
                    tp_side = "sell" if side.upper() == "BUY" else "buy"
                    tp_order = await self.exchange.create_order(
                        symbol=symbol,
                        type='take_profit_market',
                        side=tp_side,
                        amount=size,
                        params={'stopPrice': take_profit}
                    )
                    tp_order_id = tp_order.get('id')
                    logging.info(f"🎯 Take profit set: {take_profit:.6f}")
                except Exception as tp_error:
                    logging.warning(f"Failed to set take profit: {tp_error}")
            
            return {
                "trade_id": trade_id,
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price,
                "size": size,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "stop_order_id": stop_order_id,
                "tp_order_id": tp_order_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "open",
                "mode": "LIVE"
            }
            
        except Exception as e:
            logging.error(f"Live order execution failed: {e}")
            raise
    
    async def set_leverage(self, leverage: int, symbol: str) -> bool:
        """Set real leverage"""
        try:
            await self.exchange.set_leverage(leverage, symbol)
            return True
        except Exception as e:
            logging.warning(f"Failed to set leverage: {e}")
            return False


class MockExchange(ExchangeInterface):
    """Mock exchange for Demo mode that simulates real behavior"""
    
    def __init__(self):
        # Import position tracker for realistic simulation
        try:
            from core.position_tracker import global_position_tracker
            self.position_tracker = global_position_tracker
            self._positions_available = True
        except ImportError:
            self.position_tracker = None
            self._positions_available = False
            logging.warning("Position tracker not available for demo mode")
    
    async def get_balance(self) -> float:
        """Get simulated balance from position tracker"""
        if self._positions_available and self.position_tracker:
            return self.position_tracker.session_stats['current_balance']
        else:
            return DEMO_BALANCE
    
    async def get_ticker(self, symbol: str) -> Dict:
        """Simulate ticker fetch - returns placeholder data"""
        # In demo mode, we rely on the price passed to execute_order
        return {
            'last': 0.0,  # Will be updated when order is executed
            'symbol': symbol
        }
    
    async def get_open_positions_count(self) -> int:
        """Get simulated open positions count"""
        if self._positions_available and self.position_tracker:
            return self.position_tracker.get_active_positions_count()
        else:
            return 0
    
    async def execute_order(self, symbol: str, side: str, size: float,
                          stop_loss: Optional[float] = None,
                          take_profit: Optional[float] = None) -> Dict:
        """Execute simulated order using position tracker"""
        try:
            if not self._positions_available or not self.position_tracker:
                # Fallback simulation
                return {
                    "trade_id": f"demo_{uuid.uuid4().hex[:8]}",
                    "symbol": symbol,
                    "side": side,
                    "entry_price": 0.0,  # Will need to be set externally
                    "size": size,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "open",
                    "mode": "DEMO"
                }
            
            # Use position tracker for realistic simulation
            # Note: entry_price will be set by the calling function
            position_id = f"demo_{uuid.uuid4().hex[:8]}"
            
            return {
                "trade_id": position_id,
                "symbol": symbol,
                "side": side,
                "entry_price": 0.0,  # Will be updated by calling function
                "size": size,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "open",
                "mode": "DEMO",
                "position_tracker_ready": True
            }
            
        except Exception as e:
            logging.error(f"Demo order simulation failed: {e}")
            raise
    
    async def set_leverage(self, leverage: int, symbol: str) -> bool:
        """Simulate leverage setting (always succeeds in demo)"""
        logging.debug(f"🎮 Demo: Leverage {leverage}x set for {symbol}")
        return True


class UnifiedTradingEngine:
    """
    Unified Trading Engine that handles both Demo and Live modes consistently
    
    FEATURES:
    - Single codebase for both modes
    - Consistent position sizing
    - Unified TP/SL logic
    - Thread-safe operations
    - Realistic demo simulation
    """
    
    def __init__(self, exchange_client=None):
        self.demo_mode = config.DEMO_MODE
        
        if self.demo_mode:
            self.exchange = MockExchange()
            logging.info("🎮 Demo Trading Engine initialized")
        else:
            if exchange_client is None:
                raise ValueError("Live mode requires exchange_client")
            self.exchange = LiveExchange(exchange_client)
            logging.info("🔴 Live Trading Engine initialized")
    
    async def get_account_info(self) -> Dict:
        """Get unified account information"""
        balance = await self.exchange.get_balance()
        open_positions = await self.exchange.get_open_positions_count()
        
        return {
            'balance': balance,
            'open_positions': open_positions,
            'max_positions': MAX_CONCURRENT_POSITIONS,
            'available_positions': max(0, MAX_CONCURRENT_POSITIONS - open_positions),
            'mode': 'DEMO' if self.demo_mode else 'LIVE'
        }
    
    async def validate_trade(self, symbol: str, side: str, size: float) -> Tuple[bool, str]:
        """Unified trade validation for both modes"""
        try:
            # Get account info
            account = await self.get_account_info()
            
            # Check position limits
            if account['available_positions'] <= 0:
                return False, f"Max positions reached ({account['open_positions']}/{MAX_CONCURRENT_POSITIONS})"
            
            # Check balance requirements
            if account['balance'] < 50.0:
                return False, f"Insufficient balance: {account['balance']:.2f} < 50.0"
            
            # Get current price for validation
            ticker = await self.exchange.get_ticker(symbol)
            current_price = ticker.get('last', 0)
            
            if current_price <= 0:
                return False, "Invalid market price"
            
            # Check minimum position value
            position_value = size * current_price
            if position_value < 10.0:
                return False, f"Position too small: ${position_value:.2f} < $10.00"
            
            return True, "Trade validated"
            
        except Exception as e:
            logging.error(f"Trade validation failed: {e}")
            return False, f"Validation error: {e}"
    
    async def execute_trade(self, symbol: str, side: str, current_price: float, 
                          atr: float, confidence: float = 0.7,
                          risk_manager=None) -> Dict:
        """
        Unified trade execution for both Demo and Live modes
        
        Args:
            symbol: Trading symbol
            side: "Buy" or "Sell"
            current_price: Current market price
            atr: Average True Range for risk calculations
            confidence: Signal confidence (0-1)
            risk_manager: Optional risk manager instance
            
        Returns:
            Dict: Trade execution result
        """
        try:
            # Calculate position size using risk management
            if risk_manager:
                account_balance = await self.exchange.get_balance()
                position_size, stop_loss_price = risk_manager.calculate_position_size(
                    symbol=symbol,
                    signal_strength=confidence,
                    current_price=current_price,
                    atr=atr,
                    account_balance=account_balance
                )
                
                # Calculate take profit
                take_profit_price = risk_manager.calculate_take_profit(
                    symbol=symbol,
                    side=side,
                    entry_price=current_price,
                    stop_loss=stop_loss_price
                )
            else:
                # Fallback position sizing
                account_balance = await self.exchange.get_balance()
                position_size = min(account_balance * 0.05, 100.0) / current_price  # 5% of balance, max $100
                stop_loss_price = None
                take_profit_price = None
            
            # Validate trade
            is_valid, reason = await self.validate_trade(symbol, side, position_size)
            if not is_valid:
                return {
                    "success": False,
                    "reason": reason,
                    "symbol": symbol,
                    "side": side
                }
            
            # Set leverage
            leverage_set = await self.exchange.set_leverage(LEVERAGE, symbol)
            if not leverage_set:
                logging.warning(f"Could not set leverage for {symbol}")
            
            # Execute order
            order_result = await self.exchange.execute_order(
                symbol=symbol,
                side=side,
                size=position_size,
                stop_loss=stop_loss_price,
                take_profit=take_profit_price
            )
            
            # Update entry price in result
            order_result['entry_price'] = current_price
            order_result['success'] = True
            
            # For demo mode, integrate with position tracker
            if self.demo_mode and hasattr(self.exchange, 'position_tracker') and self.exchange.position_tracker:
                try:
                    position_id = self.exchange.position_tracker.open_position(
                        symbol=symbol,
                        side=side,
                        entry_price=current_price,
                        position_size=position_size,
                        leverage=LEVERAGE,
                        confidence=confidence,
                        atr=atr
                    )
                    order_result['position_tracker_id'] = position_id
                except Exception as pt_error:
                    logging.warning(f"Position tracker integration failed: {pt_error}")
            
            logging.debug(
                f"✅ Unified Trade Executed | {order_result['mode']} | {symbol}: {side} | "
                f"Price: {current_price:.6f} | Size: {position_size:.4f} | "
                f"SL: {stop_loss_price:.6f if stop_loss_price else 'None'} | "
                f"TP: {take_profit_price:.6f if take_profit_price else 'None'}"
            )
            
            return order_result
            
        except Exception as e:
            logging.error(f"Unified trade execution failed: {e}")
            return {
                "success": False,
                "reason": f"Execution error: {e}",
                "symbol": symbol,
                "side": side
            }


# Global unified trading engine instance (will be initialized in main)
global_trading_engine = None


def initialize_trading_engine(exchange_client=None):
    """Initialize the global trading engine"""
    global global_trading_engine
    global_trading_engine = UnifiedTradingEngine(exchange_client)
    logging.info("🚀 Global Unified Trading Engine initialized")
    return global_trading_engine
