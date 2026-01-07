"""
📊 Trade Management - Classes for handling simulated trades with full indicator details
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Union
import pandas as pd
import numpy as np


def safe_strftime(ts, fmt: str = '%Y-%m-%d %H:%M') -> str:
    """
    Converts a timestamp (datetime or pandas Timestamp) to formatted string.
    Handles NaT and None values safely.
    """
    if ts is None:
        return '-'
    # Check for pandas NaT
    try:
        if pd.isna(ts):
            return '-'
    except (TypeError, ValueError):
        pass
    try:
        if hasattr(ts, 'strftime'):
            return ts.strftime(fmt)
        return str(ts)
    except Exception:
        return '-'


class TradeType(Enum):
    """Trade direction"""
    LONG = "LONG"
    SHORT = "SHORT"


class ExitReason(Enum):
    """Reason for trade exit"""
    SIGNAL_REVERSAL = "Signal Reversal"     # Exit due to opposite signal
    STOP_LOSS = "Stop Loss"                 # Exit due to stop loss hit
    TAKE_PROFIT = "Take Profit"             # Exit due to take profit hit
    MAX_HOLDING = "Max Holding"             # Exit due to max candles reached
    STILL_OPEN = "Still Open"               # Trade not yet closed


@dataclass
class IndicatorSnapshot:
    """Snapshot of indicator values at a specific moment"""
    # RSI
    rsi_value: float = 0.0
    rsi_score: float = 0.0
    rsi_reason: str = ""
    
    # MACD
    macd_line: float = 0.0
    macd_signal: float = 0.0
    macd_diff: float = 0.0
    macd_score: float = 0.0
    macd_reason: str = ""
    
    # Bollinger Bands
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    bb_position: float = 0.0  # 0-1 position within bands
    bb_score: float = 0.0
    bb_reason: str = ""
    
    # Total
    total_confidence: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'rsi_value': round(self.rsi_value, 2),
            'rsi_score': round(self.rsi_score, 2),
            'rsi_reason': self.rsi_reason,
            'macd_line': round(self.macd_line, 4),
            'macd_signal': round(self.macd_signal, 4),
            'macd_diff': round(self.macd_diff, 4),
            'macd_score': round(self.macd_score, 2),
            'macd_reason': self.macd_reason,
            'bb_upper': round(self.bb_upper, 2),
            'bb_middle': round(self.bb_middle, 2),
            'bb_lower': round(self.bb_lower, 2),
            'bb_position': round(self.bb_position * 100, 1),
            'bb_score': round(self.bb_score, 2),
            'bb_reason': self.bb_reason,
            'total_confidence': round(self.total_confidence, 2)
        }


@dataclass
class SignalLog:
    """Log entry for a single candle's signal analysis"""
    timestamp: datetime
    price: float
    rsi_value: float
    rsi_score: float
    macd_line: float
    macd_signal: float
    macd_score: float
    bb_position: float
    bb_score: float
    total_confidence: float
    signal_type: str  # "LONG", "SHORT", "NEUTRAL"
    action: str  # "ENTRY", "EXIT", "HOLD", "NO_POSITION"
    threshold_used: float
    
    def to_dict(self) -> dict:
        return {
            'timestamp': safe_strftime(self.timestamp),
            'price': f"${self.price:,.2f}" if self.price and not pd.isna(self.price) else '-',
            'rsi': f"{self.rsi_value:.1f}" if self.rsi_value is not None and not pd.isna(self.rsi_value) else '-',
            'rsi_score': f"{self.rsi_score:+.1f}" if self.rsi_score is not None and not pd.isna(self.rsi_score) else '-',
            'macd_score': f"{self.macd_score:+.1f}" if self.macd_score is not None and not pd.isna(self.macd_score) else '-',
            'bb_pos': f"{self.bb_position*100:.0f}%" if self.bb_position is not None and not pd.isna(self.bb_position) else '-',
            'bb_score': f"{self.bb_score:+.1f}" if self.bb_score is not None and not pd.isna(self.bb_score) else '-',
            'confidence': f"{self.total_confidence:+.1f}" if self.total_confidence is not None and not pd.isna(self.total_confidence) else '-',
            'signal': self.signal_type,
            'action': self.action
        }


@dataclass
class Trade:
    """Represents a single trade with full indicator details"""
    trade_id: int
    trade_type: TradeType
    entry_time: datetime
    entry_price: float
    entry_confidence: float
    entry_indicators: Optional[IndicatorSnapshot] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_confidence: Optional[float] = None
    exit_indicators: Optional[IndicatorSnapshot] = None
    exit_reason: ExitReason = ExitReason.STILL_OPEN
    candles_held: int = 0
    
    @property
    def is_closed(self) -> bool:
        """Check if trade is closed"""
        if self.exit_time is None:
            return False
        # Also check for pandas NaT
        try:
            if pd.isna(self.exit_time):
                return False
        except (TypeError, ValueError):
            pass
        return True
    
    @property
    def pnl_pct(self) -> Optional[float]:
        """Calculate P&L percentage"""
        if not self.is_closed:
            return None
        
        if self.trade_type == TradeType.LONG:
            return ((self.exit_price - self.entry_price) / self.entry_price) * 100
        else:  # SHORT
            return ((self.entry_price - self.exit_price) / self.entry_price) * 100
    
    @property
    def is_winner(self) -> Optional[bool]:
        """Check if trade is profitable"""
        pnl = self.pnl_pct
        return pnl > 0 if pnl is not None else None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for display"""
        entry_time_str = safe_strftime(self.entry_time)
        exit_time_str = safe_strftime(self.exit_time) if self.exit_time is not None else 'OPEN'
        
        # Exit reason emoji
        exit_emoji = {
            ExitReason.SIGNAL_REVERSAL: "📊",
            ExitReason.STOP_LOSS: "🛑",
            ExitReason.TAKE_PROFIT: "🎯",
            ExitReason.MAX_HOLDING: "⏰",
            ExitReason.STILL_OPEN: "⏳"
        }
        
        return {
            'id': self.trade_id,
            'type': self.trade_type.value,
            'entry_time': entry_time_str,
            'entry_price': f"${self.entry_price:,.2f}" if self.entry_price else '-',
            'entry_confidence': f"{self.entry_confidence:+.1f}" if self.entry_confidence else '-',
            'exit_time': exit_time_str,
            'exit_price': f"${self.exit_price:,.2f}" if self.exit_price else '-',
            'exit_confidence': f"{self.exit_confidence:+.1f}" if self.exit_confidence else '-',
            'exit_reason': f"{exit_emoji.get(self.exit_reason, '')} {self.exit_reason.value}",
            'pnl_pct': f"{self.pnl_pct:+.2f}%" if self.pnl_pct is not None else '-',
            'candles': self.candles_held,
            'result': '✅' if self.is_winner else '❌' if self.is_winner is False else '⏳'
        }
    
    def get_entry_breakdown(self) -> Dict:
        """Get detailed entry breakdown for display"""
        if not self.entry_indicators:
            return {}
        return {
            'timestamp': self.entry_time,
            'price': self.entry_price,
            'type': 'ENTRY',
            'trade_type': self.trade_type.value,
            'indicators': self.entry_indicators.to_dict()
        }
    
    def get_exit_breakdown(self) -> Dict:
        """Get detailed exit breakdown for display"""
        if not self.exit_indicators:
            return {}
        return {
            'timestamp': self.exit_time,
            'price': self.exit_price,
            'type': 'EXIT',
            'trade_type': self.trade_type.value,
            'indicators': self.exit_indicators.to_dict(),
            'pnl_pct': self.pnl_pct,
            'candles_held': self.candles_held
        }


@dataclass
class TradeList:
    """Collection of trades with statistics"""
    trades: List[Trade] = field(default_factory=list)
    signal_log: List[SignalLog] = field(default_factory=list)
    
    def add_trade(self, trade: Trade):
        """Add a trade to the list"""
        self.trades.append(trade)
    
    def add_signal_log(self, log: SignalLog):
        """Add a signal log entry"""
        self.signal_log.append(log)
    
    @property
    def closed_trades(self) -> List[Trade]:
        """Get only closed trades"""
        return [t for t in self.trades if t.is_closed]
    
    @property
    def open_trades(self) -> List[Trade]:
        """Get only open trades"""
        return [t for t in self.trades if not t.is_closed]
    
    @property
    def total_trades(self) -> int:
        """Total number of trades"""
        return len(self.closed_trades)
    
    @property
    def winning_trades(self) -> int:
        """Number of winning trades"""
        return sum(1 for t in self.closed_trades if t.is_winner)
    
    @property
    def losing_trades(self) -> int:
        """Number of losing trades"""
        return sum(1 for t in self.closed_trades if t.is_winner is False)
    
    @property
    def win_rate(self) -> float:
        """Win rate percentage"""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    @property
    def total_return(self) -> float:
        """Total return percentage (compounded)"""
        if not self.closed_trades:
            return 0.0
        
        cumulative = 1.0
        for trade in self.closed_trades:
            if trade.pnl_pct is not None:
                cumulative *= (1 + trade.pnl_pct / 100)
        
        return (cumulative - 1) * 100
    
    @property
    def average_trade(self) -> float:
        """Average trade return percentage"""
        if not self.closed_trades:
            return 0.0
        
        returns = [t.pnl_pct for t in self.closed_trades if t.pnl_pct is not None]
        return sum(returns) / len(returns) if returns else 0.0
    
    @property
    def best_trade(self) -> float:
        """Best trade return percentage"""
        returns = [t.pnl_pct for t in self.closed_trades if t.pnl_pct is not None]
        return max(returns) if returns else 0.0
    
    @property
    def worst_trade(self) -> float:
        """Worst trade return percentage"""
        returns = [t.pnl_pct for t in self.closed_trades if t.pnl_pct is not None]
        return min(returns) if returns else 0.0
    
    @property
    def long_trades(self) -> int:
        """Number of LONG trades"""
        return sum(1 for t in self.closed_trades if t.trade_type == TradeType.LONG)
    
    @property
    def short_trades(self) -> int:
        """Number of SHORT trades"""
        return sum(1 for t in self.closed_trades if t.trade_type == TradeType.SHORT)
    
    @property
    def avg_candles_held(self) -> float:
        """Average candles held per trade"""
        if not self.closed_trades:
            return 0.0
        candles = [t.candles_held for t in self.closed_trades]
        return sum(candles) / len(candles) if candles else 0.0
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert to DataFrame for display"""
        if not self.trades:
            return pd.DataFrame()
        
        data = [t.to_dict() for t in self.trades]
        return pd.DataFrame(data)
    
    def signal_log_to_dataframe(self) -> pd.DataFrame:
        """Convert signal log to DataFrame"""
        if not self.signal_log:
            return pd.DataFrame()
        
        data = [s.to_dict() for s in self.signal_log]
        return pd.DataFrame(data)
    
    def get_statistics(self) -> dict:
        """Get all statistics as a dictionary"""
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(self.win_rate, 1),
            'total_return': round(self.total_return, 2),
            'average_trade': round(self.average_trade, 2),
            'best_trade': round(self.best_trade, 2),
            'worst_trade': round(self.worst_trade, 2),
            'long_trades': self.long_trades,
            'short_trades': self.short_trades,
            'avg_candles_held': round(self.avg_candles_held, 1),
            'total_signals': len(self.signal_log)
        }
