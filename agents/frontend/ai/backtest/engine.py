"""
🔄 Backtest Engine - Main simulation engine

Simulates trading based on confidence scores generated from technical indicators.
Processes historical data candle-by-candle and tracks entries/exits.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional, Dict, List

from ..analysis.signals import SignalCalculator, SignalComponents
from .trades import Trade, TradeType, TradeList
from ..core.config import BACKTEST_CONFIG


@dataclass
class BacktestResult:
    """Container for backtest results"""
    trades: TradeList
    confidence_scores: pd.Series
    signal_components: SignalComponents
    df: pd.DataFrame
    config: Dict
    
    def get_entry_points(self) -> pd.DataFrame:
        """Get DataFrame with entry points for visualization"""
        entries = []
        for trade in self.trades.trades:
            entries.append({
                'time': trade.entry_time,
                'price': trade.entry_price,
                'type': trade.trade_type.value,
                'confidence': trade.entry_confidence
            })
        return pd.DataFrame(entries) if entries else pd.DataFrame()
    
    def get_exit_points(self) -> pd.DataFrame:
        """Get DataFrame with exit points for visualization"""
        exits = []
        for trade in self.trades.closed_trades:
            exits.append({
                'time': trade.exit_time,
                'price': trade.exit_price,
                'type': trade.trade_type.value,
                'pnl': trade.pnl_pct,
                'is_winner': trade.is_winner
            })
        return pd.DataFrame(exits) if exits else pd.DataFrame()
    
    def get_trade_lines(self) -> List[Dict]:
        """Get list of trade lines for visualization (entry to exit)"""
        lines = []
        for trade in self.trades.closed_trades:
            lines.append({
                'entry_time': trade.entry_time,
                'entry_price': trade.entry_price,
                'exit_time': trade.exit_time,
                'exit_price': trade.exit_price,
                'type': trade.trade_type.value,
                'is_winner': trade.is_winner
            })
        return lines


class BacktestEngine:
    """
    Backtest simulation engine.
    
    Processes historical OHLCV data and generates trades based on
    confidence scores derived from technical indicators.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or BACKTEST_CONFIG
        self.signal_calculator = SignalCalculator(self.config)
    
    def run(
        self, 
        df: pd.DataFrame, 
        entry_threshold: int = None,
        exit_threshold: int = None,
        min_holding: int = None
    ) -> BacktestResult:
        """
        Run backtest on historical data.
        
        Args:
            df: DataFrame with OHLCV data (must have datetime index)
            entry_threshold: Override config entry threshold (default: 60)
            exit_threshold: Override config exit threshold (default: 30)
            min_holding: Minimum candles to hold before exit
            
        Returns:
            BacktestResult with trades and statistics
        """
        # Use config defaults if not provided
        entry_threshold = entry_threshold or self.config['entry_threshold']
        exit_threshold = exit_threshold or self.config['exit_threshold']
        min_holding = min_holding or self.config['min_holding_candles']
        
        # Calculate confidence scores
        signal_components = self.signal_calculator.calculate(df)
        confidence = signal_components.total_score
        
        # Run simulation
        trades = self._simulate_trades(
            df, 
            confidence, 
            entry_threshold, 
            exit_threshold,
            min_holding
        )
        
        return BacktestResult(
            trades=trades,
            confidence_scores=confidence,
            signal_components=signal_components,
            df=df,
            config={
                'entry_threshold': entry_threshold,
                'exit_threshold': exit_threshold,
                'min_holding': min_holding
            }
        )
    
    def _simulate_trades(
        self, 
        df: pd.DataFrame, 
        confidence: pd.Series,
        entry_threshold: int,
        exit_threshold: int,
        min_holding: int
    ) -> TradeList:
        """
        Simulate trades based on confidence scores.
        
        Entry rules:
        - LONG: confidence > +entry_threshold
        - SHORT: confidence < -entry_threshold
        
        Exit rules:
        - LONG exit: confidence < -exit_threshold (reversal signal)
        - SHORT exit: confidence > +exit_threshold (reversal signal)
        - Minimum holding period must pass before exit
        """
        trade_list = TradeList()
        trade_id = 0
        current_trade: Optional[Trade] = None
        candles_in_trade = 0
        
        for i in range(len(df)):
            idx = df.index[i]
            score = confidence.iloc[i]
            price = df['close'].iloc[i]
            
            # Skip if score is NaN (warmup period)
            if pd.isna(score):
                continue
            
            # If we have an open trade
            if current_trade is not None:
                candles_in_trade += 1
                
                # Check exit conditions
                should_exit = False
                
                if candles_in_trade >= min_holding:
                    if current_trade.trade_type == TradeType.LONG:
                        # Exit LONG if strong short signal
                        if score < -exit_threshold:
                            should_exit = True
                    else:  # SHORT
                        # Exit SHORT if strong long signal
                        if score > exit_threshold:
                            should_exit = True
                
                if should_exit:
                    # Close the trade
                    current_trade.exit_time = idx
                    current_trade.exit_price = price
                    current_trade.exit_confidence = score
                    current_trade = None
                    candles_in_trade = 0
            
            # If no open trade, check entry conditions
            if current_trade is None:
                if score > entry_threshold:
                    # LONG entry
                    trade_id += 1
                    current_trade = Trade(
                        trade_id=trade_id,
                        trade_type=TradeType.LONG,
                        entry_time=idx,
                        entry_price=price,
                        entry_confidence=score
                    )
                    trade_list.add_trade(current_trade)
                    candles_in_trade = 0
                    
                elif score < -entry_threshold:
                    # SHORT entry
                    trade_id += 1
                    current_trade = Trade(
                        trade_id=trade_id,
                        trade_type=TradeType.SHORT,
                        entry_time=idx,
                        entry_price=price,
                        entry_confidence=score
                    )
                    trade_list.add_trade(current_trade)
                    candles_in_trade = 0
        
        return trade_list


def run_backtest(
    df: pd.DataFrame,
    entry_threshold: int = None,
    exit_threshold: int = None,
    min_holding: int = None
) -> BacktestResult:
    """
    Convenience function to run backtest.
    
    Args:
        df: DataFrame with OHLCV data
        entry_threshold: Score threshold for entry (default from config)
        exit_threshold: Score threshold for exit (default from config)
        min_holding: Minimum candles to hold (default from config)
        
    Returns:
        BacktestResult with all data
    """
    # Use config defaults if not provided
    if entry_threshold is None:
        entry_threshold = BACKTEST_CONFIG['entry_threshold']
    if exit_threshold is None:
        exit_threshold = BACKTEST_CONFIG['exit_threshold']
    if min_holding is None:
        min_holding = BACKTEST_CONFIG['min_holding_candles']
    
    engine = BacktestEngine()
    return engine.run(df, entry_threshold, exit_threshold, min_holding)
