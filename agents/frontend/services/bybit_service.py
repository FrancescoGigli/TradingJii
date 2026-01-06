"""
📊 Bybit Service - Exchange Operations

Provides:
- get_balance(): Fetch USDT balance
- get_positions(): Fetch open positions
- set_trading_stop(): Set stop loss / take profit
- place_order(): Place market/limit orders (ready for real trading)

Uses CCXT library for Bybit API interactions.
All operations are async-ready but can be used synchronously via wrappers.
"""

import os
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime

try:
    import ccxt
except ImportError:
    ccxt = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BalanceInfo:
    """Container for balance information"""
    total_usdt: float
    available_usdt: float
    used_usdt: float
    timestamp: datetime
    is_real: bool = True  # False if demo/error


@dataclass
class PositionInfo:
    """Container for position information"""
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    leverage: int
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    liquidation_price: Optional[float] = None


@dataclass
class OrderResult:
    """Container for order execution result"""
    success: bool
    order_id: Optional[str]
    symbol: str
    side: str
    amount: float
    price: Optional[float]
    error: Optional[str] = None


class BybitService:
    """
    Service class for Bybit exchange operations.
    
    Usage:
        service = BybitService()
        balance = service.get_balance()
        positions = service.get_positions()
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        """
        Initialize Bybit service.
        
        Args:
            api_key: Bybit API key (defaults to env var)
            api_secret: Bybit API secret (defaults to env var)
        """
        self.api_key = api_key or os.getenv("BYBIT_API_KEY")
        self.api_secret = api_secret or os.getenv("BYBIT_API_SECRET")
        self._exchange = None
        self._initialized = False
        
        # Check if credentials are available
        if not self.api_key or not self.api_secret:
            logger.warning("⚠️ Bybit API credentials not configured")
            self._has_credentials = False
        else:
            self._has_credentials = True
    
    def _get_exchange(self) -> Optional['ccxt.bybit']:
        """Get or create CCXT exchange instance"""
        if ccxt is None:
            logger.error("❌ CCXT library not installed")
            return None
            
        if not self._has_credentials:
            return None
            
        if self._exchange is None:
            try:
                self._exchange = ccxt.bybit({
                    'apiKey': self.api_key,
                    'secret': self.api_secret,
                    'enableRateLimit': True,
                    'options': {
                        'adjustForTimeDifference': True,
                        'recvWindow': 300000,
                    }
                })
                self._initialized = True
                logger.info("✅ Bybit exchange initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Bybit: {e}")
                return None
                
        return self._exchange
    
    @property
    def is_available(self) -> bool:
        """Check if service is available (has credentials)"""
        return self._has_credentials and ccxt is not None
    
    def get_balance(self) -> BalanceInfo:
        """
        Fetch USDT balance from Bybit.
        
        Returns:
            BalanceInfo with balance details
        """
        if not self.is_available:
            return BalanceInfo(
                total_usdt=0.0,
                available_usdt=0.0,
                used_usdt=0.0,
                timestamp=datetime.now(),
                is_real=False
            )
        
        try:
            exchange = self._get_exchange()
            if exchange is None:
                raise Exception("Exchange not initialized")
            
            # ╔════════════════════════════════════════════════════════════════╗
            # ║  BYBIT API CALL: /v5/account/wallet-balance                    ║
            # ║  Fetches wallet balance using BYBIT_API_KEY/SECRET             ║
            # ╚════════════════════════════════════════════════════════════════╝
            balance_data = exchange.fetch_balance()
            
            # Parse balance - try multiple structures
            usdt_total = 0.0
            usdt_free = 0.0
            usdt_used = 0.0
            
            # Structure 1: balance['USDT'] (most common)
            if 'USDT' in balance_data:
                usdt_info = balance_data['USDT']
                if isinstance(usdt_info, dict):
                    usdt_total = float(usdt_info.get('total', 0) or 0)
                    usdt_free = float(usdt_info.get('free', 0) or 0)
                    usdt_used = float(usdt_info.get('used', 0) or 0)
            
            # Structure 2: balance['total']['USDT'] (Unified Trading Account)
            if usdt_total == 0 and 'total' in balance_data:
                if isinstance(balance_data['total'], dict):
                    usdt_total = float(balance_data['total'].get('USDT', 0) or 0)
                    usdt_free = float(balance_data.get('free', {}).get('USDT', 0) or 0)
                    usdt_used = float(balance_data.get('used', {}).get('USDT', 0) or 0)
            
            logger.info(f"💰 Balance fetched: ${usdt_total:.2f} USDT")
            
            return BalanceInfo(
                total_usdt=usdt_total,
                available_usdt=usdt_free,
                used_usdt=usdt_used,
                timestamp=datetime.now(),
                is_real=True
            )
            
        except Exception as e:
            logger.error(f"❌ Error fetching balance: {e}")
            return BalanceInfo(
                total_usdt=0.0,
                available_usdt=0.0,
                used_usdt=0.0,
                timestamp=datetime.now(),
                is_real=False
            )
    
    def get_positions(self) -> List[PositionInfo]:
        """
        Fetch open positions from Bybit.
        
        Returns:
            List of PositionInfo for each open position
        """
        if not self.is_available:
            return []
        
        try:
            exchange = self._get_exchange()
            if exchange is None:
                raise Exception("Exchange not initialized")
            
            # ╔════════════════════════════════════════════════════════════════╗
            # ║  BYBIT API CALL: /v5/position/list                             ║
            # ║  Fetches all open positions                                    ║
            # ╚════════════════════════════════════════════════════════════════╝
            positions_data = exchange.fetch_positions()
            
            positions = []
            for pos in positions_data:
                # Skip empty positions
                contracts = float(pos.get('contracts', 0) or 0)
                if contracts == 0:
                    continue
                
                position = PositionInfo(
                    symbol=pos.get('symbol', ''),
                    side=pos.get('side', '').lower(),
                    size=contracts,
                    entry_price=float(pos.get('entryPrice', 0) or 0),
                    current_price=float(pos.get('markPrice', 0) or 0),
                    unrealized_pnl=float(pos.get('unrealizedPnl', 0) or 0),
                    leverage=int(pos.get('leverage', 1) or 1),
                    stop_loss=float(pos.get('stopLoss', 0) or 0) if pos.get('stopLoss') else None,
                    take_profit=float(pos.get('takeProfit', 0) or 0) if pos.get('takeProfit') else None,
                    liquidation_price=float(pos.get('liquidationPrice', 0) or 0) if pos.get('liquidationPrice') else None,
                )
                positions.append(position)
            
            logger.info(f"📊 Fetched {len(positions)} open positions")
            return positions
            
        except Exception as e:
            logger.error(f"❌ Error fetching positions: {e}")
            return []
    
    def set_trading_stop(
        self,
        symbol: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_side: str = None
    ) -> Tuple[bool, str]:
        """
        Set stop loss and/or take profit for a position.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT:USDT")
            stop_loss: Stop loss price
            take_profit: Take profit price
            position_side: 'long' or 'short' (auto-detected if None)
        
        Returns:
            Tuple of (success, message)
        """
        if not self.is_available:
            return False, "Bybit service not available"
        
        if not stop_loss and not take_profit:
            return False, "Must specify stop_loss and/or take_profit"
        
        try:
            exchange = self._get_exchange()
            if exchange is None:
                raise Exception("Exchange not initialized")
            
            # Convert symbol to Bybit format
            bybit_symbol = symbol.replace('/USDT:USDT', 'USDT').replace('/', '')
            
            # ╔════════════════════════════════════════════════════════════════╗
            # ║  BYBIT API CALL: POST /v5/position/trading-stop                ║
            # ║  Sets stop loss and/or take profit on a position               ║
            # ╚════════════════════════════════════════════════════════════════╝
            
            # Auto-detect position side if not provided
            position_idx = 0  # Default: One-Way mode
            
            if position_side is None:
                positions = exchange.fetch_positions([symbol])
                for pos in positions:
                    if pos.get('symbol') == symbol and float(pos.get('contracts', 0)) != 0:
                        position_side = pos.get('side', '').lower()
                        pos_info = pos.get('info', {})
                        position_idx = int(pos_info.get('positionIdx', 0))
                        break
            
            # Build API params
            params = {
                'category': 'linear',
                'symbol': bybit_symbol,
                'tpslMode': 'Full',
                'positionIdx': position_idx
            }
            
            if stop_loss:
                params['stopLoss'] = str(stop_loss)
            if take_profit:
                params['takeProfit'] = str(take_profit)
            
            # Execute API call
            result = exchange.private_post_v5_position_trading_stop(params)
            
            ret_code = result.get('retCode', -1)
            ret_msg = result.get('retMsg', 'Unknown response')
            
            if ret_code == 0 or str(ret_code) == "0":
                sl_str = f"SL: ${stop_loss}" if stop_loss else ""
                tp_str = f"TP: ${take_profit}" if take_profit else ""
                logger.info(f"✅ Trading stop set for {bybit_symbol}: {sl_str} {tp_str}")
                return True, f"Stop set successfully: {sl_str} {tp_str}"
            
            elif ret_code == 34040 and "not modified" in ret_msg.lower():
                return True, "Stop loss already set correctly"
            
            else:
                return False, f"Bybit error {ret_code}: {ret_msg}"
                
        except Exception as e:
            error_str = str(e).lower()
            if "34040" in error_str and "not modified" in error_str:
                return True, "Stop loss already set correctly"
            
            logger.error(f"❌ Error setting trading stop: {e}")
            return False, str(e)
    
    def place_order(
        self,
        symbol: str,
        side: str,  # 'buy' or 'sell'
        amount: float,
        order_type: str = 'market',  # 'market' or 'limit'
        price: Optional[float] = None,
        leverage: int = 1,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None
    ) -> OrderResult:
        """
        Place an order on Bybit.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT:USDT")
            side: 'buy' (long) or 'sell' (short)
            amount: Order size in base currency
            order_type: 'market' or 'limit'
            price: Limit price (required for limit orders)
            leverage: Leverage multiplier
            stop_loss_pct: Auto-set SL as percentage from entry
            take_profit_pct: Auto-set TP as percentage from entry
        
        Returns:
            OrderResult with execution details
        """
        if not self.is_available:
            return OrderResult(
                success=False,
                order_id=None,
                symbol=symbol,
                side=side,
                amount=amount,
                price=price,
                error="Bybit service not available"
            )
        
        try:
            exchange = self._get_exchange()
            if exchange is None:
                raise Exception("Exchange not initialized")
            
            # ╔════════════════════════════════════════════════════════════════╗
            # ║  SET LEVERAGE                                                   ║
            # ╚════════════════════════════════════════════════════════════════╝
            try:
                exchange.set_leverage(leverage, symbol)
                logger.info(f"⚡ Leverage set to {leverage}x for {symbol}")
            except Exception as e:
                logger.warning(f"⚠️ Could not set leverage: {e}")
            
            # ╔════════════════════════════════════════════════════════════════╗
            # ║  PLACE ORDER                                                    ║
            # ╚════════════════════════════════════════════════════════════════╝
            params = {}
            
            if order_type == 'market':
                order = exchange.create_market_order(symbol, side, amount, params=params)
            else:
                if price is None:
                    return OrderResult(
                        success=False,
                        order_id=None,
                        symbol=symbol,
                        side=side,
                        amount=amount,
                        price=None,
                        error="Price required for limit orders"
                    )
                order = exchange.create_limit_order(symbol, side, amount, price, params=params)
            
            order_id = order.get('id')
            fill_price = float(order.get('average', 0) or order.get('price', 0) or 0)
            
            logger.info(f"✅ Order placed: {side.upper()} {amount} {symbol} @ ${fill_price}")
            
            # ╔════════════════════════════════════════════════════════════════╗
            # ║  AUTO-SET STOP LOSS / TAKE PROFIT                              ║
            # ╚════════════════════════════════════════════════════════════════╝
            if fill_price > 0 and (stop_loss_pct or take_profit_pct):
                is_long = side.lower() == 'buy'
                
                sl_price = None
                tp_price = None
                
                if stop_loss_pct:
                    if is_long:
                        sl_price = fill_price * (1 - stop_loss_pct / 100)
                    else:
                        sl_price = fill_price * (1 + stop_loss_pct / 100)
                
                if take_profit_pct:
                    if is_long:
                        tp_price = fill_price * (1 + take_profit_pct / 100)
                    else:
                        tp_price = fill_price * (1 - take_profit_pct / 100)
                
                if sl_price or tp_price:
                    sl_success, sl_msg = self.set_trading_stop(
                        symbol=symbol,
                        stop_loss=sl_price,
                        take_profit=tp_price
                    )
                    if sl_success:
                        logger.info(f"✅ Auto SL/TP set: {sl_msg}")
                    else:
                        logger.warning(f"⚠️ Failed to set SL/TP: {sl_msg}")
            
            return OrderResult(
                success=True,
                order_id=order_id,
                symbol=symbol,
                side=side,
                amount=amount,
                price=fill_price
            )
            
        except Exception as e:
            logger.error(f"❌ Error placing order: {e}")
            return OrderResult(
                success=False,
                order_id=None,
                symbol=symbol,
                side=side,
                amount=amount,
                price=price,
                error=str(e)
            )
    
    def get_ticker_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol"""
        if not self.is_available:
            return None
        
        try:
            exchange = self._get_exchange()
            if exchange is None:
                return None
            
            ticker = exchange.fetch_ticker(symbol)
            return float(ticker.get('last', 0) or 0)
            
        except Exception as e:
            logger.error(f"❌ Error fetching ticker: {e}")
            return None


# ============================================================
# SINGLETON INSTANCE
# ============================================================
_bybit_service: Optional[BybitService] = None


def get_bybit_service() -> BybitService:
    """Get singleton Bybit service instance"""
    global _bybit_service
    if _bybit_service is None:
        _bybit_service = BybitService()
    return _bybit_service
