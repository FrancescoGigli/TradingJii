"""
🎨 Centralized Color Palette for the Crypto Dashboard
All colors in ONE place - modify here to change the entire theme
"""

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PALETTE - Background & Text
# ═══════════════════════════════════════════════════════════════════════════════
PALETTE = {
    # Backgrounds (dark to light)
    'bg_primary': '#0a0a1a',        # Darkest - main app background
    'bg_secondary': '#0d1117',      # Dark - cards, tables
    'bg_tertiary': '#161b26',       # Medium - headers, hover states
    'bg_card': 'rgba(10, 15, 30, 0.8)',  # Semi-transparent card
    'bg_input': 'rgba(15, 20, 40, 0.95)', # Input fields
    
    # Text colors
    'text_primary': '#ffffff',      # Main text
    'text_secondary': '#e0e0ff',    # Secondary text
    'text_muted': '#8899aa',        # Muted/label text
    'text_dim': '#6688aa',          # Very dim text
    
    # Accent colors
    'accent_cyan': '#00ffff',       # Primary accent (headers, highlights)
    'accent_green': '#00ff88',      # Positive/Buy signals
    'accent_red': '#ff4757',        # Negative/Sell signals
    'accent_yellow': '#ffc107',     # Warning/Neutral signals
    'accent_purple': '#a855f7',     # RSI, special indicators
    'accent_orange': '#ff6b35',     # Secondary lines
    'accent_blue': '#00d4ff',       # MACD, info elements
    
    # Border colors
    'border_primary': 'rgba(0, 255, 255, 0.3)',   # Default border
    'border_hover': 'rgba(0, 255, 255, 0.6)',     # Hover state
    'border_strong': 'rgba(0, 255, 255, 0.5)',    # Strong border
}

# ═══════════════════════════════════════════════════════════════════════════════
# CHART COLORS - For Plotly graphs
# ═══════════════════════════════════════════════════════════════════════════════
CHART_COLORS = {
    # Candlestick
    'candle_up_line': '#00ff88',
    'candle_up_fill': '#00875a',
    'candle_down_line': '#ff4757',
    'candle_down_fill': '#c92a2a',
    
    # Volume bars
    'volume_up': '#00875a',
    'volume_down': '#c92a2a',
    
    # Moving Averages
    'ema_20': '#ffc107',
    'ema_50': '#ff6b35',
    'sma': '#00d4ff',
    
    # Bollinger Bands
    'bb_upper': 'rgba(0, 212, 255, 0.3)',
    'bb_middle': '#00d4ff',
    'bb_lower': 'rgba(0, 212, 255, 0.3)',
    'bb_fill': 'rgba(0, 212, 255, 0.05)',
    
    # Indicators
    'rsi': '#a855f7',
    'macd_line': '#00d4ff',
    'macd_signal': '#ff6b35',
    'macd_hist_positive': '#00ff88',
    'macd_hist_negative': '#ff4757',
    'vwap': '#ffc107',
    
    # Grid & Axes
    'grid': '#1e2a38',
    'axis_line': '#30363d',
    'axis_text': '#8b949e',
}

# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL COLORS - For trading signals display
# ═══════════════════════════════════════════════════════════════════════════════
SIGNAL_COLORS = {
    'buy': '#00ff88',
    'sell': '#ff4757',
    'neutral': '#ffc107',
    'overbought': '#ff4757',
    'oversold': '#00ff88',
    'bullish': '#00ff88',
    'bearish': '#ff4757',
}

# ═══════════════════════════════════════════════════════════════════════════════
# STATUS COLORS - For system status indicators
# ═══════════════════════════════════════════════════════════════════════════════
STATUS_COLORS = {
    'live': '#00ff88',
    'updating': '#ffc107',
    'offline': '#ff4444',
    'idle': '#00ff88',
    'warning': '#ffc107',
    'danger': '#ff4444',
}

# ═══════════════════════════════════════════════════════════════════════════════
# PLOTLY LAYOUT CONFIG - Reusable layout settings
# ═══════════════════════════════════════════════════════════════════════════════
PLOTLY_LAYOUT = {
    'template': 'plotly_dark',
    'paper_bgcolor': PALETTE['bg_primary'],
    'plot_bgcolor': PALETTE['bg_secondary'],
    'font_color': PALETTE['text_primary'],
    'title_font_color': PALETTE['text_primary'],
    'legend_bgcolor': 'rgba(0,0,0,0)',
    'legend_font_color': PALETTE['text_muted'],
    'grid_color': CHART_COLORS['grid'],
    'axis_line_color': CHART_COLORS['axis_line'],
    'axis_text_color': CHART_COLORS['axis_text'],
}

# ═══════════════════════════════════════════════════════════════════════════════
# CSS HELPERS - For generating inline styles
# ═══════════════════════════════════════════════════════════════════════════════
def get_gradient(color1: str, color2: str, angle: int = 135) -> str:
    """Generate CSS linear gradient"""
    return f"linear-gradient({angle}deg, {color1} 0%, {color2} 100%)"

def get_glow(color: str, intensity: int = 20) -> str:
    """Generate CSS box shadow glow effect"""
    return f"0 0 {intensity}px {color}"

def rgba(hex_color: str, alpha: float) -> str:
    """Convert hex color to rgba"""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"
