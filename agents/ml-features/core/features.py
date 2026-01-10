"""
📊 Feature Calculator - ML Feature Engineering

Computes all features from OHLCV data for ML training:
- Asset-level features (trend, volatility, volume)
- Context features (regime detection)
- Market features (BTC/ETH correlation)

All features are computed on rolling windows with NO LOOKAHEAD.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FeatureCalculator:
    """
    Feature calculator for ML training pipeline.
    
    Computes features from OHLCV data using only past information
    to avoid lookahead bias.
    """
    
    def __init__(self, normalize: bool = True, norm_window: int = 100):
        """
        Initialize feature calculator.
        
        Args:
            normalize: Whether to z-score normalize features
            norm_window: Rolling window for normalization
        """
        self.normalize = normalize
        self.norm_window = norm_window
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TREND / MOMENTUM FEATURES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def compute_returns(self, df: pd.DataFrame, windows: List[int]) -> pd.DataFrame:
        """Compute log returns over various windows"""
        features = pd.DataFrame(index=df.index)
        
        for w in windows:
            features[f'return_{w}'] = np.log(df['close'] / df['close'].shift(w))
        
        return features
    
    def compute_ema(self, df: pd.DataFrame, spans: List[int]) -> pd.DataFrame:
        """Compute EMA values and distances"""
        features = pd.DataFrame(index=df.index)
        
        for span in spans:
            ema = df['close'].ewm(span=span, adjust=False).mean()
            features[f'ema_{span}'] = ema
            # Distance from EMA as percentage
            features[f'ema_dist_{span}'] = (df['close'] - ema) / ema
        
        return features
    
    def compute_ema_crossovers(
        self, 
        df: pd.DataFrame, 
        pairs: List[Tuple[int, int]]
    ) -> pd.DataFrame:
        """Compute EMA crossover signals"""
        features = pd.DataFrame(index=df.index)
        
        for fast, slow in pairs:
            ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
            ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
            
            # Crossover: 1 = golden cross, -1 = death cross, 0 = no cross
            cross = np.sign(ema_fast - ema_slow)
            features[f'ema_cross_{fast}_{slow}'] = cross
            
            # Distance between EMAs
            features[f'ema_spread_{fast}_{slow}'] = (ema_fast - ema_slow) / ema_slow
        
        return features
    
    def compute_rsi(self, df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
        """Compute RSI indicator"""
        features = pd.DataFrame(index=df.index)
        
        for period in periods:
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            
            avg_gain = gain.ewm(span=period, adjust=False).mean()
            avg_loss = loss.ewm(span=period, adjust=False).mean()
            
            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            
            features[f'rsi_{period}'] = rsi
        
        return features
    
    def compute_macd(
        self, 
        df: pd.DataFrame, 
        params: List[Tuple[int, int, int]]
    ) -> pd.DataFrame:
        """Compute MACD indicator"""
        features = pd.DataFrame(index=df.index)
        
        for fast, slow, signal in params:
            ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
            ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
            
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()
            histogram = macd_line - signal_line
            
            # Normalize by price
            features[f'macd_{fast}_{slow}'] = macd_line / df['close']
            features[f'macd_signal_{fast}_{slow}_{signal}'] = signal_line / df['close']
            features[f'macd_hist_{fast}_{slow}_{signal}'] = histogram / df['close']
        
        return features
    
    def compute_adx(self, df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
        """Compute ADX (Average Directional Index) for trend strength"""
        features = pd.DataFrame(index=df.index)
        
        for period in periods:
            high = df['high']
            low = df['low']
            close = df['close']
            
            # True Range
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Directional Movement
            up_move = high - high.shift(1)
            down_move = low.shift(1) - low
            
            plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
            minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)
            
            # Smoothed averages
            atr = tr.ewm(span=period, adjust=False).mean()
            plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
            minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
            
            # ADX
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
            adx = dx.ewm(span=period, adjust=False).mean()
            
            features[f'adx_{period}'] = adx / 100  # Normalize to 0-1
            features[f'plus_di_{period}'] = plus_di / 100
            features[f'minus_di_{period}'] = minus_di / 100
        
        return features
    
    # ═══════════════════════════════════════════════════════════════════════════
    # VOLATILITY FEATURES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def compute_atr(self, df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
        """Compute ATR and ATR percentage"""
        features = pd.DataFrame(index=df.index)
        
        for period in periods:
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            atr = tr.ewm(span=period, adjust=False).mean()
            
            features[f'atr_{period}'] = atr
            features[f'atr_pct_{period}'] = atr / close  # Percentage of price
        
        return features
    
    def compute_volatility(self, df: pd.DataFrame, windows: List[int]) -> pd.DataFrame:
        """Compute return volatility (std dev)"""
        features = pd.DataFrame(index=df.index)
        
        log_returns = np.log(df['close'] / df['close'].shift(1))
        
        for w in windows:
            features[f'volatility_{w}'] = log_returns.rolling(w).std()
        
        return features
    
    def compute_bbands(self, df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
        """Compute Bollinger Bands features"""
        features = pd.DataFrame(index=df.index)
        
        for period in periods:
            sma = df['close'].rolling(period).mean()
            std = df['close'].rolling(period).std()
            
            upper = sma + 2 * std
            lower = sma - 2 * std
            
            # Width as percentage
            features[f'bb_width_{period}'] = (upper - lower) / sma
            # Position within bands (0 = lower, 1 = upper)
            features[f'bb_position_{period}'] = (df['close'] - lower) / (upper - lower)
        
        return features
    
    def compute_range(self, df: pd.DataFrame, windows: List[int]) -> pd.DataFrame:
        """Compute price range as percentage"""
        features = pd.DataFrame(index=df.index)
        
        for w in windows:
            if w == 1:
                features['range_pct_1'] = (df['high'] - df['low']) / df['close']
            else:
                high_max = df['high'].rolling(w).max()
                low_min = df['low'].rolling(w).min()
                features[f'range_pct_{w}'] = (high_max - low_min) / df['close']
        
        return features
    
    # ═══════════════════════════════════════════════════════════════════════════
    # VOLUME FEATURES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def compute_volume_features(self, df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
        """Compute volume-based features"""
        features = pd.DataFrame(index=df.index)
        
        for period in periods:
            vol_sma = df['volume'].rolling(period).mean()
            
            features[f'volume_sma_{period}'] = vol_sma
            features[f'volume_ratio_{period}'] = df['volume'] / vol_sma
            
            # Log volume ratio (more stable)
            features[f'log_volume_ratio_{period}'] = np.log1p(df['volume'] / vol_sma)
        
        return features
    
    def compute_obv(self, df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
        """Compute On-Balance Volume and its slope"""
        features = pd.DataFrame(index=df.index)
        
        # OBV calculation
        price_change = df['close'].diff()
        obv = (np.sign(price_change) * df['volume']).cumsum()
        
        for period in periods:
            # OBV slope (normalized)
            obv_sma = obv.rolling(period).mean()
            features[f'obv_slope_{period}'] = (obv - obv_sma) / obv_sma.abs().replace(0, 1)
        
        return features
    
    def compute_vwap_distance(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute distance from VWAP"""
        features = pd.DataFrame(index=df.index)
        
        # Typical price
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        
        # VWAP (session-based, approximated with rolling)
        vwap = (typical_price * df['volume']).rolling(20).sum() / df['volume'].rolling(20).sum()
        
        features['vwap_dist'] = (df['close'] - vwap) / vwap
        
        return features
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRICE ACTION FEATURES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def compute_candle_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute candlestick-based features"""
        features = pd.DataFrame(index=df.index)
        
        body = abs(df['close'] - df['open'])
        total_range = df['high'] - df['low']
        
        # Avoid division by zero
        total_range = total_range.replace(0, np.nan)
        
        # Body percentage
        features['candle_body_pct'] = body / total_range
        
        # Shadow percentages
        upper_shadow = df['high'] - df[['open', 'close']].max(axis=1)
        lower_shadow = df[['open', 'close']].min(axis=1) - df['low']
        
        features['upper_shadow_pct'] = upper_shadow / total_range
        features['lower_shadow_pct'] = lower_shadow / total_range
        
        # Direction
        features['candle_direction'] = np.sign(df['close'] - df['open'])
        
        # Gap from previous close
        features['gap_pct'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        
        return features
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONTEXT FEATURES (Regime Detection)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def compute_percentile_rank(
        self, 
        series: pd.Series, 
        window: int
    ) -> pd.Series:
        """Compute rolling percentile rank (0-1)"""
        def percentile_rank(x):
            if len(x) < 2:
                return 0.5
            return (x.values[:-1] < x.values[-1]).sum() / (len(x) - 1)
        
        return series.rolling(window).apply(percentile_rank, raw=False)
    
    def compute_regime_features(
        self, 
        df: pd.DataFrame, 
        windows: List[int]
    ) -> pd.DataFrame:
        """Compute market regime features"""
        features = pd.DataFrame(index=df.index)
        
        log_returns = np.log(df['close'] / df['close'].shift(1))
        volatility = log_returns.rolling(20).std()
        
        for w in windows:
            # Volatility percentile (internal use only)
            vol_pct = self.compute_percentile_rank(volatility, w)
            
            # Volatility regime (categorical encoded)
            features[f'vol_regime_{w}'] = pd.cut(
                vol_pct, 
                bins=[0, 0.33, 0.66, 1.0], 
                labels=[0, 1, 2],  # Low, Medium, High
                include_lowest=True
            ).astype(float)
        
        return features
    
    def compute_speed_acceleration(
        self, 
        df: pd.DataFrame, 
        windows: List[int]
    ) -> pd.DataFrame:
        """Compute speed and acceleration of price movement"""
        features = pd.DataFrame(index=df.index)
        
        log_returns = np.log(df['close'] / df['close'].shift(1))
        
        for w in windows:
            # Speed: rate of change of returns
            speed = log_returns.rolling(w).mean()
            features[f'speed_{w}'] = speed
            
            # Acceleration: rate of change of speed
            features[f'acceleration_{w}'] = speed.diff(w)
        
        return features
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN COMPUTATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def compute_all_features(
        self, 
        df: pd.DataFrame,
        feature_config: Optional[Dict] = None
    ) -> pd.DataFrame:
        """
        Compute all features for a single asset.
        
        Args:
            df: OHLCV DataFrame with columns [open, high, low, close, volume]
            feature_config: Optional custom feature configuration
        
        Returns:
            DataFrame with all computed features
        """
        from config import ASSET_FEATURES, CONTEXT_FEATURES, ALL_WINDOWS
        
        if feature_config is None:
            feature_config = ASSET_FEATURES
        
        all_features = []
        
        # Trend features
        trend_config = feature_config.get('trend', {})
        if 'returns' in trend_config:
            all_features.append(self.compute_returns(df, trend_config['returns']))
        if 'ema' in trend_config:
            all_features.append(self.compute_ema(df, trend_config['ema']))
        if 'ema_cross' in trend_config:
            all_features.append(self.compute_ema_crossovers(df, trend_config['ema_cross']))
        if 'rsi' in trend_config:
            all_features.append(self.compute_rsi(df, trend_config['rsi']))
        if 'macd' in trend_config:
            all_features.append(self.compute_macd(df, trend_config['macd']))
        if 'adx' in trend_config:
            all_features.append(self.compute_adx(df, trend_config['adx']))
        
        # Volatility features
        vol_config = feature_config.get('volatility', {})
        if 'atr' in vol_config:
            all_features.append(self.compute_atr(df, vol_config['atr']))
        if 'std_returns' in vol_config:
            all_features.append(self.compute_volatility(df, vol_config['std_returns']))
        if 'bbands_width' in vol_config:
            all_features.append(self.compute_bbands(df, vol_config['bbands_width']))
        if 'range_pct' in vol_config:
            all_features.append(self.compute_range(df, vol_config['range_pct']))
        
        # Volume features
        vol_config = feature_config.get('volume', {})
        if 'volume_sma' in vol_config or 'volume_ratio' in vol_config:
            all_features.append(self.compute_volume_features(df, vol_config.get('volume_sma', [20])))
        if 'obv_slope' in vol_config:
            all_features.append(self.compute_obv(df, vol_config['obv_slope']))
        if 'vwap_distance' in vol_config:
            all_features.append(self.compute_vwap_distance(df))
        
        # Price action features
        if 'price_action' in feature_config:
            all_features.append(self.compute_candle_features(df))
        
        # Context features - vol_regime only
        regime_windows = CONTEXT_FEATURES.get('vol_regime', [100])
        all_features.append(self.compute_regime_features(df, regime_windows))
        
        # Combine all features
        features_df = pd.concat(all_features, axis=1)
        
        # Normalize if requested
        if self.normalize:
            features_df = self.normalize_features(features_df)
        
        return features_df
    
    def normalize_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply rolling z-score normalization"""
        normalized = pd.DataFrame(index=df.index)
        
        for col in df.columns:
            # Skip categorical/binary features
            if df[col].nunique() <= 5:
                normalized[col] = df[col]
            else:
                mean = df[col].rolling(self.norm_window, min_periods=20).mean()
                std = df[col].rolling(self.norm_window, min_periods=20).std()
                normalized[col] = (df[col] - mean) / std.replace(0, 1)
        
        return normalized
    
    def get_feature_names(self) -> List[str]:
        """Get list of all feature names that will be computed"""
        # This would be computed from config
        from config import ASSET_FEATURES, CONTEXT_FEATURES
        
        names = []
        
        for category, features in ASSET_FEATURES.items():
            for feat_name, windows in features.items():
                for w in windows:
                    if isinstance(w, tuple):
                        names.append(f"{feat_name}_{'_'.join(map(str, w))}")
                    else:
                        names.append(f"{feat_name}_{w}")
        
        return names
