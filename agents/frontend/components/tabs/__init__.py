"""
Tabs package for the Crypto Dashboard
"""

from .top_coins import render_top_coins_tab
from .advanced_charts import render_advanced_charts_tab
from .volume_analysis import render_volume_analysis_tab
from .technical import render_technical_tab

__all__ = [
    'render_top_coins_tab',
    'render_advanced_charts_tab',
    'render_volume_analysis_tab',
    'render_technical_tab'
]
