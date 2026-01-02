"""
📑 Tab Components for the Crypto Dashboard
Only two tabs: Top 100 Coins and Coin Analysis
"""

from .top_coins import render_top_coins_tab
from .analysis import render_analysis_tab

__all__ = [
    'render_top_coins_tab',
    'render_analysis_tab',
]
