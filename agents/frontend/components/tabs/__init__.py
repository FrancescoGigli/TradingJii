"""
📑 Tab Components for the Crypto Dashboard

Tabs:
- Top 100 Coins: Market overview + Coin Analysis (charts, technical indicators)
- Backtest: Strategy backtesting
- Train: Unified ML training pipeline (Data → Labeling → Training → Models)
"""

from .top_coins import render_top_coins_tab
from .backtest import render_backtest_tab
from .train import render_train_tab

__all__ = [
    'render_top_coins_tab',
    'render_backtest_tab',
    'render_train_tab',
]
