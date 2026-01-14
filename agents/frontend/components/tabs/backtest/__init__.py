"""
🔄 Backtest Tab - Modular structure

Main entry point that imports and orchestrates all backtest sub-modules:
- controls: Settings and configuration UI
- signals: Dual signal comparison (Tech vs XGB)
- xgb_section: XGBoost ML backtest and simulation
- optimization: Trailing stop optimization for live trading
"""

from .main import render_backtest_tab
from .optimization import render_optimization_section

__all__ = ['render_backtest_tab', 'render_optimization_section']
