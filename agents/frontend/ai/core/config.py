"""
AI & Backtest Configuration
Centralized configuration for all AI/Backtest related settings
"""

# ============================================================
# AI CONFIGURATION (General)
# ============================================================
AI_CONFIG = {
    # Visualization settings
    'visualization': {
        'chart_height': 300,
        'equity_curve_color': '#00ff88',
        'drawdown_color': '#ff4757',
        'profit_color': '#00ff88',
        'loss_color': '#ff4757',
    }
}

# ============================================================
# BACKTEST CONFIGURATION
# ============================================================
BACKTEST_CONFIG = {
    # Entry/Exit thresholds (molto bassi per generare trade anche con poca volatilità)
    'entry_threshold': 25,          # |score| > 25 to open position
    'exit_threshold': 10,           # opposite score > 10 to close
    'min_holding_candles': 2,       # minimum candles before exit
    
    # Indicator weights (must sum to 1.0)
    'weights': {
        'rsi': 0.333,
        'macd': 0.333,
        'bollinger': 0.334
    },
    
    # RSI parameters
    'rsi': {
        'period': 14,
        'oversold': 30,     # Below this = LONG signal
        'overbought': 70,   # Above this = SHORT signal
    },
    
    # MACD parameters
    'macd': {
        'fast': 12,
        'slow': 26,
        'signal': 9,
        'max_diff_pct': 0.5,  # Max diff % for full score
    },
    
    # Bollinger Bands parameters
    'bollinger': {
        'period': 20,
        'std_dev': 2,
    },
    
    # Colors for visualization
    'colors': {
        # Entry markers
        'long_entry': '#00ff88',
        'short_entry': '#ff4757',
        'long_entry_marker': 'triangle-up',
        'short_entry_marker': 'triangle-down',
        
        # Exit markers
        'exit_profit': '#00cc6a',
        'exit_loss': '#cc3d4a',
        
        # Trade lines
        'profit_line': 'rgba(0, 255, 136, 0.4)',
        'loss_line': 'rgba(255, 71, 87, 0.4)',
        
        # Confidence bar
        'confidence_positive': '#00ff88',
        'confidence_negative': '#ff4757',
        'confidence_neutral': '#6c757d',
        
        # Background zones
        'long_zone': 'rgba(0, 255, 136, 0.05)',
        'short_zone': 'rgba(255, 71, 87, 0.05)',
    },
    
    # Marker sizes
    'markers': {
        'entry_size': 15,
        'exit_size': 12,
    }
}

# ============================================================
# CONFIDENCE SCORE THRESHOLDS
# ============================================================
CONFIDENCE_LEVELS = {
    'very_strong_long': {'min': 80, 'max': 100, 'label': '🟢 Very Strong LONG', 'color': '#00ff88'},
    'strong_long': {'min': 60, 'max': 80, 'label': '🟢 Strong LONG', 'color': '#00cc6a'},
    'weak_long': {'min': 30, 'max': 60, 'label': '🟡 Weak LONG', 'color': '#7dcea0'},
    'neutral': {'min': -30, 'max': 30, 'label': '⚪ Neutral', 'color': '#6c757d'},
    'weak_short': {'min': -60, 'max': -30, 'label': '🟡 Weak SHORT', 'color': '#f1948a'},
    'strong_short': {'min': -80, 'max': -60, 'label': '🔴 Strong SHORT', 'color': '#cc3d4a'},
    'very_strong_short': {'min': -100, 'max': -80, 'label': '🔴 Very Strong SHORT', 'color': '#ff4757'},
}


def get_confidence_level(score: float) -> dict:
    """Get confidence level info for a given score"""
    for level_name, level_info in CONFIDENCE_LEVELS.items():
        if level_info['min'] <= score <= level_info['max']:
            return {'name': level_name, **level_info}
    return CONFIDENCE_LEVELS['neutral']
