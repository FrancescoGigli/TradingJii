"""
🎨 Styles Package for the Crypto Dashboard
Centralized theming, colors, and styled components
"""

# Color palette and configuration
from .colors import (
    PALETTE,
    CHART_COLORS,
    SIGNAL_COLORS,
    STATUS_COLORS,
    PLOTLY_LAYOUT,
    get_gradient,
    get_glow,
    rgba
)

# Styled components
from .components import (
    styled_table,
    styled_signal_box,
    styled_metric_card,
    styled_info_box,
    styled_section_header,
    styled_status_indicator,
    get_signal_color
)

# Theme injection
from .theme import inject_theme

__all__ = [
    # Colors
    'PALETTE',
    'CHART_COLORS', 
    'SIGNAL_COLORS',
    'STATUS_COLORS',
    'PLOTLY_LAYOUT',
    'get_gradient',
    'get_glow',
    'rgba',
    # Components
    'styled_table',
    'styled_signal_box',
    'styled_metric_card',
    'styled_info_box',
    'styled_section_header',
    'styled_status_indicator',
    'get_signal_color',
    # Theme
    'inject_theme',
]
