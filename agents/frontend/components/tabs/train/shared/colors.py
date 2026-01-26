"""
Colors - Centralized dark theme color scheme.

This module consolidates the duplicated COLORS dict that was
previously defined in multiple files:
- training_ai_eval.py
- training_btc_inference.py  
- training_results.py (removed)

All train tab components should import colors from here.

Note: For global app styling, see also:
- agents/frontend/styles/colors.py (global app colors)
"""

# Dark theme color scheme for Train tab components
COLORS = {
    # Primary colors
    'primary': '#00ffff',      # Cyan - main accent
    'secondary': '#ff6b6b',    # Red - secondary accent
    
    # Status colors  
    'success': '#4ade80',      # Green
    'warning': '#fbbf24',      # Yellow/amber
    'error': '#ef4444',        # Red
    'info': '#60a5fa',         # Blue
    
    # Background colors
    'background': '#0d1117',   # Darkest
    'card': '#1e2130',         # Card background
    
    # Text colors
    'text': '#e0e0ff',         # Primary text
    'muted': '#9ca3af',        # Secondary/muted text
    
    # Border/grid
    'border': '#2d3748',
    'grid': '#2a2a4a',
    
    # Trading specific
    'long': '#00ffff',         # Cyan for LONG
    'short': '#ff6b6b',        # Red for SHORT
    'bullish': '#4ade80',      # Green for bullish
    'bearish': '#ff6b6b',      # Red for bearish
}


# Rating colors for AI analysis quality badges
RATING_COLORS = {
    'excellent': '#4ade80',
    'good': '#fbbf24',
    'acceptable': '#f97316',
    'poor': '#ff6b6b',
    'unknown': '#888888'
}


# Signal colors for trading signals
SIGNAL_COLORS = {
    'STRONG BUY': '#4ade80',
    'BUY': '#34d399',
    'HOLD': '#9ca3af',
    'SELL': '#f97316',
    'STRONG SELL': '#ff6b6b'
}


__all__ = ['COLORS', 'RATING_COLORS', 'SIGNAL_COLORS']
