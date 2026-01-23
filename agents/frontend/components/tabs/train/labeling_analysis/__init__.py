"""
📊 Labeling Analysis Module

Modular package for post-labeling diagnostic charts and analysis.
Split from monolithic labeling_analysis.py for maintainability.

Submodules:
- charts: Chart creation functions (MAE, score, ATR, etc.)
- dashboard: Main analysis dashboard rendering
- stability: Parameter stability report
- quality: Deep label quality analysis

Usage:
    from agents.frontend.components.tabs.train.labeling_analysis import (
        create_mae_histogram,
        render_analysis_dashboard,
        render_stability_report,
        render_label_quality_analysis
    )
"""

# Re-export all public functions for backward compatibility
from .charts import (
    create_mae_histogram,
    create_mae_vs_score_scatter,
    create_exit_type_pie,
    create_score_distribution,
    create_atr_analysis,
    create_bars_held_histogram
)

from .dashboard import render_analysis_dashboard

from .stability import (
    get_stability_report,
    render_stability_report
)

from .quality import (
    get_label_quality_from_db,
    create_score_vs_return_scatter,
    create_score_range_bar_chart,
    create_positive_distribution_pie,
    render_label_quality_analysis
)

__all__ = [
    # Charts
    'create_mae_histogram',
    'create_mae_vs_score_scatter',
    'create_exit_type_pie',
    'create_score_distribution',
    'create_atr_analysis',
    'create_bars_held_histogram',
    # Dashboard
    'render_analysis_dashboard',
    # Stability
    'get_stability_report',
    'render_stability_report',
    # Quality
    'get_label_quality_from_db',
    'create_score_vs_return_scatter',
    'create_score_range_bar_chart',
    'create_positive_distribution_pie',
    'render_label_quality_analysis'
]
