"""
📦 Order Manager - Trade Execution with Auto SL/TP

Provides high-level order management that:
1. Uses trading settings from sidebar
2. Auto-calculates SL/TP based on settings
3. Executes via BybitService

Ready for both backtest simulation and real trading.
"""

import logging
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime

from .risk_manager import RiskManager, TradingSettings, get_trading_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TradeOrder:
    """
    Represents a trade order with all parameters.
    """
    symbol: str
    side: str  # 'buy' (long) or 'sell' (short)
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    leverage: int
    
    # Execution status
    is_executed: bool = False
    order_id: Optional[str] = None
    fill_price: Optional[float] = None
    error: Optional[str] = None
    
    # Timestamps
    created_at: datetime = None
    executed_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    @property
    def is_long(self) -> bool:
        return self.side.lower() == 'buy'
    
    @property
    def trade_type(self) -> str:
        return "LONG" if self.is_long else "SHORT"
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'side': self.side,
            'trade_type': self.trade_type,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'leverage': self.leverage,
            'is_executed': self.is_executed,
            'order_id': self.order_id,
            'fill_price': self.fill_price,
            'error': self.error,
        }


class OrderManager:
    """
    High-level order management.
    
    Creates orders with auto-calculated SL/TP based on trading settings.
    Can execute via BybitService for real trading.
    
    Usage:
        manager = OrderManager()
        order = manager.create_order("BTC/USDT:USDT", "buy", entry_price=68000)
        result = manager.execute_order(order)  # For real trading
    """
    
    def __init__(self, settings: TradingSettings = None):
        """
        Initialize Order Manager.
        
        Args:
            settings: TradingSettings (defaults to session_state settings)
        """
        self.settings = settings or get_trading_settings()
        self.risk_manager = RiskManager(self.settings)
        self._bybit_service = None
    
    @property
    def bybit_service(self):
        """Lazy load BybitService to avoid import issues"""
        if self._bybit_service is None:
            try:
                from services.bybit_service import get_bybit_service
                self._bybit_service = get_bybit_service()
            except ImportError:
                logger.warning("⚠️ BybitService not available")
        return self._bybit_service
    
    def create_order(
        self,
        symbol: str,
        side: str,  # 'buy' or 'sell'
        entry_price: float,
        quantity: float = None,
        balance: float = None,
        stop_loss_pct: float = None,
        take_profit_pct: float = None,
        leverage: int = None
    ) -> TradeOrder:
        """
        Create a trade order with auto-calculated SL/TP.
        
        Args:
            symbol: Trading pair
            side: 'buy' (long) or 'sell' (short)
            entry_price: Expected entry price
            quantity: Position size (if None, calculated from balance)
            balance: Available balance (for position sizing)
            stop_loss_pct: Override settings SL %
            take_profit_pct: Override settings TP %
            leverage: Override settings leverage
        
        Returns:
            TradeOrder ready for execution
        """
        is_long = side.lower() == 'buy'
        
        # Use settings or overrides
        sl_pct = stop_loss_pct or self.settings.stop_loss_pct
        tp_pct = take_profit_pct or self.settings.take_profit_pct
        lev = leverage or self.settings.leverage
        
        # Calculate SL/TP prices
        sl_price = self.risk_manager.calculate_stop_loss_price(entry_price, is_long, sl_pct)
        tp_price = self.risk_manager.calculate_take_profit_price(entry_price, is_long, tp_pct)
        
        # Calculate quantity if not provided
        if quantity is None:
            if balance is None:
                # Default to a small position for safety
                quantity = 0.001
                logger.warning("⚠️ No quantity or balance provided, using minimum")
            else:
                position_info = self.risk_manager.calculate_position_size(
                    balance, entry_price, sl_price, is_long
                )
                quantity = position_info['quantity']
        
        order = TradeOrder(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=round(sl_price, 2),
            take_profit=round(tp_price, 2),
            leverage=lev
        )
        
        logger.info(
            f"📝 Order created: {order.trade_type} {symbol} | "
            f"Entry: ${entry_price:,.2f} | SL: ${sl_price:,.2f} | TP: ${tp_price:,.2f}"
        )
        
        return order
    
    def execute_order(self, order: TradeOrder, dry_run: bool = True) -> TradeOrder:
        """
        Execute a trade order on Bybit.
        
        Args:
            order: TradeOrder to execute
            dry_run: If True, simulate without placing real order
        
        Returns:
            Updated TradeOrder with execution status
        """
        if dry_run:
            logger.info(f"🔄 DRY RUN: Would execute {order.trade_type} {order.symbol}")
            order.is_executed = True
            order.fill_price = order.entry_price
            order.executed_at = datetime.now()
            return order
        
        # Real execution
        if self.bybit_service is None or not self.bybit_service.is_available:
            order.error = "Bybit service not available"
            logger.error(f"❌ {order.error}")
            return order
        
        try:
            # Execute order with auto SL/TP
            result = self.bybit_service.place_order(
                symbol=order.symbol,
                side=order.side,
                amount=order.quantity,
                order_type='market',
                leverage=order.leverage,
                stop_loss_pct=self.settings.stop_loss_pct,
                take_profit_pct=self.settings.take_profit_pct
            )
            
            if result.success:
                order.is_executed = True
                order.order_id = result.order_id
                order.fill_price = result.price
                order.executed_at = datetime.now()
                logger.info(f"✅ Order executed: {order.order_id}")
            else:
                order.error = result.error
                logger.error(f"❌ Order failed: {result.error}")
                
        except Exception as e:
            order.error = str(e)
            logger.error(f"❌ Execution error: {e}")
        
        return order
    
    def simulate_backtest_trade(
        self,
        symbol: str,
        trade_type: str,  # 'LONG' or 'SHORT'
        entry_price: float,
        exit_price: float,
        entry_time: datetime,
        exit_time: datetime
    ) -> Dict:
        """
        Simulate a backtest trade with SL/TP calculations.
        
        Returns:
            Dict with trade results including leveraged PnL
        """
        is_long = trade_type.upper() == 'LONG'
        
        # Calculate SL/TP prices
        sl_price, tp_price = self.risk_manager.calculate_sl_tp_prices(entry_price, is_long)
        
        # Check if SL or TP was hit
        sl_hit = False
        tp_hit = False
        actual_exit_price = exit_price
        
        if is_long:
            if exit_price <= sl_price:
                sl_hit = True
                actual_exit_price = sl_price
            elif exit_price >= tp_price:
                tp_hit = True
                actual_exit_price = tp_price
        else:
            if exit_price >= sl_price:
                sl_hit = True
                actual_exit_price = sl_price
            elif exit_price <= tp_price:
                tp_hit = True
                actual_exit_price = tp_price
        
        # Calculate PnL
        pnl = self.risk_manager.calculate_pnl(
            entry_price=entry_price,
            exit_price=actual_exit_price,
            quantity=1.0,  # Normalized
            is_long=is_long
        )
        
        return {
            'symbol': symbol,
            'trade_type': trade_type,
            'entry_price': entry_price,
            'exit_price': actual_exit_price,
            'original_exit_price': exit_price,
            'stop_loss': sl_price,
            'take_profit': tp_price,
            'sl_hit': sl_hit,
            'tp_hit': tp_hit,
            'pnl_pct': pnl['pnl_pct'],
            'pnl_pct_with_leverage': pnl['pnl_pct_with_leverage'],
            'leverage': self.settings.leverage,
            'is_profit': pnl['is_profit'],
            'entry_time': entry_time,
            'exit_time': exit_time,
        }
    
    def get_order_summary(self, order: TradeOrder) -> str:
        """Get formatted order summary for display"""
        status = "✅ EXECUTED" if order.is_executed else "⏳ PENDING"
        if order.error:
            status = f"❌ ERROR: {order.error}"
        
        return f"""
**{order.trade_type} Order - {order.symbol}**

**Status:** {status}

| Parameter | Value |
|-----------|-------|
| Entry Price | ${order.entry_price:,.2f} |
| Stop Loss | ${order.stop_loss:,.2f} |
| Take Profit | ${order.take_profit:,.2f} |
| Quantity | {order.quantity:.6f} |
| Leverage | {order.leverage}x |

{f'**Order ID:** {order.order_id}' if order.order_id else ''}
{f'**Fill Price:** ${order.fill_price:,.2f}' if order.fill_price else ''}
"""


# ============================================================
# SINGLETON INSTANCE
# ============================================================
_order_manager: Optional[OrderManager] = None


def get_order_manager() -> OrderManager:
    """Get singleton Order Manager instance"""
    global _order_manager
    if _order_manager is None:
        _order_manager = OrderManager()
    return _order_manager
