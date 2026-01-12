"""
Bybit Service - Main Service Class
"""

import os
import logging
import threading
from datetime import datetime
from typing import Optional, List, Tuple

try:
    import ccxt
except ImportError:
    ccxt = None

from .models import (
    BalanceInfo, PositionInfo, OrderResult, CachedData,
    API_TIMEOUT_MS, MAX_RETRIES, RETRY_DELAY_BASE, EXCHANGE_RECONNECT_INTERVAL
)
from .decorators import retry_with_backoff

logger = logging.getLogger(__name__)


class BybitService:
    """
    Service class for Bybit exchange operations.
    
    Features:
    - Automatic timeout on all API calls
    - Retry with exponential backoff
    - Response caching to reduce API calls
    - Automatic exchange reconnection
    - Thread-safe operations
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key or os.getenv("BYBIT_API_KEY")
        self.api_secret = api_secret or os.getenv("BYBIT_API_SECRET")
        self._exchange = None
        self._exchange_created_at: Optional[datetime] = None
        self._initialized = False
        self._lock = threading.Lock()
        
        self._balance_cache: Optional[CachedData] = None
        self._positions_cache: Optional[CachedData] = None
        
        if not self.api_key or not self.api_secret:
            logger.warning("⚠️ Bybit API credentials not configured")
            self._has_credentials = False
        else:
            self._has_credentials = True
    
    def _should_reconnect(self) -> bool:
        if self._exchange is None or self._exchange_created_at is None:
            return True
        age = (datetime.now() - self._exchange_created_at).total_seconds()
        return age > EXCHANGE_RECONNECT_INTERVAL
    
    def _create_exchange(self) -> Optional['ccxt.bybit']:
        if ccxt is None:
            logger.error("❌ CCXT library not installed")
            return None
        if not self._has_credentials:
            return None
        
        try:
            exchange = ccxt.bybit({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
                'timeout': API_TIMEOUT_MS,
                'options': {'adjustForTimeDifference': True, 'recvWindow': 60000},
                'rateLimit': 100,
            })
            logger.info("✅ Bybit exchange initialized with timeout=%dms", API_TIMEOUT_MS)
            return exchange
        except Exception as e:
            logger.error(f"❌ Failed to initialize Bybit: {e}")
            return None
    
    def _get_exchange(self, force_reconnect: bool = False) -> Optional['ccxt.bybit']:
        with self._lock:
            if force_reconnect or self._should_reconnect():
                logger.info("🔄 Reconnecting to Bybit exchange...")
                self._exchange = self._create_exchange()
                self._exchange_created_at = datetime.now() if self._exchange else None
                self._initialized = self._exchange is not None
            return self._exchange
    
    def _invalidate_exchange(self):
        with self._lock:
            logger.warning("⚠️ Invalidating exchange connection...")
            self._exchange = None
            self._exchange_created_at = None
            self._initialized = False
    
    @property
    def is_available(self) -> bool:
        return self._has_credentials and ccxt is not None
    
    def get_balance(self, use_cache: bool = True) -> BalanceInfo:
        if use_cache and self._balance_cache and self._balance_cache.is_valid:
            logger.debug("💾 Using cached balance")
            return self._balance_cache.data
        
        if not self.is_available:
            return BalanceInfo(total_usdt=0.0, available_usdt=0.0, used_usdt=0.0, timestamp=datetime.now(), is_real=False)
        
        try:
            balance_info = self._fetch_balance_with_retry()
            self._balance_cache = CachedData(data=balance_info, timestamp=datetime.now())
            return balance_info
        except Exception as e:
            logger.error(f"❌ Error fetching balance: {e}")
            if self._balance_cache and self._balance_cache.data:
                logger.warning("⚠️ Returning stale cached balance")
                return self._balance_cache.data
            return BalanceInfo(total_usdt=0.0, available_usdt=0.0, used_usdt=0.0, timestamp=datetime.now(), is_real=False)
    
    @retry_with_backoff(max_retries=MAX_RETRIES, base_delay=RETRY_DELAY_BASE)
    def _fetch_balance_with_retry(self) -> BalanceInfo:
        exchange = self._get_exchange()
        if exchange is None:
            raise Exception("Exchange not initialized")
        
        try:
            balance_data = exchange.fetch_balance()
            usdt_total, usdt_free, usdt_used = 0.0, 0.0, 0.0
            
            if 'USDT' in balance_data:
                usdt_info = balance_data['USDT']
                if isinstance(usdt_info, dict):
                    usdt_total = float(usdt_info.get('total', 0) or 0)
                    usdt_free = float(usdt_info.get('free', 0) or 0)
                    usdt_used = float(usdt_info.get('used', 0) or 0)
            
            if usdt_total == 0 and 'total' in balance_data:
                if isinstance(balance_data['total'], dict):
                    usdt_total = float(balance_data['total'].get('USDT', 0) or 0)
                    usdt_free = float(balance_data.get('free', {}).get('USDT', 0) or 0)
                    usdt_used = float(balance_data.get('used', {}).get('USDT', 0) or 0)
            
            logger.info(f"💰 Balance fetched: ${usdt_total:.2f} USDT")
            return BalanceInfo(total_usdt=usdt_total, available_usdt=usdt_free, used_usdt=usdt_used, timestamp=datetime.now(), is_real=True)
        except (ccxt.NetworkError, ccxt.RequestTimeout):
            self._invalidate_exchange()
            raise
        except ccxt.ExchangeError as e:
            if 'timestamp' in str(e).lower() or 'sign' in str(e).lower():
                self._invalidate_exchange()
            raise
    
    def get_positions(self, use_cache: bool = True) -> List[PositionInfo]:
        if use_cache and self._positions_cache and self._positions_cache.is_valid:
            logger.debug("💾 Using cached positions")
            return self._positions_cache.data
        
        if not self.is_available:
            return []
        
        try:
            positions = self._fetch_positions_with_retry()
            self._positions_cache = CachedData(data=positions, timestamp=datetime.now())
            return positions
        except Exception as e:
            logger.error(f"❌ Error fetching positions: {e}")
            if self._positions_cache and self._positions_cache.data:
                logger.warning("⚠️ Returning stale cached positions")
                return self._positions_cache.data
            return []
    
    @retry_with_backoff(max_retries=MAX_RETRIES, base_delay=RETRY_DELAY_BASE)
    def _fetch_positions_with_retry(self) -> List[PositionInfo]:
        exchange = self._get_exchange()
        if exchange is None:
            raise Exception("Exchange not initialized")
        
        try:
            positions_data = exchange.fetch_positions()
            positions = []
            for pos in positions_data:
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
        except (ccxt.NetworkError, ccxt.RequestTimeout):
            self._invalidate_exchange()
            raise
        except ccxt.ExchangeError as e:
            if 'timestamp' in str(e).lower() or 'sign' in str(e).lower():
                self._invalidate_exchange()
            raise
    
    def clear_cache(self):
        self._balance_cache = None
        self._positions_cache = None
        logger.info("🗑️ Cache cleared")
    
    def force_reconnect(self):
        self._invalidate_exchange()
        self._get_exchange(force_reconnect=True)
    
    def set_trading_stop(self, symbol: str, stop_loss: Optional[float] = None, take_profit: Optional[float] = None, position_side: str = None) -> Tuple[bool, str]:
        if not self.is_available:
            return False, "Bybit service not available"
        if not stop_loss and not take_profit:
            return False, "Must specify stop_loss and/or take_profit"
        
        try:
            return self._set_trading_stop_with_retry(symbol, stop_loss, take_profit, position_side)
        except Exception as e:
            error_str = str(e).lower()
            if "34040" in error_str and "not modified" in error_str:
                return True, "Stop loss already set correctly"
            logger.error(f"❌ Error setting trading stop: {e}")
            return False, str(e)
    
    @retry_with_backoff(max_retries=2, base_delay=0.5)
    def _set_trading_stop_with_retry(self, symbol: str, stop_loss: Optional[float], take_profit: Optional[float], position_side: str = None) -> Tuple[bool, str]:
        exchange = self._get_exchange()
        if exchange is None:
            raise Exception("Exchange not initialized")
        
        bybit_symbol = symbol.replace('/USDT:USDT', 'USDT').replace('/', '')
        position_idx = 0
        
        if position_side is None:
            positions = exchange.fetch_positions([symbol])
            for pos in positions:
                if pos.get('symbol') == symbol and float(pos.get('contracts', 0)) != 0:
                    position_side = pos.get('side', '').lower()
                    pos_info = pos.get('info', {})
                    position_idx = int(pos_info.get('positionIdx', 0))
                    break
        
        params = {'category': 'linear', 'symbol': bybit_symbol, 'tpslMode': 'Full', 'positionIdx': position_idx}
        if stop_loss:
            params['stopLoss'] = str(stop_loss)
        if take_profit:
            params['takeProfit'] = str(take_profit)
        
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
    
    def place_order(self, symbol: str, side: str, amount: float, order_type: str = 'market', price: Optional[float] = None, leverage: int = 1, stop_loss_pct: Optional[float] = None, take_profit_pct: Optional[float] = None) -> OrderResult:
        if not self.is_available:
            return OrderResult(success=False, order_id=None, symbol=symbol, side=side, amount=amount, price=price, error="Bybit service not available")
        
        try:
            return self._place_order_with_retry(symbol, side, amount, order_type, price, leverage, stop_loss_pct, take_profit_pct)
        except Exception as e:
            logger.error(f"❌ Error placing order: {e}")
            return OrderResult(success=False, order_id=None, symbol=symbol, side=side, amount=amount, price=price, error=str(e))
    
    @retry_with_backoff(max_retries=2, base_delay=0.5)
    def _place_order_with_retry(self, symbol: str, side: str, amount: float, order_type: str, price: Optional[float], leverage: int, stop_loss_pct: Optional[float], take_profit_pct: Optional[float]) -> OrderResult:
        exchange = self._get_exchange()
        if exchange is None:
            raise Exception("Exchange not initialized")
        
        try:
            exchange.set_leverage(leverage, symbol)
            logger.info(f"⚡ Leverage set to {leverage}x for {symbol}")
        except Exception as e:
            logger.warning(f"⚠️ Could not set leverage: {e}")
        
        params = {}
        if order_type == 'market':
            order = exchange.create_market_order(symbol, side, amount, params=params)
        else:
            if price is None:
                return OrderResult(success=False, order_id=None, symbol=symbol, side=side, amount=amount, price=None, error="Price required for limit orders")
            order = exchange.create_limit_order(symbol, side, amount, price, params=params)
        
        order_id = order.get('id')
        fill_price = float(order.get('average', 0) or order.get('price', 0) or 0)
        logger.info(f"✅ Order placed: {side.upper()} {amount} {symbol} @ ${fill_price}")
        self.clear_cache()
        
        if fill_price > 0 and (stop_loss_pct or take_profit_pct):
            is_long = side.lower() == 'buy'
            sl_price = fill_price * (1 - stop_loss_pct / 100) if stop_loss_pct and is_long else fill_price * (1 + stop_loss_pct / 100) if stop_loss_pct else None
            tp_price = fill_price * (1 + take_profit_pct / 100) if take_profit_pct and is_long else fill_price * (1 - take_profit_pct / 100) if take_profit_pct else None
            
            if sl_price or tp_price:
                sl_success, sl_msg = self.set_trading_stop(symbol=symbol, stop_loss=sl_price, take_profit=tp_price)
                if sl_success:
                    logger.info(f"✅ Auto SL/TP set: {sl_msg}")
                else:
                    logger.warning(f"⚠️ Failed to set SL/TP: {sl_msg}")
        
        return OrderResult(success=True, order_id=order_id, symbol=symbol, side=side, amount=amount, price=fill_price)
    
    def get_ticker_price(self, symbol: str) -> Optional[float]:
        if not self.is_available:
            return None
        try:
            return self._get_ticker_with_retry(symbol)
        except Exception as e:
            logger.error(f"❌ Error fetching ticker: {e}")
            return None
    
    @retry_with_backoff(max_retries=2, base_delay=0.3)
    def _get_ticker_with_retry(self, symbol: str) -> Optional[float]:
        exchange = self._get_exchange()
        if exchange is None:
            return None
        ticker = exchange.fetch_ticker(symbol)
        return float(ticker.get('last', 0) or 0)
