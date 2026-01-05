"""
📑 Tab Components for the Crypto Dashboard
Tabs: Top 100 Coins, Coin Analysis, and Backtest
"""

from .top_coins import render_top_coins_tab
from .analysis import render_analysis_tab
from .backtest import render_backtest_tab

__all__ = [
    'render_top_coins_tab',
    'render_analysis_tab',
    'render_backtest_tab',
]
