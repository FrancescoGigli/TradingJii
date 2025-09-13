#data_utils.py
import pandas as pd
import numpy as np
import logging
from ta import momentum, trend, volatility, volume
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice
from ta.momentum import StochRSIIndicator
from ta.volume import OnBalanceVolumeIndicator

from config import EXPECTED_COLUMNS
from core.symbol_exclusion_manager import global_symbol_exclusion_manager

# Minimum dataset size requirements for reliable calculations
MIN_DATASET_SIZE = 50  # Minimum candles needed for reliable technical indicators
MIN_ROLLING_PERIODS = {'ema20': 20, 'bollinger': 20, 'atr': 14, 'adx': 14, 'vwap': 14}

def validate_dataset_size(df, symbol=None):
    """
    Validates that the dataset has enough data for reliable indicator calculations.
    Auto-excludes symbols with insufficient data.
    
    Args:
        df (pd.DataFrame): Input DataFrame to validate
        symbol (str, optional): Symbol name for logging
        
    Returns:
        bool: True if dataset is valid, False otherwise
    """
    symbol_info = f" for {symbol}" if symbol else ""
    
    if len(df) < MIN_DATASET_SIZE:
        logging.error(f"❌ Dataset too small{symbol_info}: {len(df)} candles < {MIN_DATASET_SIZE} minimum required")
        
        # 🔧 AUTO-EXCLUDE: Aggiunge simbolo alla lista degli esclusi
        if symbol and global_symbol_exclusion_manager:
            global_symbol_exclusion_manager.exclude_symbol_insufficient_data(
                symbol, 
                missing_timeframes=None, 
                candle_count=len(df)
            )
        
        return False
        
    # Check if we have enough data for the most demanding indicators
    max_required = max(MIN_ROLLING_PERIODS.values())
    if len(df) < max_required:
        logging.warning(f"Dataset{symbol_info} may be too small for reliable indicators: {len(df)} candles < {max_required} recommended")
        
    return True

def add_technical_indicators(df, symbol=None):
    """
    Adds technical indicators with improved error handling and no lookahead bias.
    
    Fixes:
    - Consolidated volatility calculation (no more duplication)
    - Better error handling with correction statistics
    - Time-aware NaN handling without lookahead bias
    - Dataset size validation
    
    Args:
        df (pd.DataFrame): DataFrame with OHLCV data
        symbol (str, optional): Symbol name for logging
        
    Returns:
        pd.DataFrame: DataFrame with technical indicators
    """
    symbol_info = f" for {symbol}" if symbol else ""
    
    # Validate dataset size first
    if not validate_dataset_size(df, symbol):
        raise ValueError(f"Dataset{symbol_info} too small for reliable indicator calculations")
    
    correction_stats = {'indicators_failed': 0, 'nan_corrections': {}}
    
    # === MEDIE MOBILI ESPONENZIALI (3) ===
    try:
        df['ema5'] = EMAIndicator(df['close'], window=5).ema_indicator()
        df['ema10'] = EMAIndicator(df['close'], window=10).ema_indicator()
        df['ema20'] = EMAIndicator(df['close'], window=20).ema_indicator()
    except Exception as e:
        correction_stats['indicators_failed'] += 1
        df['ema5'] = df['ema10'] = df['ema20'] = df['close']  # Use close price as fallback
        logging.warning(f"Failed to calculate EMA{symbol_info}. Error: {e}. Using close price as fallback.")

    # === MACD (3) ===
    try:
        macd = MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
    except Exception as e:
        correction_stats['indicators_failed'] += 1
        df['macd'] = df['macd_signal'] = df['macd_histogram'] = 0.0
        logging.warning(f"Failed to calculate MACD{symbol_info}. Error: {e}. Defaulting to 0.0.")

    # === OSCILLATORI MOMENTUM (2) ===
    try:
        df['rsi_fast'] = momentum.RSIIndicator(df['close'], window=7).rsi()
    except Exception as e:
        correction_stats['indicators_failed'] += 1
        df['rsi_fast'] = 50.0
        logging.warning(f"Failed to calculate RSI{symbol_info}. Error: {e}. Defaulting to neutral 50.0.")

    try:
        df['stoch_rsi'] = StochRSIIndicator(df['close'], window=14).stochrsi()
    except Exception as e:
        correction_stats['indicators_failed'] += 1
        df['stoch_rsi'] = 0.5
        logging.warning(f"Failed to calculate Stoch RSI{symbol_info}. Error: {e}. Defaulting to 0.5.")

    # === VOLATILITÀ (4 - INCLUDING CONSOLIDATED VOLATILITY) ===
    try:
        df['atr'] = AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()
    except Exception as e:
        correction_stats['indicators_failed'] += 1
        # Use high-low range as ATR fallback
        df['atr'] = (df['high'] - df['low']).rolling(14, min_periods=1).mean()
        logging.warning(f"Failed to calculate ATR{symbol_info}. Error: {e}. Using high-low range as fallback.")

    try:
        bollinger = BollingerBands(df['close'], window=20, window_dev=2)
        df['bollinger_hband'] = bollinger.bollinger_hband()
        df['bollinger_lband'] = bollinger.bollinger_lband()
    except Exception as e:
        correction_stats['indicators_failed'] += 1
        # Use simple moving average +/- 2 standard deviations as fallback
        sma20 = df['close'].rolling(20, min_periods=1).mean()
        std20 = df['close'].rolling(20, min_periods=1).std()
        df['bollinger_hband'] = sma20 + (2 * std20)
        df['bollinger_lband'] = sma20 - (2 * std20)
        logging.warning(f"Failed to calculate Bollinger Bands{symbol_info}. Error: {e}. Using simple MA +/- 2 std as fallback.")

    # === CONSOLIDATED VOLATILITY CALCULATION (FIXED DUPLICATION) ===
    try:
        df['volatility'] = df['close'].pct_change() * 100  # Convert to percentage
        df['volatility'] = df['volatility'].replace([np.inf, -np.inf], 0.0)
        df['volatility'] = df['volatility'].clip(-100, 100)  # Clip extreme values
    except Exception as e:
        correction_stats['indicators_failed'] += 1
        df['volatility'] = 0.0
        logging.warning(f"Failed to calculate volatility{symbol_info}. Error: {e}. Defaulting to 0.0.")

    # === VOLUME (2) ===
    try:
        df['vwap'] = VolumeWeightedAveragePrice(df['high'], df['low'], df['close'], df['volume'], window=14).volume_weighted_average_price()
    except Exception as e:
        correction_stats['indicators_failed'] += 1
        df['vwap'] = df['close']  # Use close price as fallback
        logging.warning(f"Failed to calculate VWAP{symbol_info}. Error: {e}. Using close price as fallback.")

    try:
        df['obv'] = OnBalanceVolumeIndicator(df['close'], df['volume']).on_balance_volume()
    except Exception as e:
        correction_stats['indicators_failed'] += 1
        df['obv'] = df['volume'].cumsum()  # Use cumulative volume as fallback
        logging.warning(f"Failed to calculate OBV{symbol_info}. Error: {e}. Using cumulative volume as fallback.")

    # === FORZA TREND (1) ===
    try:
        df['adx'] = ADXIndicator(df['high'], df['low'], df['close'], window=14).adx()
    except Exception as e:
        correction_stats['indicators_failed'] += 1
        df['adx'] = 25.0  # Neutral ADX value
        logging.warning(f"Failed to calculate ADX{symbol_info}. Error: {e}. Defaulting to neutral 25.0.")

    # === AGGRESSIVE NaN AND INFINITE HANDLING ===
    # Handle NaN and infinite values more aggressively to ensure finite data
    for col in ['ema5', 'ema10', 'ema20', 'macd', 'macd_signal', 'macd_histogram', 
                'rsi_fast', 'stoch_rsi', 'atr', 'bollinger_hband', 'bollinger_lband',
                'volatility', 'vwap', 'obv', 'adx']:
        if col in df.columns:
            nan_count_before = df[col].isna().sum()
            inf_count_before = np.isinf(df[col]).sum()
            
            # Step 1: Forward fill NaN values (no lookahead bias)
            df[col] = df[col].ffill()
            
            # Step 2: For remaining NaN (at the beginning), use meaningful defaults
            if col in ['rsi_fast']:
                df[col] = df[col].fillna(50.0)  # Neutral RSI
            elif col in ['stoch_rsi']:
                df[col] = df[col].fillna(0.5)  # Neutral stoch RSI
            elif col in ['adx']:
                df[col] = df[col].fillna(25.0)  # Neutral ADX
            elif col in ['ema5', 'ema10', 'ema20', 'vwap', 'bollinger_hband', 'bollinger_lband']:
                df[col] = df[col].fillna(df['close'].iloc[0])  # Use first close price
            else:
                df[col] = df[col].fillna(0.0)  # Default to zero
            
            # Step 3: Replace infinite values
            df[col] = df[col].replace([np.inf, -np.inf], 0.0)
            
            # Step 4: Final safety check - ensure all values are finite
            if not np.isfinite(df[col]).all():
                logging.warning(f"Still non-finite values in {col}, forcing to 0.0")
                df[col] = np.where(np.isfinite(df[col]), df[col], 0.0)
            
            nan_count_after = df[col].isna().sum()
            inf_count_after = np.isinf(df[col]).sum()
            
            if nan_count_before > 0 or inf_count_before > 0:
                correction_stats['nan_corrections'][col] = {
                    'nan_before': int(nan_count_before),
                    'nan_after': int(nan_count_after), 
                    'inf_before': int(inf_count_before),
                    'inf_after': int(inf_count_after),
                    'corrected': int((nan_count_before + inf_count_before) - (nan_count_after + inf_count_after))
                }
    
    # Add swing probability features (no lookahead bias)
    df = add_swing_probability_features(df)
    
    # Log only critical correction statistics (simplified)
    if correction_stats['indicators_failed'] > 0:
        logging.warning(f"⚠️ {correction_stats['indicators_failed']} indicators failed{symbol_info}")
    
    # Count total corrections without verbose details
    total_corrections = sum(stats.get('corrected', 0) for stats in correction_stats['nan_corrections'].values())
    if total_corrections > 0:
        logging.debug(f"🔧 {total_corrections} NaN/Inf values corrected{symbol_info}")
    
    # Verify all expected columns are present
    missing_cols = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing_cols:
        logging.warning(f"Missing expected columns{symbol_info}: {missing_cols}")
        for col in missing_cols:
            df[col] = 0.0
    
    # Select only expected columns and round to reduce precision noise
    return df[EXPECTED_COLUMNS].round(6)

def prepare_data(df):
    """
    Prepares data by adding technical indicators.
    
    FIXED: Removed duplicate volatility calculation - now handled by add_technical_indicators()
    
    Args:
        df (pd.DataFrame): DataFrame with OHLCV data
        
    Returns:
        np.ndarray: Array with all expected features
    """
    required_initial = ['open', 'high', 'low', 'close', 'volume']
    for col in required_initial:
        if col not in df.columns:
            raise ValueError(f"Column {col} missing in input data.")
    
    # Add all technical indicators including volatility (consolidated)
    df_with_indicators = add_technical_indicators(df)
    
    # Ensure all expected columns are present (should already be handled by add_technical_indicators)
    for col in EXPECTED_COLUMNS:
        if col not in df_with_indicators.columns:
            df_with_indicators[col] = 0.0
            logging.warning(f"Missing expected column {col} - added with default value 0.0")
    
    return df_with_indicators[EXPECTED_COLUMNS].values

def add_swing_probability_features(df):
    """
    Aggiunge features che stimano la probabilità di swing senza lookahead bias.
    Queste features possono essere calcolate in real-time durante il live trading.
    
    Args:
        df (pd.DataFrame): DataFrame con indicatori tecnici già calcolati
        
    Returns:
        pd.DataFrame: DataFrame con swing probability features aggiunte
    """
    try:
        # 1. Price Position in Range (5, 10, 20 periodi)
        for period in [5, 10, 20]:
            high_max = df['high'].rolling(period).max()
            low_min = df['low'].rolling(period).min()
            range_size = high_max - low_min
            # Evita divisione per zero
            df[f'price_pos_{period}'] = np.where(
                range_size > 0, 
                (df['close'] - low_min) / range_size,
                0.5  # Posizione neutra se range = 0
            )
        
        # 2. Volume Acceleration (surge detection)
        vol_ma3 = df['volume'].rolling(3).mean()
        vol_ma10 = df['volume'].rolling(10).mean()
        df['vol_acceleration'] = np.where(
            vol_ma10 > 0,
            vol_ma3 / vol_ma10,
            1.0  # Neutro se denominatore = 0
        )
        
        # 3. ATR-Normalized Movement (current vs previous)
        price_change = df['close'] - df['close'].shift(1)
        df['atr_norm_move'] = np.where(
            df['atr'] > 0,
            price_change / df['atr'],
            0.0  # Zero se ATR = 0
        )
        
        # 4. Momentum Divergence (RSI vs Price)
        price_roc = df['close'].pct_change(periods=5) * 100
        rsi_roc = df['rsi_fast'].diff(periods=5)
        df['momentum_divergence'] = price_roc - rsi_roc
        
        # 5. Volatility Squeeze Indicator
        bb_width = df['bollinger_hband'] - df['bollinger_lband'] 
        df['volatility_squeeze'] = np.where(
            df['close'] > 0,
            bb_width / df['close'],
            0.0  # Zero se close = 0
        )
        
        # 6. Support/Resistance Proximity
        # Calcola distanza da livelli di supporto/resistenza recenti
        for period in [10, 20]:
            high_level = df['high'].rolling(period).max()
            low_level = df['low'].rolling(period).min()
            
            # Distanza dal resistance (negativa se sopra)
            df[f'resistance_dist_{period}'] = (high_level - df['close']) / df['close']
            
            # Distanza dal support (positiva se sopra)  
            df[f'support_dist_{period}'] = (df['close'] - low_level) / df['close']
        
        # 7. Price Velocity (accelerazione del prezzo)
        price_velocity = df['close'].diff()
        df['price_acceleration'] = price_velocity.diff()
        
        # 8. Volume-Price Trend Alignment
        price_trend = df['close'] > df['close'].shift(1)
        volume_trend = df['volume'] > df['volume'].rolling(3).mean()
        df['vol_price_alignment'] = (price_trend == volume_trend).astype(float)
        
        # Gestione NaN e infiniti
        swing_features = [
            'price_pos_5', 'price_pos_10', 'price_pos_20',
            'vol_acceleration', 'atr_norm_move', 'momentum_divergence',
            'volatility_squeeze', 'resistance_dist_10', 'resistance_dist_20',
            'support_dist_10', 'support_dist_20', 'price_acceleration',
            'vol_price_alignment'
        ]
        
        for feature in swing_features:
            if feature in df.columns:
                # Replace inf/-inf with 0
                df[feature] = df[feature].replace([np.inf, -np.inf], 0.0)
                # Forward/backward fill NaN
                df[feature] = df[feature].fillna(0.0)
                # Clip extreme values
                df[feature] = df[feature].clip(-10, 10)
    
    except Exception as e:
        logging.error(f"Error calculating swing probability features: {e}")
        # Fallback: crea features dummy
        swing_features = [
            'price_pos_5', 'price_pos_10', 'price_pos_20',
            'vol_acceleration', 'atr_norm_move', 'momentum_divergence',
            'volatility_squeeze', 'resistance_dist_10', 'resistance_dist_20',
            'support_dist_10', 'support_dist_20', 'price_acceleration',
            'vol_price_alignment'
        ]
        for feature in swing_features:
            df[feature] = 0.0
    
    return df
