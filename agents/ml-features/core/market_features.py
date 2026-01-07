"""
🌐 Market Context Features

Cross-asset features that provide market context:
- BTC/ETH returns and volatility
- Correlation with BTC
- Market breadth indicators
- Top-N aggregate statistics

These features help the model understand the broader market environment.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class MarketFeatureCalculator:
    """
    Calculator for market-wide context features.
    
    Uses BTC and ETH as market proxies and computes
    cross-asset correlations and breadth indicators.
    """
    
    def __init__(self, market_symbols: List[str] = None):
        """
        Initialize market feature calculator.
        
        Args:
            market_symbols: List of market proxy symbols [BTC, ETH]
        """
        self.market_symbols = market_symbols or ['BTC/USDT:USDT', 'ETH/USDT:USDT']
    
    def compute_market_returns(
        self, 
        btc_df: pd.DataFrame, 
        eth_df: pd.DataFrame,
        windows: List[int]
    ) -> pd.DataFrame:
        """
        Compute BTC and ETH returns.
        
        Args:
            btc_df: BTC OHLCV DataFrame
            eth_df: ETH OHLCV DataFrame
            windows: List of return windows
        
        Returns:
            DataFrame with market return features
        """
        features = pd.DataFrame(index=btc_df.index)
        
        for w in windows:
            # BTC returns
            features[f'btc_return_{w}'] = np.log(
                btc_df['close'] / btc_df['close'].shift(w)
            )
            
            # ETH returns
            features[f'eth_return_{w}'] = np.log(
                eth_df['close'] / eth_df['close'].shift(w)
            )
            
            # ETH/BTC ratio change
            eth_btc_ratio = eth_df['close'] / btc_df['close']
            features[f'eth_btc_ratio_{w}'] = np.log(
                eth_btc_ratio / eth_btc_ratio.shift(w)
            )
        
        return features
    
    def compute_market_volatility(
        self, 
        btc_df: pd.DataFrame, 
        eth_df: pd.DataFrame,
        windows: List[int]
    ) -> pd.DataFrame:
        """
        Compute BTC and ETH volatility.
        
        Args:
            btc_df: BTC OHLCV DataFrame
            eth_df: ETH OHLCV DataFrame
            windows: List of volatility windows
        
        Returns:
            DataFrame with market volatility features
        """
        features = pd.DataFrame(index=btc_df.index)
        
        btc_returns = np.log(btc_df['close'] / btc_df['close'].shift(1))
        eth_returns = np.log(eth_df['close'] / eth_df['close'].shift(1))
        
        for w in windows:
            features[f'btc_volatility_{w}'] = btc_returns.rolling(w).std()
            features[f'eth_volatility_{w}'] = eth_returns.rolling(w).std()
            
            # Volatility ratio (ETH/BTC)
            features[f'vol_ratio_eth_btc_{w}'] = (
                features[f'eth_volatility_{w}'] / 
                features[f'btc_volatility_{w}'].replace(0, np.nan)
            )
        
        return features
    
    def compute_correlation_with_btc(
        self, 
        asset_df: pd.DataFrame, 
        btc_df: pd.DataFrame,
        windows: List[int]
    ) -> pd.DataFrame:
        """
        Compute rolling correlation between an asset and BTC.
        
        Args:
            asset_df: Asset OHLCV DataFrame
            btc_df: BTC OHLCV DataFrame
            windows: List of correlation windows
        
        Returns:
            DataFrame with correlation features
        """
        features = pd.DataFrame(index=asset_df.index)
        
        asset_returns = np.log(asset_df['close'] / asset_df['close'].shift(1))
        btc_returns = np.log(btc_df['close'] / btc_df['close'].shift(1))
        
        for w in windows:
            features[f'btc_corr_{w}'] = asset_returns.rolling(w).corr(btc_returns)
            
            # Beta to BTC (regression coefficient)
            cov = asset_returns.rolling(w).cov(btc_returns)
            var = btc_returns.rolling(w).var()
            features[f'btc_beta_{w}'] = cov / var.replace(0, np.nan)
        
        return features
    
    def compute_market_breadth(
        self, 
        all_returns: pd.DataFrame,
        windows: List[int]
    ) -> pd.DataFrame:
        """
        Compute market breadth indicators from all assets.
        
        Args:
            all_returns: DataFrame with returns for all assets (columns = symbols)
            windows: List of breadth windows
        
        Returns:
            DataFrame with breadth features
        """
        features = pd.DataFrame(index=all_returns.index)
        
        for w in windows:
            # Percentage of assets with positive returns
            positive_ratio = (all_returns > 0).sum(axis=1) / all_returns.shape[1]
            features[f'market_breadth_{w}'] = positive_ratio.rolling(w).mean()
            
            # Average return of all assets
            avg_return = all_returns.mean(axis=1)
            features[f'market_avg_return_{w}'] = avg_return.rolling(w).mean()
            
            # Dispersion (std of returns across assets)
            features[f'market_dispersion_{w}'] = all_returns.std(axis=1).rolling(w).mean()
            
            # Leader/laggard spread
            top_10_pct = all_returns.apply(lambda x: x.nlargest(10).mean(), axis=1)
            bottom_10_pct = all_returns.apply(lambda x: x.nsmallest(10).mean(), axis=1)
            features[f'market_spread_{w}'] = (top_10_pct - bottom_10_pct).rolling(w).mean()
        
        return features
    
    def compute_regime_indicators(
        self, 
        btc_df: pd.DataFrame,
        window: int = 100
    ) -> pd.DataFrame:
        """
        Compute market regime indicators based on BTC.
        
        Args:
            btc_df: BTC OHLCV DataFrame
            window: Window for regime detection
        
        Returns:
            DataFrame with regime features
        """
        features = pd.DataFrame(index=btc_df.index)
        
        btc_returns = np.log(btc_df['close'] / btc_df['close'].shift(1))
        btc_vol = btc_returns.rolling(20).std()
        
        # Trend regime: based on 50/200 EMA
        ema_50 = btc_df['close'].ewm(span=50, adjust=False).mean()
        ema_200 = btc_df['close'].ewm(span=200, adjust=False).mean()
        
        features['market_trend'] = np.where(
            ema_50 > ema_200, 1,  # Bull
            np.where(ema_50 < ema_200, -1, 0)  # Bear / Neutral
        )
        
        # Volatility regime based on percentile
        def percentile_rank(x):
            if len(x) < 2:
                return 0.5
            return (x.values[:-1] < x.values[-1]).sum() / (len(x) - 1)
        
        vol_pct = btc_vol.rolling(window).apply(percentile_rank, raw=False)
        
        # Classify: 0=Low, 1=Medium, 2=High
        features['market_vol_regime'] = pd.cut(
            vol_pct, 
            bins=[0, 0.33, 0.66, 1.0], 
            labels=[0, 1, 2],
            include_lowest=True
        ).astype(float)
        
        # Combined regime (trend + volatility)
        # 0: Bull Low Vol, 1: Bull High Vol, 2: Bear Low Vol, 3: Bear High Vol
        features['market_regime'] = (
            (features['market_trend'] > 0).astype(int) * 2 + 
            (features['market_vol_regime'] > 1).astype(int)
        )
        
        return features
    
    def compute_all_market_features(
        self, 
        asset_df: pd.DataFrame,
        btc_df: pd.DataFrame,
        eth_df: pd.DataFrame,
        all_returns: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Compute all market context features for an asset.
        
        Args:
            asset_df: Target asset OHLCV DataFrame
            btc_df: BTC OHLCV DataFrame
            eth_df: ETH OHLCV DataFrame
            all_returns: Optional DataFrame with returns for all assets
        
        Returns:
            DataFrame with all market features
        """
        from config import MARKET_FEATURES, ALL_WINDOWS
        
        all_features = []
        
        # Market returns
        return_windows = MARKET_FEATURES.get('btc_return', ALL_WINDOWS)
        all_features.append(
            self.compute_market_returns(btc_df, eth_df, return_windows)
        )
        
        # Market volatility
        vol_windows = MARKET_FEATURES.get('btc_volatility', [20])
        all_features.append(
            self.compute_market_volatility(btc_df, eth_df, vol_windows)
        )
        
        # Correlation with BTC
        corr_windows = MARKET_FEATURES.get('btc_correlation', [50, 100])
        all_features.append(
            self.compute_correlation_with_btc(asset_df, btc_df, corr_windows)
        )
        
        # Regime indicators
        all_features.append(
            self.compute_regime_indicators(btc_df)
        )
        
        # Market breadth (if all returns provided)
        if all_returns is not None:
            breadth_windows = MARKET_FEATURES.get('top_n_avg_return', [20])
            all_features.append(
                self.compute_market_breadth(all_returns, breadth_windows)
            )
        
        # Combine all features
        features_df = pd.concat(all_features, axis=1)
        
        # Align index with asset
        features_df = features_df.reindex(asset_df.index)
        
        return features_df


class MultiTimeframeFeatures:
    """
    Compute features from multiple timeframes.
    
    Maps higher timeframe features to lower timeframe timestamps.
    """
    
    def __init__(self, primary_tf: str = '15m', context_tf: str = '1h'):
        """
        Initialize MTF feature calculator.
        
        Args:
            primary_tf: Primary (lower) timeframe
            context_tf: Context (higher) timeframe
        """
        self.primary_tf = primary_tf
        self.context_tf = context_tf
    
    def map_to_primary_timeframe(
        self, 
        primary_df: pd.DataFrame,
        context_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Map context timeframe data to primary timeframe.
        
        Uses forward-fill to avoid lookahead bias.
        
        Args:
            primary_df: Primary timeframe DataFrame
            context_df: Context timeframe DataFrame
        
        Returns:
            Context features aligned to primary timeframe
        """
        # Ensure context_df index is timezone-aware if primary is
        if primary_df.index.tz is not None and context_df.index.tz is None:
            context_df = context_df.tz_localize(primary_df.index.tz)
        
        # Reindex and forward-fill (no lookahead)
        aligned = context_df.reindex(primary_df.index, method='ffill')
        
        return aligned
    
    def compute_mtf_features(
        self,
        primary_df: pd.DataFrame,
        context_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Compute features from context timeframe.
        
        Args:
            primary_df: Primary timeframe OHLCV
            context_df: Context timeframe OHLCV
        
        Returns:
            MTF features aligned to primary timeframe
        """
        from config import MTF_FEATURES
        
        features = pd.DataFrame(index=context_df.index)
        
        mtf_config = MTF_FEATURES.get(self.context_tf, {})
        
        # Trend direction (based on EMA)
        if mtf_config.get('trend_direction', False):
            ema_20 = context_df['close'].ewm(span=20, adjust=False).mean()
            ema_50 = context_df['close'].ewm(span=50, adjust=False).mean()
            features[f'{self.context_tf}_trend'] = np.sign(ema_20 - ema_50)
        
        # RSI
        if mtf_config.get('rsi', False):
            delta = context_df['close'].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.ewm(span=14, adjust=False).mean()
            avg_loss = loss.ewm(span=14, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            features[f'{self.context_tf}_rsi'] = (100 - (100 / (1 + rs)) - 50) / 50
        
        # Volume ratio
        if mtf_config.get('volume_ratio', False):
            vol_sma = context_df['volume'].rolling(20).mean()
            features[f'{self.context_tf}_vol_ratio'] = context_df['volume'] / vol_sma
        
        # Map to primary timeframe
        aligned_features = self.map_to_primary_timeframe(primary_df, features)
        
        return aligned_features
