#!/usr/bin/env python3
"""
📊 STATS CALCULATOR

Calcola statistiche e metriche per il dashboard.
Separato dalla UI per migliorare testabilità.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import config


class StatsCalculator:
    """Calcola statistiche di sessione e portfolio"""
    
    @staticmethod
    def calculate_session_stats(session_stats, current_balance: float) -> Dict[str, Any]:
        """
        Calcola statistiche principali della sessione
        
        Returns:
            Dict con: balance, trades, win_rate, pnl, best_worst
        """
        total_trades = session_stats.get_total_trades()
        win_rate = session_stats.get_win_rate()
        win_rate_emoji = session_stats.get_win_rate_emoji()
        
        # PnL totale = Balance corrente - Balance iniziale
        pnl_usd = current_balance - session_stats.session_start_balance
        pnl_pct = (pnl_usd / session_stats.session_start_balance * 100) if session_stats.session_start_balance > 0 else 0.0
        
        return {
            'balance': {
                'current': current_balance,
                'start': session_stats.session_start_balance,
            },
            'trades': {
                'total': total_trades,
                'won': session_stats.trades_won,
                'lost': session_stats.trades_lost,
                'avg_win_pct': session_stats.get_average_win_pct(),
            },
            'win_rate': {
                'value': win_rate,
                'emoji': win_rate_emoji,
            },
            'pnl': {
                'usd': pnl_usd,
                'pct': pnl_pct,
            },
            'best_worst': {
                'best_pnl': session_stats.best_trade_pnl,
                'worst_pnl': session_stats.worst_trade_pnl,
                'avg_hold_time': session_stats.get_average_hold_time(),
            }
        }
    
    @staticmethod
    def calculate_adaptive_stats(adaptive_sizing) -> Dict[str, Any]:
        """
        Calcola statistiche adaptive position sizing
        
        Returns:
            Dict con: cycle, active, blocked, win_rate, avg_size
        """
        if adaptive_sizing is None:
            return {
                'enabled': False,
                'cycle': 0,
                'active': 0,
                'blocked': 0,
                'win_rate': 0,
                'avg_size': 0,
            }
        
        stats = adaptive_sizing.get_memory_stats()
        
        # Calculate average size from memory
        memory_values = list(adaptive_sizing.symbol_memory.values())
        total = len(memory_values)
        
        if total > 0:
            total_size = sum(m.current_size for m in memory_values)
            avg_size = total_size / total
        else:
            avg_size = 0
        
        return {
            'enabled': True,
            'cycle': stats.get('cycle', 0),
            'active': total,
            'blocked': stats.get('blocked_symbols', 0),
            'win_rate': stats.get('win_rate', 0),
            'avg_size': avg_size,
        }
    
    @staticmethod
    def calculate_portfolio_summary(position_manager) -> Dict[str, Any]:
        """
        Calcola summary del portfolio
        
        Returns:
            Dict con: active_positions, used_margin, available_balance, 
                     unrealized_pnl, trailing_count
        """
        summary = position_manager.safe_get_session_summary()
        
        active_positions = position_manager.safe_get_all_active_positions()
        trailing_count = sum(
            1 for pos in active_positions 
            if hasattr(pos, 'trailing_data') and pos.trailing_data and pos.trailing_data.enabled
        )
        
        return {
            'active_positions': summary.get('active_positions', 0),
            'used_margin': summary.get('used_margin', 0),
            'available_balance': summary.get('available_balance', 0),
            'unrealized_pnl': summary.get('unrealized_pnl', 0),
            'trailing_count': trailing_count,
            'total_active': len(active_positions),
        }
    
    @staticmethod
    def get_protection_status(positions: list) -> Dict[str, int]:
        """
        Calcola status protezioni (trailing, stuck, fixed)
        
        Args:
            positions: Lista posizioni attive
            
        Returns:
            Dict con: trailing, stuck, fixed counts
        """
        trailing_count = 0
        stuck_count = 0
        fixed_count = 0
        
        for pos in positions:
            is_trailing = (hasattr(pos, 'trailing_data') and 
                          pos.trailing_data and 
                          pos.trailing_data.enabled)
            
            if is_trailing:
                trailing_count += 1
            elif pos.unrealized_pnl_pct >= 10:
                stuck_count += 1
            else:
                fixed_count += 1
        
        return {
            'trailing': trailing_count,
            'stuck': stuck_count,
            'fixed': fixed_count,
            'total': len(positions),
        }
    
    @staticmethod
    def get_max_positions_info(position_manager) -> Dict[str, int]:
        """
        Ottiene info su max positions e capacità
        
        Returns:
            Dict con: max, current, available
        """
        max_positions = config.MAX_CONCURRENT_POSITIONS
        current_open = position_manager.safe_get_position_count()
        available = max_positions - current_open
        
        return {
            'max': max_positions,
            'current': current_open,
            'available': available,
            'is_full': current_open >= max_positions,
        }
    
    @staticmethod
    def calculate_position_metrics(pos) -> Dict[str, Any]:
        """
        Calcola metriche per una singola posizione
        
        Returns:
            Dict con metriche calcolate (ROE, liquidation, etc.)
        """
        # Calculate ROE
        roe_pct = pos.unrealized_pnl_pct
        
        # Check trailing status
        is_trailing_active = (hasattr(pos, 'trailing_data') and 
                             pos.trailing_data and 
                             pos.trailing_data.enabled)
        
        # Calculate liquidation price
        if pos.side in ['buy', 'long']:
            liq_price = pos.entry_price * (1 - 1 / pos.leverage)
        else:
            liq_price = pos.entry_price * (1 + 1 / pos.leverage)
        
        # Distance to liquidation
        distance_to_liq_pct = abs((pos.current_price - liq_price) / liq_price) * 100
        
        # Calculate SL percentages
        sl_price = pos.real_stop_loss if (hasattr(pos, 'real_stop_loss') and pos.real_stop_loss) else pos.stop_loss
        
        if pos.side in ['buy', 'long']:
            risk_pct = ((sl_price - pos.entry_price) / pos.entry_price) * 100
        else:
            risk_pct = ((pos.entry_price - sl_price) / pos.entry_price) * 100
        
        sl_roe_pct = risk_pct * pos.leverage
        
        # Price movement
        if pos.side in ['buy', 'long']:
            price_move_pct = ((pos.current_price - pos.entry_price) / pos.entry_price) * 100
        else:
            price_move_pct = ((pos.entry_price - pos.current_price) / pos.entry_price) * 100
        
        # Time in position
        time_str = "N/A"
        if pos.entry_time:
            try:
                entry_dt = datetime.fromisoformat(pos.entry_time)
                now = datetime.now()
                delta = now - entry_dt
                hours = int(delta.total_seconds() // 3600)
                minutes = int((delta.total_seconds() % 3600) // 60)
                
                if hours > 0:
                    time_str = f"{hours}h {minutes}m"
                else:
                    time_str = f"{minutes}m"
            except:
                pass
        
        return {
            'roe_pct': roe_pct,
            'is_trailing': is_trailing_active,
            'liq_price': liq_price,
            'distance_to_liq_pct': distance_to_liq_pct,
            'sl_price': sl_price,
            'risk_pct': risk_pct,
            'sl_roe_pct': sl_roe_pct,
            'price_move_pct': price_move_pct,
            'time_in_position': time_str,
        }
    
    @staticmethod
    def calculate_initial_margin(pos) -> tuple[float, str]:
        """
        Calcola Initial Margin (IM) con source
        
        Returns:
            (margin_value, source) where source is 'Bybit' or 'Calculated'
        """
        if hasattr(pos, 'real_initial_margin') and pos.real_initial_margin is not None:
            return pos.real_initial_margin, "Bybit"
        else:
            margin = pos.position_size / pos.leverage if pos.position_size > 0 else 0
            return margin, "Calculated"
    
    @staticmethod
    def calculate_hold_time(entry_time: Optional[str], close_time: Optional[str]) -> str:
        """
        Calcola hold time formattato
        
        Returns:
            Stringa formattata (e.g. "2h 15m" o "45m")
        """
        if not entry_time or not close_time:
            return "N/A"
        
        try:
            entry_dt = datetime.fromisoformat(entry_time)
            close_dt = datetime.fromisoformat(close_time)
            hold_minutes = int((close_dt - entry_dt).total_seconds() / 60)
            
            if hold_minutes < 60:
                return f"{hold_minutes}m"
            else:
                hours = hold_minutes // 60
                minutes = hold_minutes % 60
                return f"{hours}h {minutes}m"
        except:
            return "N/A"
