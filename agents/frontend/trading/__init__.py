"""
📦 Trading Package

Trading utilities and risk management:
- RiskManager: Calculate stop loss, take profit, position sizing
- OrderManager: Execute trades with SL/TP automation
- TradingSettings: User-configurable trading parameters
"""

from .risk_manager import RiskManager, TradingSettings, get_trading_settings
from .order_manager import OrderManager, get_order_manager

__all__ = [
    'RiskManager',
    'TradingSettings',
    'get_trading_settings',
    'OrderManager',
    'get_order_manager'
]
