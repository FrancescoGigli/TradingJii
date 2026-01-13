"""
📑 Tab Components for the Crypto Dashboard

Tabs:
- Top 100 Coins: Market overview
- Coin Analysis: Technical analysis
- Backtest: Strategy backtesting
- Historical Data: ML training data monitor
- ML Labels: Training label visualization
- XGB Models: XGBoost model results visualization
"""

from .top_coins import render_top_coins_tab
from .analysis import render_analysis_tab
from .backtest import render_backtest_tab
from .historical_data import render_historical_data_tab
from .ml_labels import render_ml_labels_tab
from .xgb_models import render_xgb_models_tab

__all__ = [
    'render_top_coins_tab',
    'render_analysis_tab',
    'render_backtest_tab',
    'render_historical_data_tab',
    'render_ml_labels_tab',
    'render_xgb_models_tab',
]
