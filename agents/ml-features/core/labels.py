"""
🎯 Triple Barrier Method - Label Generation

Generates training labels using the Triple Barrier Method:
- Upper barrier: Take Profit (adaptive based on volatility)
- Lower barrier: Stop Loss (adaptive based on volatility)
- Vertical barrier: Time horizon (max holding period)

Labels indicate whether a LONG or SHORT entry would have been profitable.

Reference: Advances in Financial Machine Learning - Marcos Lopez de Prado
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class BarrierConfig:
    """Configuration for Triple Barrier Method"""
    # Time barrier (max holding period in bars)
    max_holding_bars: int = 24  # 24 bars = 6 hours on 15m
    
    # Profit/Loss barriers (as multiples of volatility)
    tp_multiplier: float = 2.0  # Take profit = 2x ATR
    sl_multiplier: float = 1.0  # Stop loss = 1x ATR
    
    # Volatility lookback
    volatility_window: int = 20
    
    # Minimum barriers (as percentage)
    min_tp_pct: float = 0.005  # 0.5% minimum
    min_sl_pct: float = 0.003  # 0.3% minimum
    
    # Maximum barriers (as percentage)
    max_tp_pct: float = 0.10   # 10% maximum
    max_sl_pct: float = 0.05   # 5% maximum
    
    # Label thresholds
    min_return_for_label: float = 0.001  # 0.1% minimum for label=1


class TripleBarrierLabeler:
    """
    Triple Barrier Method for generating ML labels.
    
    For each timestamp, determines if a LONG or SHORT entry
    would have hit take-profit before stop-loss.
    """
    
    def __init__(self, config: BarrierConfig = None):
        """
        Initialize labeler.
        
        Args:
            config: Barrier configuration
        """
        self.config = config or BarrierConfig()
    
    def compute_volatility(self, df: pd.DataFrame) -> pd.Series:
        """
        Compute volatility for adaptive barriers.
        
        Uses ATR as volatility measure.
        
        Args:
            df: OHLCV DataFrame
        
        Returns:
            Series with volatility (ATR percentage)
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR
        atr = tr.ewm(span=self.config.volatility_window, adjust=False).mean()
        
        # ATR as percentage of price
        atr_pct = atr / close
        
        return atr_pct
    
    def compute_barriers(
        self, 
        df: pd.DataFrame,
        volatility: pd.Series = None
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Compute adaptive take-profit and stop-loss barriers.
        
        Args:
            df: OHLCV DataFrame
            volatility: Pre-computed volatility (optional)
        
        Returns:
            Tuple of (take_profit_pct, stop_loss_pct) Series
        """
        if volatility is None:
            volatility = self.compute_volatility(df)
        
        # Base barriers from volatility
        tp_pct = volatility * self.config.tp_multiplier
        sl_pct = volatility * self.config.sl_multiplier
        
        # Clip to min/max
        tp_pct = tp_pct.clip(self.config.min_tp_pct, self.config.max_tp_pct)
        sl_pct = sl_pct.clip(self.config.min_sl_pct, self.config.max_sl_pct)
        
        return tp_pct, sl_pct
    
    def get_first_barrier_touch(
        self,
        close_prices: np.ndarray,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        entry_idx: int,
        tp_price: float,
        sl_price: float,
        is_long: bool,
        max_bars: int
    ) -> Tuple[int, str, float]:
        """
        Find which barrier is touched first.
        
        Args:
            close_prices: Array of close prices
            high_prices: Array of high prices
            low_prices: Array of low prices
            entry_idx: Entry bar index
            tp_price: Take profit price
            sl_price: Stop loss price
            is_long: True for long, False for short
            max_bars: Maximum bars to look forward
        
        Returns:
            Tuple of (exit_idx, barrier_type, return_pct)
            barrier_type: 'tp', 'sl', or 'time'
        """
        entry_price = close_prices[entry_idx]
        end_idx = min(entry_idx + max_bars, len(close_prices) - 1)
        
        for i in range(entry_idx + 1, end_idx + 1):
            if is_long:
                # Long: TP hit if high >= tp_price, SL hit if low <= sl_price
                if high_prices[i] >= tp_price:
                    return i, 'tp', (tp_price - entry_price) / entry_price
                if low_prices[i] <= sl_price:
                    return i, 'sl', (sl_price - entry_price) / entry_price
            else:
                # Short: TP hit if low <= tp_price, SL hit if high >= sl_price
                if low_prices[i] <= tp_price:
                    return i, 'tp', (entry_price - tp_price) / entry_price
                if high_prices[i] >= sl_price:
                    return i, 'sl', (entry_price - sl_price) / entry_price
        
        # Time barrier reached
        exit_price = close_prices[end_idx]
        if is_long:
            return_pct = (exit_price - entry_price) / entry_price
        else:
            return_pct = (entry_price - exit_price) / entry_price
        
        return end_idx, 'time', return_pct
    
    def generate_labels(
        self, 
        df: pd.DataFrame,
        progress_callback: callable = None
    ) -> pd.DataFrame:
        """
        Generate labels for all timestamps.
        
        Args:
            df: OHLCV DataFrame
            progress_callback: Optional callback for progress updates
        
        Returns:
            DataFrame with columns:
            - y_long: 1 if long entry was profitable, 0 otherwise
            - y_short: 1 if short entry was profitable, 0 otherwise
            - long_return: Return from long entry
            - short_return: Return from short entry
            - long_barrier: Which barrier was hit for long
            - short_barrier: Which barrier was hit for short
            - tp_pct: Take profit percentage used
            - sl_pct: Stop loss percentage used
        """
        # Compute adaptive barriers
        volatility = self.compute_volatility(df)
        tp_pct, sl_pct = self.compute_barriers(df, volatility)
        
        # Convert to numpy for speed
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        n = len(df)
        
        # Initialize output arrays
        y_long = np.zeros(n)
        y_short = np.zeros(n)
        long_return = np.zeros(n)
        short_return = np.zeros(n)
        long_barrier = np.empty(n, dtype=object)
        short_barrier = np.empty(n, dtype=object)
        
        # Vectorized barrier prices
        tp_pct_arr = tp_pct.values
        sl_pct_arr = sl_pct.values
        
        # Process each bar (skip last max_holding_bars)
        for i in range(n - self.config.max_holding_bars):
            if progress_callback and i % 1000 == 0:
                progress_callback(i, n)
            
            entry_price = close[i]
            tp = tp_pct_arr[i]
            sl = sl_pct_arr[i]
            
            # Long barriers
            long_tp_price = entry_price * (1 + tp)
            long_sl_price = entry_price * (1 - sl)
            
            # Short barriers
            short_tp_price = entry_price * (1 - tp)
            short_sl_price = entry_price * (1 + sl)
            
            # Check long
            exit_idx, barrier, ret = self.get_first_barrier_touch(
                close, high, low, i,
                long_tp_price, long_sl_price,
                is_long=True,
                max_bars=self.config.max_holding_bars
            )
            long_return[i] = ret
            long_barrier[i] = barrier
            y_long[i] = 1 if ret > self.config.min_return_for_label else 0
            
            # Check short
            exit_idx, barrier, ret = self.get_first_barrier_touch(
                close, high, low, i,
                short_tp_price, short_sl_price,
                is_long=False,
                max_bars=self.config.max_holding_bars
            )
            short_return[i] = ret
            short_barrier[i] = barrier
            y_short[i] = 1 if ret > self.config.min_return_for_label else 0
        
        # Mark last bars as invalid
        long_barrier[n - self.config.max_holding_bars:] = 'invalid'
        short_barrier[n - self.config.max_holding_bars:] = 'invalid'
        
        # Create result DataFrame
        labels_df = pd.DataFrame({
            'y_long': y_long,
            'y_short': y_short,
            'long_return': long_return,
            'short_return': short_return,
            'long_barrier': long_barrier,
            'short_barrier': short_barrier,
            'tp_pct': tp_pct.values,
            'sl_pct': sl_pct.values
        }, index=df.index)
        
        return labels_df
    
    def get_label_stats(self, labels_df: pd.DataFrame) -> dict:
        """
        Get statistics about generated labels.
        
        Args:
            labels_df: Labels DataFrame from generate_labels
        
        Returns:
            Dictionary with label statistics
        """
        valid_mask = labels_df['long_barrier'] != 'invalid'
        valid_labels = labels_df[valid_mask]
        
        stats = {
            'total_samples': len(valid_labels),
            
            # Long labels
            'long_positive': (valid_labels['y_long'] == 1).sum(),
            'long_negative': (valid_labels['y_long'] == 0).sum(),
            'long_positive_pct': (valid_labels['y_long'] == 1).mean() * 100,
            'long_avg_return': valid_labels['long_return'].mean() * 100,
            'long_tp_hits': (valid_labels['long_barrier'] == 'tp').sum(),
            'long_sl_hits': (valid_labels['long_barrier'] == 'sl').sum(),
            'long_time_exits': (valid_labels['long_barrier'] == 'time').sum(),
            
            # Short labels
            'short_positive': (valid_labels['y_short'] == 1).sum(),
            'short_negative': (valid_labels['y_short'] == 0).sum(),
            'short_positive_pct': (valid_labels['y_short'] == 1).mean() * 100,
            'short_avg_return': valid_labels['short_return'].mean() * 100,
            'short_tp_hits': (valid_labels['short_barrier'] == 'tp').sum(),
            'short_sl_hits': (valid_labels['short_barrier'] == 'sl').sum(),
            'short_time_exits': (valid_labels['short_barrier'] == 'time').sum(),
            
            # Barrier stats
            'avg_tp_pct': valid_labels['tp_pct'].mean() * 100,
            'avg_sl_pct': valid_labels['sl_pct'].mean() * 100,
        }
        
        return stats
    
    def print_label_stats(self, labels_df: pd.DataFrame):
        """Print label statistics in a nice format"""
        stats = self.get_label_stats(labels_df)
        
        print("""
╔══════════════════════════════════════════════════════════════╗
║               TRIPLE BARRIER LABEL STATISTICS                ║
╠══════════════════════════════════════════════════════════════╣
║  Total Samples:     {total:>10,}                              
╠══════════════════════════════════════════════════════════════╣
║  LONG Labels:                                                
║    Positive (1):    {long_pos:>10,} ({long_pct:>5.1f}%)               
║    Avg Return:      {long_ret:>9.2f}%                         
║    TP Hits:         {long_tp:>10,}                            
║    SL Hits:         {long_sl:>10,}                            
║    Time Exits:      {long_time:>10,}                          
╠══════════════════════════════════════════════════════════════╣
║  SHORT Labels:                                               
║    Positive (1):    {short_pos:>10,} ({short_pct:>5.1f}%)              
║    Avg Return:      {short_ret:>9.2f}%                        
║    TP Hits:         {short_tp:>10,}                           
║    SL Hits:         {short_sl:>10,}                           
║    Time Exits:      {short_time:>10,}                         
╠══════════════════════════════════════════════════════════════╣
║  Avg TP:            {avg_tp:>9.2f}%                           
║  Avg SL:            {avg_sl:>9.2f}%                           
╚══════════════════════════════════════════════════════════════╝
        """.format(
            total=stats['total_samples'],
            long_pos=stats['long_positive'],
            long_pct=stats['long_positive_pct'],
            long_ret=stats['long_avg_return'],
            long_tp=stats['long_tp_hits'],
            long_sl=stats['long_sl_hits'],
            long_time=stats['long_time_exits'],
            short_pos=stats['short_positive'],
            short_pct=stats['short_positive_pct'],
            short_ret=stats['short_avg_return'],
            short_tp=stats['short_tp_hits'],
            short_sl=stats['short_sl_hits'],
            short_time=stats['short_time_exits'],
            avg_tp=stats['avg_tp_pct'],
            avg_sl=stats['avg_sl_pct'],
        ))


def generate_training_labels(
    df: pd.DataFrame,
    config: BarrierConfig = None
) -> pd.DataFrame:
    """
    Convenience function to generate training labels.
    
    Args:
        df: OHLCV DataFrame
        config: Optional barrier configuration
    
    Returns:
        Labels DataFrame
    """
    labeler = TripleBarrierLabeler(config)
    return labeler.generate_labels(df)
