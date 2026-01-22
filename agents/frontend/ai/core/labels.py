"""
🎯 ATR-Based Trailing Stop Label Generation

Genera etichette di training usando:
- Stop Loss FISSO basato su ATR (protezione rischio)
- Trailing Stop basato su ATR (gestione profitto)
- effective_sl = max(fixed_sl, trailing_sl) per LONG
- effective_sl = min(fixed_sl, trailing_sl) per SHORT

REGOLA FONDAMENTALE: Lo stop non peggiora mai!

Parametri k_* sono:
- GLOBALI (uguali per tutti i symbol)
- STABILI (scelti per stabilità, non performance)
- NON OTTIMIZZATI automaticamente

Formula Score: score = R - λ*log(1+D) - costs

Dove:
- R = realized return
- D = bars held
- λ = time penalty coefficient
- costs = trading fees

Reference: ATR-based labeling for ML-safe training
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass
import logging
from math import log

logger = logging.getLogger(__name__)


@dataclass
class ATRLabelConfig:
    """
    Configuration for ATR-Based Label Generation.
    
    Parametri scelti per STABILITÀ cross-asset, non per massimizzare performance!
    """
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ATR MULTIPLIERS (globali, stabili)
    # ═══════════════════════════════════════════════════════════════════════════
    
    # 15m timeframe
    k_fixed_sl_15m: float = 2.5      # Fixed SL = ATR% * 2.5
    k_trailing_15m: float = 1.2      # Trailing = ATR% * 1.2
    max_bars_15m: int = 48           # 12 ore (48 * 15m)
    
    # 1h timeframe
    k_fixed_sl_1h: float = 3.0       # Fixed SL = ATR% * 3.0 (più largo)
    k_trailing_1h: float = 1.5       # Trailing = ATR% * 1.5
    max_bars_1h: int = 24            # 24 ore
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ATR CALCULATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    atr_period: int = 14             # Periodo per calcolo ATR
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SCORING (uguali per tutti)
    # ═══════════════════════════════════════════════════════════════════════════
    
    time_penalty_lambda: float = 0.001   # λ coefficient
    trading_cost: float = 0.001          # 0.1% total (entry + exit)
    
    def get_k_fixed_sl(self, timeframe: str) -> float:
        """Get fixed SL multiplier for given timeframe"""
        if timeframe == '15m':
            return self.k_fixed_sl_15m
        elif timeframe == '1h':
            return self.k_fixed_sl_1h
        else:
            raise ValueError(f"Unknown timeframe: {timeframe}")
    
    def get_k_trailing(self, timeframe: str) -> float:
        """Get trailing multiplier for given timeframe"""
        if timeframe == '15m':
            return self.k_trailing_15m
        elif timeframe == '1h':
            return self.k_trailing_1h
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


def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Calculate Average True Range (ATR).
    
    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of close prices
        period: ATR period (default: 14)
    
    Returns:
        Array of ATR values
    """
    n = len(high)
    tr = np.zeros(n)
    atr = np.zeros(n)
    
    # True Range calculation
    for i in range(1, n):
        tr1 = high[i] - low[i]
        tr2 = abs(high[i] - close[i-1])
        tr3 = abs(low[i] - close[i-1])
        tr[i] = max(tr1, tr2, tr3)
    
    # First ATR is simple average
    if n > period:
        atr[period] = np.mean(tr[1:period+1])
        
        # Subsequent ATRs use EMA-style smoothing
        for i in range(period + 1, n):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    
    return atr


class ATRLabeler:
    """
    ATR-Based Label Generator.
    
    Per ogni candela di entry, simula un trade LONG e SHORT con:
    - Fixed Stop Loss basato su ATR (protezione)
    - Trailing Stop basato su ATR (gestione profitto)
    - effective_sl = max/min per garantire che lo stop non peggiori
    
    Formula: score = R - λ*log(1+D) - costs
    """
    
    def __init__(self, config: ATRLabelConfig = None):
        """
        Initialize labeler.
        
        Args:
            config: Label generation configuration
        """
        self.config = config or ATRLabelConfig()
    
    def _simulate_long(
        self,
        entry_price: float,
        atr_pct: float,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        close_prices: np.ndarray,
        k_fixed_sl: float,
        k_trailing: float,
        max_bars: int
    ) -> Tuple[float, int, str, float, float]:
        """
        Simulate a LONG trade with ATR-based stops.
        
        Args:
            entry_price: Entry price (close of entry candle)
            atr_pct: ATR as percentage of price at entry
            high_prices: Array of high prices after entry
            low_prices: Array of low prices after entry
            close_prices: Array of close prices after entry
            k_fixed_sl: Fixed SL multiplier
            k_trailing: Trailing multiplier
            max_bars: Maximum bars to hold
        
        Returns:
            Tuple of (exit_price, bars_held, exit_type, mfe, mae)
        """
        n_bars = min(len(high_prices), max_bars)
        
        # Fixed Stop Loss (NON SI MUOVE MAI)
        fixed_sl = entry_price * (1 - k_fixed_sl * atr_pct)
        
        # Tracking variables
        max_seen = entry_price
        min_seen = entry_price
        
        for i in range(n_bars):
            # Update max seen (per trailing)
            if high_prices[i] > max_seen:
                max_seen = high_prices[i]
            
            # Update min seen (per MAE)
            if low_prices[i] < min_seen:
                min_seen = low_prices[i]
            
            # Trailing Stop (segue il max)
            trailing_sl = max_seen * (1 - k_trailing * atr_pct)
            
            # REGOLA FONDAMENTALE: lo stop non peggiora mai
            effective_sl = max(fixed_sl, trailing_sl)
            
            # Check if effective_sl hit
            if low_prices[i] <= effective_sl:
                exit_price = effective_sl
                bars_held = i + 1
                
                # Determine exit type
                if effective_sl == fixed_sl:
                    exit_type = 'fixed_sl'
                else:
                    exit_type = 'trailing'
                
                # Calculate MFE/MAE up to exit
                mfe = (max_seen - entry_price) / entry_price
                mae = (entry_price - min_seen) / entry_price
                
                return exit_price, bars_held, exit_type, mfe, mae
        
        # Time exit (max bars reached)
        exit_price = close_prices[n_bars - 1] if n_bars > 0 else entry_price
        bars_held = n_bars
        exit_type = 'time'
        
        # Calculate MFE/MAE up to exit
        mfe = (max_seen - entry_price) / entry_price
        mae = (entry_price - min_seen) / entry_price
        
        return exit_price, bars_held, exit_type, mfe, mae
    
    def _simulate_short(
        self,
        entry_price: float,
        atr_pct: float,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        close_prices: np.ndarray,
        k_fixed_sl: float,
        k_trailing: float,
        max_bars: int
    ) -> Tuple[float, int, str, float, float]:
        """
        Simulate a SHORT trade with ATR-based stops.
        
        Args:
            entry_price: Entry price (close of entry candle)
            atr_pct: ATR as percentage of price at entry
            high_prices: Array of high prices after entry
            low_prices: Array of low prices after entry
            close_prices: Array of close prices after entry
            k_fixed_sl: Fixed SL multiplier
            k_trailing: Trailing multiplier
            max_bars: Maximum bars to hold
        
        Returns:
            Tuple of (exit_price, bars_held, exit_type, mfe, mae)
        """
        n_bars = min(len(high_prices), max_bars)
        
        # Fixed Stop Loss (NON SI MUOVE MAI) - per SHORT è sopra entry
        fixed_sl = entry_price * (1 + k_fixed_sl * atr_pct)
        
        # Tracking variables
        min_seen = entry_price
        max_seen = entry_price
        
        for i in range(n_bars):
            # Update min seen (per trailing - SHORT profit when price goes down)
            if low_prices[i] < min_seen:
                min_seen = low_prices[i]
            
            # Update max seen (per MAE)
            if high_prices[i] > max_seen:
                max_seen = high_prices[i]
            
            # Trailing Stop (segue il min) - per SHORT è sopra
            trailing_sl = min_seen * (1 + k_trailing * atr_pct)
            
            # REGOLA FONDAMENTALE: lo stop non peggiora mai
            # Per SHORT: effective_sl = min(fixed_sl, trailing_sl)
            effective_sl = min(fixed_sl, trailing_sl)
            
            # Check if effective_sl hit
            if high_prices[i] >= effective_sl:
                exit_price = effective_sl
                bars_held = i + 1
                
                # Determine exit type
                if effective_sl == fixed_sl:
                    exit_type = 'fixed_sl'
                else:
                    exit_type = 'trailing'
                
                # Calculate MFE/MAE up to exit (inverted for SHORT)
                mfe = (entry_price - min_seen) / entry_price
                mae = (max_seen - entry_price) / entry_price
                
                return exit_price, bars_held, exit_type, mfe, mae
        
        # Time exit (max bars reached)
        exit_price = close_prices[n_bars - 1] if n_bars > 0 else entry_price
        bars_held = n_bars
        exit_type = 'time'
        
        # Calculate MFE/MAE up to exit
        mfe = (entry_price - min_seen) / entry_price
        mae = (max_seen - entry_price) / entry_price
        
        return exit_price, bars_held, exit_type, mfe, mae
    
    def _calculate_score(
        self,
        realized_return: float,
        bars_held: int
    ) -> float:
        """
        Calculate final score.
        
        Formula: score = R - λ*log(1+D) - costs
        
        Args:
            realized_return: R = (exit_price - entry_price) / entry_price
            bars_held: D = number of bars held
        
        Returns:
            Score (continuous, not normalized)
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
            DataFrame with label columns
        """
        tf = timeframe
        k_fixed_sl = self.config.get_k_fixed_sl(timeframe)
        k_trailing = self.config.get_k_trailing(timeframe)
        max_bars = self.config.get_max_bars(timeframe)
        atr_period = self.config.atr_period
        
        # Convert to numpy for speed
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        n = len(df)
        
        # Calculate ATR
        atr = calculate_atr(high, low, close, atr_period)
        atr_pct = np.zeros(n)
        atr_pct[atr_period:] = atr[atr_period:] / close[atr_period:]
        
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
        atr_pct_at_entry = np.full(n, np.nan)
        
        # Valid range: need ATR calculated and enough future bars
        start_idx = atr_period + 1
        end_idx = n - max_bars
        
        logger.info(f"Generating ATR-based labels for {tf}: {start_idx} to {end_idx}")
        
        for i in range(start_idx, end_idx):
            if progress_callback and i % 1000 == 0:
                progress_callback(i - start_idx, end_idx - start_idx, timeframe)
            
            entry_price = close[i]
            current_atr_pct = atr_pct[i]
            
            # Skip if ATR is too small (avoid division issues)
            if current_atr_pct < 0.001:
                exit_type_long[i] = 'invalid'
                exit_type_short[i] = 'invalid'
                continue
            
            atr_pct_at_entry[i] = current_atr_pct
            
            # Future price arrays (after entry)
            future_high = high[i + 1: i + 1 + max_bars]
            future_low = low[i + 1: i + 1 + max_bars]
            future_close = close[i + 1: i + 1 + max_bars]
            
            # ═══════════════════════════════════════════════════════════════
            # LONG SIMULATION
            # ═══════════════════════════════════════════════════════════════
            
            exit_price_l, bars_l, exit_t_l, mfe_l, mae_l = self._simulate_long(
                entry_price=entry_price,
                atr_pct=current_atr_pct,
                high_prices=future_high,
                low_prices=future_low,
                close_prices=future_close,
                k_fixed_sl=k_fixed_sl,
                k_trailing=k_trailing,
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
            
            exit_price_s, bars_s, exit_t_s, mfe_s, mae_s = self._simulate_short(
                entry_price=entry_price,
                atr_pct=current_atr_pct,
                high_prices=future_high,
                low_prices=future_low,
                close_prices=future_close,
                k_fixed_sl=k_fixed_sl,
                k_trailing=k_trailing,
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
        
        # Mark edges as invalid
        exit_type_long[:start_idx] = 'invalid'
        exit_type_short[:start_idx] = 'invalid'
        exit_type_long[end_idx:] = 'invalid'
        exit_type_short[end_idx:] = 'invalid'
        
        # Create result DataFrame
        labels_df = pd.DataFrame({
            # TARGETS (for ML training)
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
            f'atr_pct_{tf}': atr_pct_at_entry,
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
            timeframes: List of timeframes to process (default: ['15m'])
            progress_callback: Optional callback for progress updates
        
        Returns:
            DataFrame with all label columns
        """
        if timeframes is None:
            timeframes = ['15m']
        
        all_labels = []
        
        for tf in timeframes:
            logger.info(f"Generating ATR-based labels for timeframe: {tf}")
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
        valid_mask = labels_df[f'exit_type_long_{tf}'].notna() & (labels_df[f'exit_type_long_{tf}'] != 'invalid')
        valid_labels = labels_df[valid_mask]
        
        n_valid = len(valid_labels)
        if n_valid == 0:
            return {'total_samples': 0}
        
        # Exit type counts
        exit_counts_long = valid_labels[f'exit_type_long_{tf}'].value_counts()
        exit_counts_short = valid_labels[f'exit_type_short_{tf}'].value_counts()
        
        stats = {
            'total_samples': n_valid,
            
            # ATR stats
            'avg_atr_pct': valid_labels[f'atr_pct_{tf}'].mean() * 100,
            
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
            'long_fixed_sl_pct': exit_counts_long.get('fixed_sl', 0) / n_valid * 100,
            'long_trailing_pct': exit_counts_long.get('trailing', 0) / n_valid * 100,
            'long_time_pct': exit_counts_long.get('time', 0) / n_valid * 100,
            
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
            'short_fixed_sl_pct': exit_counts_short.get('fixed_sl', 0) / n_valid * 100,
            'short_trailing_pct': exit_counts_short.get('trailing', 0) / n_valid * 100,
            'short_time_pct': exit_counts_short.get('time', 0) / n_valid * 100,
        }
        
        return stats
    
    def print_label_stats(self, labels_df: pd.DataFrame, timeframe: str = '15m'):
        """Print label statistics in a nice format"""
        stats = self.get_label_stats(labels_df, timeframe)
        
        if stats['total_samples'] == 0:
            print("No valid samples found!")
            return
        
        print(f"""
╔══════════════════════════════════════════════════════════════════╗
║           ATR-BASED LABEL STATISTICS ({timeframe})                      ║
╠══════════════════════════════════════════════════════════════════╣
║  Total Samples:     {stats['total_samples']:>10,}                                
║  Avg ATR %:         {stats['avg_atr_pct']:>9.2f}%                               
╠══════════════════════════════════════════════════════════════════╣
║  LONG LABELS:                                                    
║    Score Mean:      {stats['long_score_mean']:>10.5f}                           
║    Score Std:       {stats['long_score_std']:>10.5f}                           
║    Positive %:      {stats['long_positive_pct']:>9.1f}%                          
║    Avg Return:      {stats['long_avg_return']:>9.2f}%                           
║    Avg MFE:         {stats['long_avg_mfe']:>9.2f}%                           
║    Avg MAE:         {stats['long_avg_mae']:>9.2f}%                           
║    Avg Bars Held:   {stats['long_avg_bars']:>9.1f}                            
║    Exit Types:                                                    
║      Fixed SL:      {stats['long_fixed_sl_pct']:>9.1f}%                          
║      Trailing:      {stats['long_trailing_pct']:>9.1f}%                          
║      Time:          {stats['long_time_pct']:>9.1f}%                          
╠══════════════════════════════════════════════════════════════════╣
║  SHORT LABELS:                                                   
║    Score Mean:      {stats['short_score_mean']:>10.5f}                           
║    Score Std:       {stats['short_score_std']:>10.5f}                           
║    Positive %:      {stats['short_positive_pct']:>9.1f}%                          
║    Avg Return:      {stats['short_avg_return']:>9.2f}%                           
║    Avg MFE:         {stats['short_avg_mfe']:>9.2f}%                           
║    Avg MAE:         {stats['short_avg_mae']:>9.2f}%                           
║    Avg Bars Held:   {stats['short_avg_bars']:>9.1f}                            
║    Exit Types:                                                    
║      Fixed SL:      {stats['short_fixed_sl_pct']:>9.1f}%                          
║      Trailing:      {stats['short_trailing_pct']:>9.1f}%                          
║      Time:          {stats['short_time_pct']:>9.1f}%                          
╚══════════════════════════════════════════════════════════════════╝
        """)


def generate_atr_labels(
    df: pd.DataFrame,
    config: ATRLabelConfig = None,
    timeframes: List[str] = None
) -> pd.DataFrame:
    """
    Convenience function to generate ATR-based labels.
    
    Args:
        df: OHLCV DataFrame
        config: Optional label configuration
        timeframes: List of timeframes (default: ['15m'])
    
    Returns:
        Labels DataFrame with all columns
    """
    labeler = ATRLabeler(config)
    return labeler.generate_all_labels(df, timeframes)


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY ALIASES
# ═══════════════════════════════════════════════════════════════════════════════

# Old names map to new implementation
TrailingLabelConfig = ATRLabelConfig
TrailingStopLabeler = ATRLabeler
BarrierConfig = ATRLabelConfig
TripleBarrierLabeler = ATRLabeler

def generate_trailing_labels(
    df: pd.DataFrame,
    config: ATRLabelConfig = None,
    timeframes: List[str] = None
) -> pd.DataFrame:
    """Backward compatible function name."""
    return generate_atr_labels(df, config, timeframes)

def generate_training_labels(
    df: pd.DataFrame,
    config: ATRLabelConfig = None
) -> pd.DataFrame:
    """Backward compatible function name."""
    logger.warning("generate_training_labels is deprecated. Use generate_atr_labels instead.")
    return generate_atr_labels(df, config, timeframes=['15m'])
