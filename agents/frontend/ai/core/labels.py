"""
🎯 Trailing Stop Label Generation

Genera etichette di training usando simulazione Trailing Stop:
- Score continuo basato su Realized Return (NON MFE!)
- Penalità tempo additiva: score = R - λ*log(1+D) - costs
- Multi-timeframe: 15m e 1h

IMPORTANTE: 
- Queste sono ETICHETTE (guardano il futuro), NON feature!
- NON verranno mai usate come input del modello
- Servono SOLO per l'addestramento supervisionato
- MFE/MAE sono diagnostica, NON entrano nello score

Reference: Custom implementation for trailing stop based labeling
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass
import logging
from math import log

logger = logging.getLogger(__name__)


@dataclass
class TrailingLabelConfig:
    """Configuration for Trailing Stop Label Generation"""
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRAILING STOP SETTINGS (per timeframe)
    # ═══════════════════════════════════════════════════════════════════════════
    
    # 15m timeframe
    trailing_stop_pct_15m: float = 0.015   # 1.5% trailing stop
    max_bars_15m: int = 48                  # 12 ore (48 * 15m)
    
    # 1h timeframe  
    trailing_stop_pct_1h: float = 0.025    # 2.5% trailing stop (più largo per 1h)
    max_bars_1h: int = 24                   # 24 ore (24 * 1h)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TIME PENALTY SETTINGS
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Penalità tempo: penalty = λ * log(1 + D)
    time_penalty_lambda: float = 0.001     # λ coefficient
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COST SETTINGS
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Trading costs (fees)
    trading_cost: float = 0.001            # 0.1% total (entry + exit)
    
    def get_trailing_stop_pct(self, timeframe: str) -> float:
        """Get trailing stop percentage for given timeframe"""
        if timeframe == '15m':
            return self.trailing_stop_pct_15m
        elif timeframe == '1h':
            return self.trailing_stop_pct_1h
        else:
            raise ValueError(f"Unknown timeframe: {timeframe}")
    
    def get_max_bars(self, timeframe: str) -> int:
        """Get max holding bars for given timeframe"""
        if timeframe == '15m':
            return self.max_bars_15m
        elif timeframe == '1h':
            return self.max_bars_1h
        else:
            raise ValueError(f"Unknown timeframe: {timeframe}")


class TrailingStopLabeler:
    """
    Trailing Stop Label Generator.
    
    Per ogni candela di entry, simula un trade LONG e SHORT con trailing stop
    deterministico e calcola lo score basato sul return realizzato.
    
    Formula: score = R - λ*log(1+D) - costs
    
    Dove:
    - R = realized return (exit_price - entry_price) / entry_price
    - D = bars held until exit
    - λ = time penalty coefficient
    - costs = trading fees
    """
    
    def __init__(self, config: TrailingLabelConfig = None):
        """
        Initialize labeler.
        
        Args:
            config: Label generation configuration
        """
        self.config = config or TrailingLabelConfig()
    
    def _simulate_trailing_stop_long(
        self,
        entry_price: float,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        close_prices: np.ndarray,
        trailing_stop_pct: float,
        max_bars: int
    ) -> Tuple[float, int, str, float, float]:
        """
        Simulate a LONG trade with trailing stop.
        
        The trailing stop tracks the highest price seen and exits when
        price drops by trailing_stop_pct from that high.
        
        Args:
            entry_price: Entry price (close of entry candle)
            high_prices: Array of high prices after entry
            low_prices: Array of low prices after entry
            close_prices: Array of close prices after entry
            trailing_stop_pct: Trailing stop percentage (e.g., 0.015 for 1.5%)
            max_bars: Maximum bars to hold
        
        Returns:
            Tuple of (exit_price, bars_held, exit_type, mfe, mae)
            - exit_price: Price at exit
            - bars_held: Number of bars held
            - exit_type: 'trailing' or 'time'
            - mfe: Maximum Favorable Excursion (highest profit %)
            - mae: Maximum Adverse Excursion (worst drawdown %)
        """
        n_bars = min(len(high_prices), max_bars)
        
        highest_seen = entry_price
        lowest_seen = entry_price
        
        for i in range(n_bars):
            # Update highest seen (for trailing)
            if high_prices[i] > highest_seen:
                highest_seen = high_prices[i]
            
            # Update lowest seen (for MAE)
            if low_prices[i] < lowest_seen:
                lowest_seen = low_prices[i]
            
            # Calculate trailing stop level
            trailing_level = highest_seen * (1 - trailing_stop_pct)
            
            # Check if trailing stop hit
            if low_prices[i] <= trailing_level:
                # Exit at trailing level
                exit_price = trailing_level
                bars_held = i + 1
                exit_type = 'trailing'
                
                # Calculate MFE/MAE up to exit point only
                mfe = (highest_seen - entry_price) / entry_price
                mae = (entry_price - lowest_seen) / entry_price
                
                return exit_price, bars_held, exit_type, mfe, mae
        
        # Time exit (max bars reached)
        exit_price = close_prices[n_bars - 1] if n_bars > 0 else entry_price
        bars_held = n_bars
        exit_type = 'time'
        
        # Calculate MFE/MAE up to exit point only
        mfe = (highest_seen - entry_price) / entry_price
        mae = (entry_price - lowest_seen) / entry_price
        
        return exit_price, bars_held, exit_type, mfe, mae
    
    def _simulate_trailing_stop_short(
        self,
        entry_price: float,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        close_prices: np.ndarray,
        trailing_stop_pct: float,
        max_bars: int
    ) -> Tuple[float, int, str, float, float]:
        """
        Simulate a SHORT trade with trailing stop.
        
        The trailing stop tracks the lowest price seen and exits when
        price rises by trailing_stop_pct from that low.
        
        Args:
            entry_price: Entry price (close of entry candle)
            high_prices: Array of high prices after entry
            low_prices: Array of low prices after entry
            close_prices: Array of close prices after entry
            trailing_stop_pct: Trailing stop percentage (e.g., 0.015 for 1.5%)
            max_bars: Maximum bars to hold
        
        Returns:
            Tuple of (exit_price, bars_held, exit_type, mfe, mae)
            - exit_price: Price at exit
            - bars_held: Number of bars held
            - exit_type: 'trailing' or 'time'
            - mfe: Maximum Favorable Excursion (lowest price %)
            - mae: Maximum Adverse Excursion (worst spike up %)
        """
        n_bars = min(len(high_prices), max_bars)
        
        lowest_seen = entry_price
        highest_seen = entry_price
        
        for i in range(n_bars):
            # Update lowest seen (for trailing - SHORT profits when price goes down)
            if low_prices[i] < lowest_seen:
                lowest_seen = low_prices[i]
            
            # Update highest seen (for MAE)
            if high_prices[i] > highest_seen:
                highest_seen = high_prices[i]
            
            # Calculate trailing stop level (for SHORT, stop is above)
            trailing_level = lowest_seen * (1 + trailing_stop_pct)
            
            # Check if trailing stop hit
            if high_prices[i] >= trailing_level:
                # Exit at trailing level
                exit_price = trailing_level
                bars_held = i + 1
                exit_type = 'trailing'
                
                # Calculate MFE/MAE up to exit point only (inverted for SHORT)
                mfe = (entry_price - lowest_seen) / entry_price
                mae = (highest_seen - entry_price) / entry_price
                
                return exit_price, bars_held, exit_type, mfe, mae
        
        # Time exit (max bars reached)
        exit_price = close_prices[n_bars - 1] if n_bars > 0 else entry_price
        bars_held = n_bars
        exit_type = 'time'
        
        # Calculate MFE/MAE up to exit point only
        mfe = (entry_price - lowest_seen) / entry_price
        mae = (highest_seen - entry_price) / entry_price
        
        return exit_price, bars_held, exit_type, mfe, mae
    
    def _calculate_score(
        self,
        realized_return: float,
        bars_held: int
    ) -> float:
        """
        Calculate final score using the approved formula.
        
        Formula: score = R - λ*log(1+D) - costs
        
        Args:
            realized_return: R = (exit_price - entry_price) / entry_price
            bars_held: D = number of bars held
        
        Returns:
            Score (range libero, NON normalizzato)
        """
        # Time penalty: λ * log(1 + D)
        time_penalty = self.config.time_penalty_lambda * log(1 + bars_held)
        
        # Final score
        score = realized_return - time_penalty - self.config.trading_cost
        
        return score
    
    def generate_labels_for_timeframe(
        self,
        df: pd.DataFrame,
        timeframe: str = '15m',
        progress_callback: callable = None
    ) -> pd.DataFrame:
        """
        Generate labels for a specific timeframe.
        
        Args:
            df: OHLCV DataFrame with columns [open, high, low, close, volume]
            timeframe: '15m' or '1h'
            progress_callback: Optional callback for progress updates
        
        Returns:
            DataFrame with columns:
            - score_long_{tf}: Score for LONG entry
            - score_short_{tf}: Score for SHORT entry
            - realized_return_long_{tf}: Actual return from LONG
            - realized_return_short_{tf}: Actual return from SHORT
            - mfe_long_{tf}: Max Favorable Excursion for LONG
            - mfe_short_{tf}: Max Favorable Excursion for SHORT
            - mae_long_{tf}: Max Adverse Excursion for LONG
            - mae_short_{tf}: Max Adverse Excursion for SHORT
            - bars_held_long_{tf}: Bars held for LONG
            - bars_held_short_{tf}: Bars held for SHORT
            - exit_type_long_{tf}: Exit type for LONG ('trailing'/'time')
            - exit_type_short_{tf}: Exit type for SHORT ('trailing'/'time')
        """
        tf = timeframe
        trailing_stop_pct = self.config.get_trailing_stop_pct(timeframe)
        max_bars = self.config.get_max_bars(timeframe)
        
        # Convert to numpy for speed
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        n = len(df)
        
        # Initialize output arrays
        score_long = np.full(n, np.nan)
        score_short = np.full(n, np.nan)
        realized_return_long = np.full(n, np.nan)
        realized_return_short = np.full(n, np.nan)
        mfe_long = np.full(n, np.nan)
        mfe_short = np.full(n, np.nan)
        mae_long = np.full(n, np.nan)
        mae_short = np.full(n, np.nan)
        bars_held_long = np.full(n, np.nan)
        bars_held_short = np.full(n, np.nan)
        exit_type_long = np.empty(n, dtype=object)
        exit_type_short = np.empty(n, dtype=object)
        
        # Process each bar (skip last max_bars - not enough future data)
        valid_range = n - max_bars
        
        for i in range(valid_range):
            if progress_callback and i % 1000 == 0:
                progress_callback(i, valid_range, timeframe)
            
            entry_price = close[i]
            
            # Future price arrays (after entry)
            future_high = high[i + 1: i + 1 + max_bars]
            future_low = low[i + 1: i + 1 + max_bars]
            future_close = close[i + 1: i + 1 + max_bars]
            
            # ═══════════════════════════════════════════════════════════════
            # LONG SIMULATION
            # ═══════════════════════════════════════════════════════════════
            
            exit_price_l, bars_l, exit_t_l, mfe_l, mae_l = self._simulate_trailing_stop_long(
                entry_price=entry_price,
                high_prices=future_high,
                low_prices=future_low,
                close_prices=future_close,
                trailing_stop_pct=trailing_stop_pct,
                max_bars=max_bars
            )
            
            # Realized return for LONG
            r_long = (exit_price_l - entry_price) / entry_price
            
            # Score for LONG
            s_long = self._calculate_score(r_long, bars_l)
            
            # Store LONG results
            score_long[i] = s_long
            realized_return_long[i] = r_long
            mfe_long[i] = mfe_l
            mae_long[i] = mae_l
            bars_held_long[i] = bars_l
            exit_type_long[i] = exit_t_l
            
            # ═══════════════════════════════════════════════════════════════
            # SHORT SIMULATION
            # ═══════════════════════════════════════════════════════════════
            
            exit_price_s, bars_s, exit_t_s, mfe_s, mae_s = self._simulate_trailing_stop_short(
                entry_price=entry_price,
                high_prices=future_high,
                low_prices=future_low,
                close_prices=future_close,
                trailing_stop_pct=trailing_stop_pct,
                max_bars=max_bars
            )
            
            # Realized return for SHORT (profit when price goes down)
            r_short = (entry_price - exit_price_s) / entry_price
            
            # Score for SHORT
            s_short = self._calculate_score(r_short, bars_s)
            
            # Store SHORT results
            score_short[i] = s_short
            realized_return_short[i] = r_short
            mfe_short[i] = mfe_s
            mae_short[i] = mae_s
            bars_held_short[i] = bars_s
            exit_type_short[i] = exit_t_s
        
        # Mark last bars as invalid
        exit_type_long[valid_range:] = 'invalid'
        exit_type_short[valid_range:] = 'invalid'
        
        # Create result DataFrame
        labels_df = pd.DataFrame({
            # LABELS (main targets for ML)
            f'score_long_{tf}': score_long,
            f'score_short_{tf}': score_short,
            
            # DIAGNOSTICS (for analysis, not training)
            f'realized_return_long_{tf}': realized_return_long,
            f'realized_return_short_{tf}': realized_return_short,
            f'mfe_long_{tf}': mfe_long,
            f'mfe_short_{tf}': mfe_short,
            f'mae_long_{tf}': mae_long,
            f'mae_short_{tf}': mae_short,
            f'bars_held_long_{tf}': bars_held_long,
            f'bars_held_short_{tf}': bars_held_short,
            f'exit_type_long_{tf}': exit_type_long,
            f'exit_type_short_{tf}': exit_type_short,
        }, index=df.index)
        
        return labels_df
    
    def generate_all_labels(
        self,
        df: pd.DataFrame,
        timeframes: List[str] = None,
        progress_callback: callable = None
    ) -> pd.DataFrame:
        """
        Generate labels for all specified timeframes.
        
        Args:
            df: OHLCV DataFrame
            timeframes: List of timeframes to process (default: ['15m', '1h'])
            progress_callback: Optional callback for progress updates
        
        Returns:
            DataFrame with all label columns for all timeframes
        """
        if timeframes is None:
            timeframes = ['15m', '1h']
        
        all_labels = []
        
        for tf in timeframes:
            logger.info(f"Generating labels for timeframe: {tf}")
            labels = self.generate_labels_for_timeframe(df, tf, progress_callback)
            all_labels.append(labels)
        
        # Combine all labels
        result = pd.concat(all_labels, axis=1)
        
        return result
    
    def get_label_stats(self, labels_df: pd.DataFrame, timeframe: str = '15m') -> dict:
        """
        Get statistics about generated labels.
        
        Args:
            labels_df: Labels DataFrame from generate_labels
            timeframe: Timeframe to analyze
        
        Returns:
            Dictionary with label statistics
        """
        tf = timeframe
        
        # Valid mask (exclude invalid rows)
        valid_mask = labels_df[f'exit_type_long_{tf}'] != 'invalid'
        valid_labels = labels_df[valid_mask]
        
        n_valid = len(valid_labels)
        if n_valid == 0:
            return {'total_samples': 0}
        
        stats = {
            'total_samples': n_valid,
            
            # LONG statistics
            'long_score_mean': valid_labels[f'score_long_{tf}'].mean(),
            'long_score_std': valid_labels[f'score_long_{tf}'].std(),
            'long_score_min': valid_labels[f'score_long_{tf}'].min(),
            'long_score_max': valid_labels[f'score_long_{tf}'].max(),
            'long_positive_pct': (valid_labels[f'score_long_{tf}'] > 0).mean() * 100,
            'long_avg_return': valid_labels[f'realized_return_long_{tf}'].mean() * 100,
            'long_avg_mfe': valid_labels[f'mfe_long_{tf}'].mean() * 100,
            'long_avg_mae': valid_labels[f'mae_long_{tf}'].mean() * 100,
            'long_avg_bars': valid_labels[f'bars_held_long_{tf}'].mean(),
            'long_trailing_exits': (valid_labels[f'exit_type_long_{tf}'] == 'trailing').sum(),
            'long_time_exits': (valid_labels[f'exit_type_long_{tf}'] == 'time').sum(),
            
            # SHORT statistics
            'short_score_mean': valid_labels[f'score_short_{tf}'].mean(),
            'short_score_std': valid_labels[f'score_short_{tf}'].std(),
            'short_score_min': valid_labels[f'score_short_{tf}'].min(),
            'short_score_max': valid_labels[f'score_short_{tf}'].max(),
            'short_positive_pct': (valid_labels[f'score_short_{tf}'] > 0).mean() * 100,
            'short_avg_return': valid_labels[f'realized_return_short_{tf}'].mean() * 100,
            'short_avg_mfe': valid_labels[f'mfe_short_{tf}'].mean() * 100,
            'short_avg_mae': valid_labels[f'mae_short_{tf}'].mean() * 100,
            'short_avg_bars': valid_labels[f'bars_held_short_{tf}'].mean(),
            'short_trailing_exits': (valid_labels[f'exit_type_short_{tf}'] == 'trailing').sum(),
            'short_time_exits': (valid_labels[f'exit_type_short_{tf}'] == 'time').sum(),
        }
        
        return stats
    
    def print_label_stats(self, labels_df: pd.DataFrame, timeframe: str = '15m'):
        """Print label statistics in a nice format"""
        stats = self.get_label_stats(labels_df, timeframe)
        
        if stats['total_samples'] == 0:
            print("No valid samples found!")
            return
        
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║         TRAILING STOP LABEL STATISTICS ({timeframe})               ║
╠══════════════════════════════════════════════════════════════╣
║  Total Samples:     {stats['total_samples']:>10,}                              
╠══════════════════════════════════════════════════════════════╣
║  LONG LABELS:                                                
║    Score Mean:      {stats['long_score_mean']:>10.5f}                         
║    Score Std:       {stats['long_score_std']:>10.5f}                         
║    Score Range:     [{stats['long_score_min']:.5f}, {stats['long_score_max']:.5f}]      
║    Positive %:      {stats['long_positive_pct']:>9.1f}%                        
║    Avg Return:      {stats['long_avg_return']:>9.2f}%                         
║    Avg MFE:         {stats['long_avg_mfe']:>9.2f}%                         
║    Avg MAE:         {stats['long_avg_mae']:>9.2f}%                         
║    Avg Bars Held:   {stats['long_avg_bars']:>9.1f}                          
║    Trailing Exits:  {stats['long_trailing_exits']:>10,}                            
║    Time Exits:      {stats['long_time_exits']:>10,}                            
╠══════════════════════════════════════════════════════════════╣
║  SHORT LABELS:                                               
║    Score Mean:      {stats['short_score_mean']:>10.5f}                         
║    Score Std:       {stats['short_score_std']:>10.5f}                         
║    Score Range:     [{stats['short_score_min']:.5f}, {stats['short_score_max']:.5f}]      
║    Positive %:      {stats['short_positive_pct']:>9.1f}%                        
║    Avg Return:      {stats['short_avg_return']:>9.2f}%                         
║    Avg MFE:         {stats['short_avg_mfe']:>9.2f}%                         
║    Avg MAE:         {stats['short_avg_mae']:>9.2f}%                         
║    Avg Bars Held:   {stats['short_avg_bars']:>9.1f}                          
║    Trailing Exits:  {stats['short_trailing_exits']:>10,}                            
║    Time Exits:      {stats['short_time_exits']:>10,}                            
╚══════════════════════════════════════════════════════════════╝
        """)


def generate_trailing_labels(
    df: pd.DataFrame,
    config: TrailingLabelConfig = None,
    timeframes: List[str] = None
) -> pd.DataFrame:
    """
    Convenience function to generate trailing stop labels.
    
    Args:
        df: OHLCV DataFrame
        config: Optional label configuration
        timeframes: List of timeframes (default: ['15m', '1h'])
    
    Returns:
        Labels DataFrame with all columns
    """
    labeler = TrailingStopLabeler(config)
    return labeler.generate_all_labels(df, timeframes)


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY ALIASES (for migration)
# ═══════════════════════════════════════════════════════════════════════════════

# Old names map to new implementation
BarrierConfig = TrailingLabelConfig  # Alias for backward compatibility
TripleBarrierLabeler = TrailingStopLabeler  # Alias for backward compatibility

def generate_training_labels(
    df: pd.DataFrame,
    config: TrailingLabelConfig = None
) -> pd.DataFrame:
    """
    Backward compatible function name.
    
    DEPRECATED: Use generate_trailing_labels instead.
    """
    logger.warning("generate_training_labels is deprecated. Use generate_trailing_labels instead.")
    return generate_trailing_labels(df, config, timeframes=['15m'])
