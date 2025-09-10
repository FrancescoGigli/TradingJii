"""
Backtesting module for the trading bot
Contains all backtesting functionality separated from live trading
"""

from .backtest_engine import BacktestEngine

__all__ = ['BacktestEngine']
