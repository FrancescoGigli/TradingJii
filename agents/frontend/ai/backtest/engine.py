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
from .trades import Trade, TradeType, TradeList, ExitReason
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
        min_holding: int,
        stop_loss_pct: float = None,
        take_profit_pct: float = None,
        use_sl_tp: bool = None,
        max_holding_candles: int = None
    ) -> TradeList:
        """
        Simulate trades based on confidence scores.
        
        Entry rules:
        - LONG: confidence > +entry_threshold
        - SHORT: confidence < -entry_threshold
        
        Exit rules (in priority order):
        1. Stop Loss: Exit if loss exceeds stop_loss_pct
        2. Take Profit: Exit if profit exceeds take_profit_pct
        3. Max Holding: Exit if held for max_holding_candles
        4. Signal Reversal: Exit on opposite signal (after min_holding)
        """
        # Get SL/TP config
        stop_loss_pct = stop_loss_pct if stop_loss_pct is not None else self.config.get('stop_loss_pct', 2.0)
        take_profit_pct = take_profit_pct if take_profit_pct is not None else self.config.get('take_profit_pct', 4.0)
        use_sl_tp = use_sl_tp if use_sl_tp is not None else self.config.get('use_sl_tp', True)
        max_holding_candles = max_holding_candles if max_holding_candles is not None else self.config.get('max_holding_candles', 0)
        
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
                current_trade.candles_held = candles_in_trade
                
                # Calculate current PnL %
                if current_trade.trade_type == TradeType.LONG:
                    current_pnl_pct = ((price - current_trade.entry_price) / current_trade.entry_price) * 100
                else:  # SHORT
                    current_pnl_pct = ((current_trade.entry_price - price) / current_trade.entry_price) * 100
                
                # Check exit conditions (in priority order)
                should_exit = False
                exit_reason = ExitReason.STILL_OPEN
                
                # 1. Check Stop Loss
                if use_sl_tp and current_pnl_pct <= -stop_loss_pct:
                    should_exit = True
                    exit_reason = ExitReason.STOP_LOSS
                
                # 2. Check Take Profit
                elif use_sl_tp and current_pnl_pct >= take_profit_pct:
                    should_exit = True
                    exit_reason = ExitReason.TAKE_PROFIT
                
                # 3. Check Max Holding
                elif max_holding_candles > 0 and candles_in_trade >= max_holding_candles:
                    should_exit = True
                    exit_reason = ExitReason.MAX_HOLDING
                
                # 4. Check Signal Reversal (only after min_holding)
                elif candles_in_trade >= min_holding:
                    if current_trade.trade_type == TradeType.LONG:
                        if score < -exit_threshold:
                            should_exit = True
                            exit_reason = ExitReason.SIGNAL_REVERSAL
                    else:  # SHORT
                        if score > exit_threshold:
                            should_exit = True
                            exit_reason = ExitReason.SIGNAL_REVERSAL
                
                if should_exit:
                    # Close the trade
                    current_trade.exit_time = idx
                    current_trade.exit_price = price
                    current_trade.exit_confidence = score
                    current_trade.exit_reason = exit_reason
                    current_trade.candles_held = candles_in_trade
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
