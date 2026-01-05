"""
🔄 Backtest Module - Backtesting engine and trade simulation
"""

from .trades import Trade, TradeType, TradeList, IndicatorSnapshot, SignalLog, safe_strftime
from .engine import BacktestEngine, BacktestResult, run_backtest
from .logger import (
    log_signal,
    log_trade,
    log_backtest_summary,
    get_recent_signals,
    get_trade_history,
    clear_logs,
    get_log_stats,
    safe_timestamp_str
)

__all__ = [
    'Trade',
    'TradeType', 
    'TradeList',
    'IndicatorSnapshot',
    'SignalLog',
    'safe_strftime',
    'BacktestEngine',
    'BacktestResult',
    'run_backtest',
    # Logging
    'log_signal',
    'log_trade',
    'log_backtest_summary',
    'get_recent_signals',
    'get_trade_history',
    'clear_logs',
    'get_log_stats',
    'safe_timestamp_str'
]
