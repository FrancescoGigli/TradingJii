#!/usr/bin/env python3
"""
📊 SESSION STATISTICS TRACKER

Tracks all trading statistics for the current session:
- Win/Loss tracking
- PnL analysis
- Trade history
- Performance metrics

Used by dashboard for live statistics display
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class ClosedTradeRecord:
    """Record of a closed trade with all details"""
    symbol: str
    entry_price: float
    exit_price: float
    entry_time: str
    close_time: str
    pnl_usd: float
    pnl_pct: float
    hold_time_minutes: int
    close_reason: str
    side: str
    leverage: int
    confidence: float
    trailing_was_active: bool = False


class SessionStatistics:
    """
    Tracks trading statistics for current session
    
    Features:
    - Win/Loss counting
    - PnL tracking (total, best, worst)
    - Win rate calculation
    - Average metrics
    - Trade history storage
    """
    
    def __init__(self):
        self.session_start_time = datetime.now()
        self.session_start_balance = 0.0
        
        # Trade counters
        self.trades_won = 0
        self.trades_lost = 0
        self.trades_breakeven = 0
        
        # PnL tracking
        self.total_pnl_usd = 0.0
        self.total_pnl_pct = 0.0
        self.best_trade_pnl = 0.0
        self.worst_trade_pnl = 0.0
        
        # Trade history
        self.closed_trades: List[ClosedTradeRecord] = []
        
        logging.debug("📊 SessionStatistics initialized")
    
    def initialize_balance(self, start_balance: float):
        """Set starting balance for session"""
        self.session_start_balance = start_balance
        logging.info(f"💰 Session starting balance: ${start_balance:.2f}")
    
    def update_from_closed_position(self, position) -> ClosedTradeRecord:
        """
        Update statistics when a position closes
        
        Args:
            position: ThreadSafePosition that was closed
            
        Returns:
            ClosedTradeRecord: Record of the closed trade
        """
        try:
            # Calculate hold time
            entry_dt = datetime.fromisoformat(position.entry_time)
            close_dt = datetime.fromisoformat(position.close_time) if position.close_time else datetime.now()
            hold_time_minutes = int((close_dt - entry_dt).total_seconds() / 60)
            
            # Extract PnL
            pnl_usd = position.unrealized_pnl_usd or 0.0
            pnl_pct = position.unrealized_pnl_pct or 0.0
            
            # Determine if trailing was active
            trailing_active = (
                position.trailing_data is not None and 
                position.trailing_data.enabled if hasattr(position, 'trailing_data') else False
            )
            
            # Create trade record
            trade_record = ClosedTradeRecord(
                symbol=position.symbol.replace('/USDT:USDT', ''),
                entry_price=position.entry_price,
                exit_price=position.current_price,
                entry_time=position.entry_time,
                close_time=position.close_time or datetime.now().isoformat(),
                pnl_usd=pnl_usd,
                pnl_pct=pnl_pct,
                hold_time_minutes=hold_time_minutes,
                close_reason=self._extract_close_reason(position.status),
                side=position.side,
                leverage=position.leverage,
                confidence=position.confidence,
                trailing_was_active=trailing_active
            )
            
            # Update counters
            if pnl_usd > 0.5:  # > $0.50 = win
                self.trades_won += 1
            elif pnl_usd < -0.5:  # < -$0.50 = loss
                self.trades_lost += 1
            else:  # -$0.50 to +$0.50 = breakeven
                self.trades_breakeven += 1
            
            # Update PnL tracking
            self.total_pnl_usd += pnl_usd
            self.best_trade_pnl = max(self.best_trade_pnl, pnl_usd)
            self.worst_trade_pnl = min(self.worst_trade_pnl, pnl_usd)
            
            # Store trade
            self.closed_trades.append(trade_record)
            
            logging.info(
                f"📊 Trade closed: {trade_record.symbol} "
                f"{'+' if pnl_usd >= 0 else ''}{pnl_usd:.2f} USD "
                f"({trade_record.close_reason})"
            )
            
            return trade_record
            
        except Exception as e:
            logging.error(f"Error updating statistics from closed position: {e}")
            return None
    
    def _extract_close_reason(self, status: str) -> str:
        """Extract clean close reason from position status"""
        if "STOP_LOSS" in status.upper() or "SL" in status.upper():
            return "STOP_LOSS_HIT"
        elif "TRAILING" in status.upper():
            return "TRAILING_STOP_HIT"
        elif "TAKE_PROFIT" in status.upper() or "TP" in status.upper():
            return "TAKE_PROFIT_HIT"
        elif "MANUAL" in status.upper():
            return "MANUAL_CLOSE"
        else:
            return "UNKNOWN"
    
    # ========================================
    # STATISTICS GETTERS
    # ========================================
    
    def get_total_trades(self) -> int:
        """Get total number of closed trades"""
        return self.trades_won + self.trades_lost + self.trades_breakeven
    
    def get_win_rate(self) -> float:
        """Calculate win rate percentage"""
        total = self.trades_won + self.trades_lost
        if total == 0:
            return 0.0
        return (self.trades_won / total) * 100
    
    def get_win_rate_emoji(self) -> str:
        """Get emoji based on win rate"""
        wr = self.get_win_rate()
        if wr >= 60:
            return "🟢"
        elif wr >= 40:
            return "🟡"
        else:
            return "🔴"
    
    def get_average_win_pct(self) -> float:
        """Calculate average win percentage"""
        wins = [t.pnl_pct for t in self.closed_trades if t.pnl_pct > 0]
        return sum(wins) / len(wins) if wins else 0.0
    
    def get_average_loss_pct(self) -> float:
        """Calculate average loss percentage"""
        losses = [t.pnl_pct for t in self.closed_trades if t.pnl_pct < 0]
        return sum(losses) / len(losses) if losses else 0.0
    
    def get_average_hold_time(self) -> str:
        """Calculate average holding time"""
        if not self.closed_trades:
            return "0m"
        
        total_minutes = sum(t.hold_time_minutes for t in self.closed_trades)
        avg_minutes = total_minutes / len(self.closed_trades)
        
        hours = int(avg_minutes // 60)
        minutes = int(avg_minutes % 60)
        
        if hours > 24:
            days = hours // 24
            hours = hours % 24
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def get_session_duration(self) -> str:
        """Get current session duration"""
        duration = datetime.now() - self.session_start_time
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def get_last_n_trades(self, n: int = 5) -> List[ClosedTradeRecord]:
        """Get last N closed trades (most recent first)"""
        return sorted(
            self.closed_trades,
            key=lambda x: x.close_time,
            reverse=True
        )[:n]
    
    def get_pnl_vs_start(self) -> tuple:
        """Get PnL compared to starting balance (USD and %)"""
        pnl_pct = (self.total_pnl_usd / self.session_start_balance * 100) if self.session_start_balance > 0 else 0.0
        return self.total_pnl_usd, pnl_pct
    
    def get_summary_dict(self) -> Dict:
        """Get complete statistics summary as dictionary"""
        total_trades = self.get_total_trades()
        win_rate = self.get_win_rate()
        pnl_usd, pnl_pct = self.get_pnl_vs_start()
        
        return {
            'session_duration': self.get_session_duration(),
            'start_balance': self.session_start_balance,
            'total_trades': total_trades,
            'trades_won': self.trades_won,
            'trades_lost': self.trades_lost,
            'trades_breakeven': self.trades_breakeven,
            'win_rate': win_rate,
            'win_rate_emoji': self.get_win_rate_emoji(),
            'total_pnl_usd': self.total_pnl_usd,
            'total_pnl_pct': pnl_pct,
            'best_trade': self.best_trade_pnl,
            'worst_trade': self.worst_trade_pnl,
            'avg_win_pct': self.get_average_win_pct(),
            'avg_loss_pct': self.get_average_loss_pct(),
            'avg_hold_time': self.get_average_hold_time()
        }


# Global session statistics instance
global_session_statistics = SessionStatistics()
