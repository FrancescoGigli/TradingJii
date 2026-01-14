"""
🤖 XGB Trade Simulator
======================

Simulates trades based on XGBoost ML signals with:
- Entry based on XGB score threshold
- Stop Loss / Take Profit
- Trailing Stop Loss
- Trade statistics
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum
import pandas as pd
import numpy as np


class XGBTradeType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class XGBExitReason(Enum):
    TRAILING_STOP = "Trailing Stop"
    STOP_LOSS = "Stop Loss"
    TAKE_PROFIT = "Take Profit"
    SIGNAL_REVERSAL = "Signal Reversal"
    MAX_HOLDING = "Max Holding"
    END_OF_DATA = "End of Data"


@dataclass
class XGBTrade:
    """Single XGB trade record"""
    trade_id: int
    trade_type: XGBTradeType
    entry_time: pd.Timestamp
    entry_price: float
    entry_score: float
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[XGBExitReason] = None
    pnl_pct: Optional[float] = None
    max_favorable: float = 0.0  # Maximum favorable excursion
    max_adverse: float = 0.0    # Maximum adverse excursion
    trailing_stop_price: Optional[float] = None
    
    @property
    def is_closed(self) -> bool:
        return self.exit_time is not None
    
    @property
    def is_winner(self) -> bool:
        return self.pnl_pct is not None and self.pnl_pct > 0


@dataclass
class XGBSimulatorConfig:
    """Configuration for XGB trade simulator"""
    entry_threshold: float = 40.0      # XGB score to enter
    stop_loss_pct: float = 2.0         # Stop loss percentage
    take_profit_pct: float = 4.0       # Take profit percentage
    trailing_stop_pct: float = 1.5     # Trailing stop percentage
    trailing_activation_pct: float = 1.0  # Profit % to activate trailing
    max_holding_candles: int = 50      # Max candles to hold (0=disabled)
    min_holding_candles: int = 2       # Min candles before exit


@dataclass 
class XGBSimulatorResult:
    """Results from XGB simulation"""
    df: pd.DataFrame
    trades: List[XGBTrade]
    config: XGBSimulatorConfig
    xgb_scores: pd.Series
    
    def get_statistics(self) -> Dict:
        """Calculate trade statistics"""
        closed_trades = [t for t in self.trades if t.is_closed]
        
        if not closed_trades:
            return {
                'total_trades': len(self.trades),
                'closed_trades': 0,
                'open_trades': len(self.trades),
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_return': 0.0,
                'average_trade': 0.0,
                'best_trade': 0.0,
                'worst_trade': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'long_trades': 0,
                'short_trades': 0,
                'exit_reasons': {}
            }
        
        pnls = [t.pnl_pct for t in closed_trades]
        winners = [t for t in closed_trades if t.is_winner]
        losers = [t for t in closed_trades if not t.is_winner]
        
        win_pnls = [t.pnl_pct for t in winners]
        loss_pnls = [abs(t.pnl_pct) for t in losers]
        
        total_wins = sum(win_pnls) if win_pnls else 0
        total_losses = sum(loss_pnls) if loss_pnls else 0
        
        # Exit reason breakdown
        exit_reasons = {}
        for t in closed_trades:
            reason = t.exit_reason.value if t.exit_reason else "Unknown"
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        return {
            'total_trades': len(self.trades),
            'closed_trades': len(closed_trades),
            'open_trades': len(self.trades) - len(closed_trades),
            'winning_trades': len(winners),
            'losing_trades': len(losers),
            'win_rate': len(winners) / len(closed_trades) * 100,
            'total_return': sum(pnls),
            'average_trade': np.mean(pnls),
            'best_trade': max(pnls) if pnls else 0,
            'worst_trade': min(pnls) if pnls else 0,
            'avg_win': np.mean(win_pnls) if win_pnls else 0,
            'avg_loss': -np.mean(loss_pnls) if loss_pnls else 0,
            'profit_factor': total_wins / total_losses if total_losses > 0 else float('inf'),
            'long_trades': len([t for t in self.trades if t.trade_type == XGBTradeType.LONG]),
            'short_trades': len([t for t in self.trades if t.trade_type == XGBTradeType.SHORT]),
            'exit_reasons': exit_reasons
        }
    
    def get_trade_data_for_chart(self) -> Tuple[pd.DataFrame, pd.DataFrame, List[Dict]]:
        """
        Get data formatted for charting.
        
        Returns:
            - entries: DataFrame with entry points
            - exits: DataFrame with exit points
            - lines: List of dicts for trade lines
        """
        entries_data = []
        exits_data = []
        lines = []
        
        for trade in self.trades:
            # Entry point
            entries_data.append({
                'time': trade.entry_time,
                'price': trade.entry_price,
                'type': trade.trade_type.value,
                'score': trade.entry_score,
                'trade_id': trade.trade_id
            })
            
            # Exit point (if closed)
            if trade.is_closed:
                exits_data.append({
                    'time': trade.exit_time,
                    'price': trade.exit_price,
                    'pnl': trade.pnl_pct,
                    'is_winner': trade.is_winner,
                    'exit_reason': trade.exit_reason.value if trade.exit_reason else "",
                    'trade_id': trade.trade_id
                })
                
                # Trade line
                lines.append({
                    'entry_time': trade.entry_time,
                    'entry_price': trade.entry_price,
                    'exit_time': trade.exit_time,
                    'exit_price': trade.exit_price,
                    'is_winner': trade.is_winner,
                    'pnl': trade.pnl_pct
                })
        
        entries = pd.DataFrame(entries_data) if entries_data else pd.DataFrame()
        exits = pd.DataFrame(exits_data) if exits_data else pd.DataFrame()
        
        return entries, exits, lines


def run_xgb_simulation(
    df: pd.DataFrame,
    xgb_scores: pd.Series,
    config: Optional[XGBSimulatorConfig] = None
) -> XGBSimulatorResult:
    """
    Run XGB trade simulation with trailing stop.
    
    Args:
        df: OHLCV DataFrame
        xgb_scores: Series of normalized XGB scores (-100 to +100)
        config: Simulator configuration
        
    Returns:
        XGBSimulatorResult with trades and statistics
    """
    if config is None:
        config = XGBSimulatorConfig()
    
    trades = []
    trade_id = 0
    current_trade: Optional[XGBTrade] = None
    
    for i in range(len(df)):
        idx = df.index[i]
        candle = df.iloc[i]
        score = xgb_scores.iloc[i] if i < len(xgb_scores) else 0
        
        high = candle['high']
        low = candle['low']
        close = candle['close']
        
        # ═══════════════════════════════════════════════════════════════
        # MANAGE OPEN TRADE
        # ═══════════════════════════════════════════════════════════════
        if current_trade is not None:
            entry_price = current_trade.entry_price
            is_long = current_trade.trade_type == XGBTradeType.LONG
            
            # Calculate current P&L
            if is_long:
                current_pnl_high = (high - entry_price) / entry_price * 100
                current_pnl_low = (low - entry_price) / entry_price * 100
                current_pnl_close = (close - entry_price) / entry_price * 100
            else:  # SHORT
                current_pnl_high = (entry_price - low) / entry_price * 100
                current_pnl_low = (entry_price - high) / entry_price * 100
                current_pnl_close = (entry_price - close) / entry_price * 100
            
            # Update MFE/MAE
            current_trade.max_favorable = max(current_trade.max_favorable, current_pnl_high)
            current_trade.max_adverse = min(current_trade.max_adverse, current_pnl_low)
            
            # Count holding candles
            holding_candles = i - df.index.get_loc(current_trade.entry_time)
            
            exit_reason = None
            exit_price = None
            
            # Check exit conditions (in order of priority)
            
            # 1. STOP LOSS
            if current_pnl_low <= -config.stop_loss_pct:
                exit_reason = XGBExitReason.STOP_LOSS
                if is_long:
                    exit_price = entry_price * (1 - config.stop_loss_pct / 100)
                else:
                    exit_price = entry_price * (1 + config.stop_loss_pct / 100)
            
            # 2. TAKE PROFIT
            elif current_pnl_high >= config.take_profit_pct:
                exit_reason = XGBExitReason.TAKE_PROFIT
                if is_long:
                    exit_price = entry_price * (1 + config.take_profit_pct / 100)
                else:
                    exit_price = entry_price * (1 - config.take_profit_pct / 100)
            
            # 3. TRAILING STOP
            elif current_trade.trailing_stop_price is not None:
                if is_long and low <= current_trade.trailing_stop_price:
                    exit_reason = XGBExitReason.TRAILING_STOP
                    exit_price = current_trade.trailing_stop_price
                elif not is_long and high >= current_trade.trailing_stop_price:
                    exit_reason = XGBExitReason.TRAILING_STOP
                    exit_price = current_trade.trailing_stop_price
            
            # 4. MAX HOLDING
            elif config.max_holding_candles > 0 and holding_candles >= config.max_holding_candles:
                exit_reason = XGBExitReason.MAX_HOLDING
                exit_price = close
            
            # 5. SIGNAL REVERSAL (only after min holding)
            elif holding_candles >= config.min_holding_candles:
                if is_long and score < -config.entry_threshold:
                    exit_reason = XGBExitReason.SIGNAL_REVERSAL
                    exit_price = close
                elif not is_long and score > config.entry_threshold:
                    exit_reason = XGBExitReason.SIGNAL_REVERSAL
                    exit_price = close
            
            # Close trade if exit triggered
            if exit_reason is not None:
                if is_long:
                    final_pnl = (exit_price - entry_price) / entry_price * 100
                else:
                    final_pnl = (entry_price - exit_price) / entry_price * 100
                
                current_trade.exit_time = idx
                current_trade.exit_price = exit_price
                current_trade.exit_reason = exit_reason
                current_trade.pnl_pct = final_pnl
                
                trades.append(current_trade)
                current_trade = None
            
            else:
                # Update trailing stop if profitable
                if current_trade.max_favorable >= config.trailing_activation_pct:
                    if is_long:
                        # For LONG: trailing stop moves up
                        new_trailing = high * (1 - config.trailing_stop_pct / 100)
                        if current_trade.trailing_stop_price is None:
                            current_trade.trailing_stop_price = new_trailing
                        else:
                            current_trade.trailing_stop_price = max(
                                current_trade.trailing_stop_price, 
                                new_trailing
                            )
                    else:
                        # For SHORT: trailing stop moves down
                        new_trailing = low * (1 + config.trailing_stop_pct / 100)
                        if current_trade.trailing_stop_price is None:
                            current_trade.trailing_stop_price = new_trailing
                        else:
                            current_trade.trailing_stop_price = min(
                                current_trade.trailing_stop_price,
                                new_trailing
                            )
        
        # ═══════════════════════════════════════════════════════════════
        # OPEN NEW TRADE
        # ═══════════════════════════════════════════════════════════════
        if current_trade is None:
            # Check for LONG entry
            if score > config.entry_threshold:
                trade_id += 1
                current_trade = XGBTrade(
                    trade_id=trade_id,
                    trade_type=XGBTradeType.LONG,
                    entry_time=idx,
                    entry_price=close,
                    entry_score=score
                )
            
            # Check for SHORT entry
            elif score < -config.entry_threshold:
                trade_id += 1
                current_trade = XGBTrade(
                    trade_id=trade_id,
                    trade_type=XGBTradeType.SHORT,
                    entry_time=idx,
                    entry_price=close,
                    entry_score=score
                )
    
    # Close any remaining open trade at end of data
    if current_trade is not None:
        last_candle = df.iloc[-1]
        entry_price = current_trade.entry_price
        exit_price = last_candle['close']
        
        if current_trade.trade_type == XGBTradeType.LONG:
            final_pnl = (exit_price - entry_price) / entry_price * 100
        else:
            final_pnl = (entry_price - exit_price) / entry_price * 100
        
        current_trade.exit_time = df.index[-1]
        current_trade.exit_price = exit_price
        current_trade.exit_reason = XGBExitReason.END_OF_DATA
        current_trade.pnl_pct = final_pnl
        
        trades.append(current_trade)
    
    return XGBSimulatorResult(
        df=df,
        trades=trades,
        config=config,
        xgb_scores=xgb_scores
    )
