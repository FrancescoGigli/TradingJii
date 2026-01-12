"""
⚙️ ML Feature Engineering Configuration

Defines all feature parameters for the ML training pipeline.
Features are computed on rolling windows from historical OHLCV data.
"""

import os

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE PATHS
# ═══════════════════════════════════════════════════════════════════════════════
SHARED_DATA_PATH = os.environ.get('SHARED_DATA_PATH', '/app/shared')
DB_PATH = os.path.join(SHARED_DATA_PATH, 'data_cache', 'trading_data.db')

# ═══════════════════════════════════════════════════════════════════════════════
# TIMEFRAME SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
PRIMARY_TIMEFRAME = '15m'      # Main operational timeframe
CONTEXT_TIMEFRAME = '1h'       # Higher timeframe for context

# Market context symbols
MARKET_SYMBOLS = ['BTC/USDT:USDT', 'ETH/USDT:USDT']

# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE WINDOWS (in candles for PRIMARY_TIMEFRAME)
# ═══════════════════════════════════════════════════════════════════════════════
FEATURE_WINDOWS = {
    # Short-term
    'short': [5, 10, 20],
    # Medium-term  
    'medium': [50, 100],
    # Long-term
    'long': [200]
}

# All windows combined for iteration
ALL_WINDOWS = [5, 10, 20, 50, 100, 200]

# ═══════════════════════════════════════════════════════════════════════════════
# ASSET-LEVEL FEATURES
# ═══════════════════════════════════════════════════════════════════════════════
ASSET_FEATURES = {
    # Trend/Momentum features
    'trend': {
        'returns': ALL_WINDOWS,           # Log returns over window
        'ema': [20, 50, 200],             # EMA values
        'ema_cross': [(20, 50), (50, 200)],  # EMA crossover signals
        'rsi': [14],                       # RSI
        'macd': [(12, 26, 9)],            # MACD (fast, slow, signal)
        'adx': [14],                       # ADX for trend strength
    },
    
    # Volatility features
    'volatility': {
        'atr': [14],                       # ATR
        'atr_pct': [14],                   # ATR as % of price
        'std_returns': ALL_WINDOWS,        # Std dev of returns
        'bbands_width': [20],              # Bollinger Bands width
        'range_pct': ALL_WINDOWS,          # (High-Low)/Close
    },
    
    # Volume features
    'volume': {
        'volume_sma': [20],                # Volume SMA
        'volume_ratio': [20],              # Current vol / SMA vol
        'obv_slope': [20],                 # OBV trend
        'vwap_distance': [1],              # Distance from VWAP
    },
    
    # Price action
    'price_action': {
        'candle_body_pct': [1],            # Body / Total range
        'upper_shadow_pct': [1],           # Upper shadow / Total
        'lower_shadow_pct': [1],           # Lower shadow / Total
        'gap_pct': [1],                    # Gap from previous close
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# ASSET CONTEXT FEATURES (Normalized)
# ═══════════════════════════════════════════════════════════════════════════════
CONTEXT_FEATURES = {
    # Volatility regime
    'vol_regime': [100],                   # High/Medium/Low classification
    
    # Liquidity proxy
    'spread_estimate': [20],               # (High-Low)/Volume proxy
}

# ═══════════════════════════════════════════════════════════════════════════════
# MARKET CONTEXT FEATURES (Cross-asset)
# ═══════════════════════════════════════════════════════════════════════════════
MARKET_FEATURES = {
    # BTC/ETH returns
    'btc_return': ALL_WINDOWS,
    'eth_return': ALL_WINDOWS,
    
    # BTC/ETH volatility
    'btc_volatility': [20],
    'eth_volatility': [20],
    
    # Correlation with BTC
    'btc_correlation': [50, 100],
    
    # Market breadth (computed separately)
    'top_n_avg_return': [20],              # Avg return of top N coins
    'top_n_up_ratio': [1],                 # % of coins with positive return
}

# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-TIMEFRAME FEATURES
# ═══════════════════════════════════════════════════════════════════════════════
MTF_FEATURES = {
    # 1h timeframe features to include
    '1h': {
        'rsi': True,                        # 1h RSI
        'volume_ratio': True,              # 1h volume vs average
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# TRAILING STOP LABEL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
# These settings control label generation for ML training.
# Labels use FUTURE data (lookahead) - they are NOT features!
# 
# Formula: score = R - λ*log(1+D) - costs
# Where:
#   R = realized return from trailing stop exit
#   D = bars held until exit
#   λ = time penalty coefficient
#   costs = trading fees

TRAILING_LABEL_CONFIG = {
    # Trailing stop percentage per timeframe
    # (larger for higher timeframes to account for more volatility)
    'trailing_stop_pct': {
        '15m': 0.015,   # 1.5% trailing stop
        '1h': 0.025,    # 2.5% trailing stop
    },
    
    # Maximum bars to hold before time exit
    'max_bars': {
        '15m': 48,      # 12 hours (48 * 15m)
        '1h': 24,       # 24 hours (24 * 1h)
    },
    
    # Time penalty: penalty = λ * log(1 + bars_held)
    'time_penalty_lambda': 0.001,
    
    # Trading costs (entry + exit fees)
    'trading_cost': 0.001,  # 0.1% total
    
    # Timeframes to generate labels for
    'timeframes': ['15m', '1h'],
}

# Label column names that will be generated
LABEL_COLUMNS = {
    '15m': [
        'score_long_15m',           # Main LABEL for LONG
        'score_short_15m',          # Main LABEL for SHORT
        'realized_return_long_15m', # Diagnostics
        'realized_return_short_15m',
        'mfe_long_15m',             # Max Favorable Excursion
        'mfe_short_15m',
        'mae_long_15m',             # Max Adverse Excursion
        'mae_short_15m',
        'bars_held_long_15m',       # Duration
        'bars_held_short_15m',
        'exit_type_long_15m',       # 'trailing' or 'time'
        'exit_type_short_15m',
    ],
    '1h': [
        'score_long_1h',
        'score_short_1h',
        'realized_return_long_1h',
        'realized_return_short_1h',
        'mfe_long_1h',
        'mfe_short_1h',
        'mae_long_1h',
        'mae_short_1h',
        'bars_held_long_1h',
        'bars_held_short_1h',
        'exit_type_long_1h',
        'exit_type_short_1h',
    ],
}

# Primary labels for ML training (regression targets)
PRIMARY_LABELS = ['score_long_15m', 'score_short_15m', 'score_long_1h', 'score_short_1h']


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE GENERATION SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
# Minimum data required (warmup)
MIN_BARS_REQUIRED = 250  # Match historical-data warmup

# Feature normalization
NORMALIZE_FEATURES = True
NORMALIZATION_WINDOW = 100  # Rolling window for z-score normalization

# Feature selection
DROP_NA_ROWS = True
MAX_NA_RATIO = 0.1  # Max ratio of NaN allowed per feature

# Output
FEATURE_TABLE_NAME = 'ml_features'
FEATURE_VERSION = 'v1'

# Logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')


def get_total_feature_count():
    """Calculate approximate total number of features"""
    count = 0
    
    # Asset features
    for category, features in ASSET_FEATURES.items():
        for feat_name, windows in features.items():
            count += len(windows)
    
    # Context features
    for feat_name, windows in CONTEXT_FEATURES.items():
        count += len(windows)
    
    # Market features
    for feat_name, windows in MARKET_FEATURES.items():
        if isinstance(windows, list):
            count += len(windows)
        else:
            count += 1
    
    # MTF features
    for tf, features in MTF_FEATURES.items():
        count += len([f for f, enabled in features.items() if enabled])
    
    return count


def print_config():
    """Print feature configuration"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║           ML FEATURE ENGINEERING CONFIGURATION               ║
╠══════════════════════════════════════════════════════════════╣
║  Primary Timeframe:    {primary:<10}                         ║
║  Context Timeframe:    {context:<10}                         ║
║  Feature Windows:      {windows}                   ║
║  Estimated Features:   ~{features:<3}                                ║
╠══════════════════════════════════════════════════════════════╣
║  Min Bars Required:    {min_bars}                              ║
║  Normalize:            {normalize}                               ║
║  Norm Window:          {norm_window}                              ║
╚══════════════════════════════════════════════════════════════╝
    """.format(
        primary=PRIMARY_TIMEFRAME,
        context=CONTEXT_TIMEFRAME,
        windows=str(ALL_WINDOWS),
        features=get_total_feature_count(),
        min_bars=MIN_BARS_REQUIRED,
        normalize=NORMALIZE_FEATURES,
        norm_window=NORMALIZATION_WINDOW
    ))


if __name__ == '__main__':
    print_config()
