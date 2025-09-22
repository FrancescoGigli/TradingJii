#!/usr/bin/env python3
"""
🧠 ONLINE LEARNING MANAGER

Sistema avanzato per l'apprendimento continuo del trading bot:
- Feedback automatico dai risultati dei trade
- Adattamento dinamico delle soglie
- Performance tracking in tempo reale
- Learning dashboard nel terminale
"""

import logging
import asyncio
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from termcolor import colored
import numpy as np


class OnlineLearningManager:
    """
    Manager per l'apprendimento continuo e il feedback automatico
    """
    
    def __init__(self, rl_agent=None):
        self.rl_agent = rl_agent
        self.learning_active = True
        
        # Trade tracking for automatic feedback
        self.active_trades = {}  # symbol -> trade_info
        self.completed_trades = []
        self.max_completed_history = 500  # Keep last 500 completed trades
        
        # Performance metrics
        self.performance_history = []
        self.learning_stats = {
            'total_trades_tracked': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'total_pnl': 0.0,
            'avg_win_rate': 0.0,
            'avg_reward_per_trade': 0.0,
            'model_updates': 0,
            'last_update': None,
            'adaptive_threshold': 0.5,  # Dynamic threshold
            'performance_trend': 'stable'  # improving, stable, declining
        }
        
        # Adaptive learning parameters
        self.base_threshold = 0.5
        self.threshold_adjustment_factor = 0.05
        self.min_threshold = 0.3
        self.max_threshold = 0.8
        
        # Performance evaluation windows
        self.short_term_window = 20   # Last 20 trades for trend analysis
        self.medium_term_window = 50  # Last 50 trades for stability
        self.long_term_window = 100   # Last 100 trades for overall performance
        
        # Thread safety
        self._lock = threading.Lock()
        self._monitoring_task = None
        
        # Save path for learning data
        self.learning_data_path = Path("trained_models/online_learning_data.json")
        
        # Load existing learning data
        self.load_learning_data()
        
        logging.info(colored("🧠 Online Learning Manager initialized", "cyan"))
    
    def track_trade_opening(self, symbol: str, signal_data: Dict, market_context: Dict, portfolio_state: Dict):
        """
        Inizia il tracking di un trade appena aperto
        
        Args:
            symbol: Symbol del trade
            signal_data: Dati del segnale che ha generato il trade
            market_context: Contesto di mercato al momento dell'apertura
            portfolio_state: Stato del portfolio al momento dell'apertura
        """
        try:
            with self._lock:
                trade_info = {
                    'symbol': symbol,
                    'open_timestamp': datetime.now().isoformat(),
                    'signal_data': signal_data.copy(),
                    'market_context': market_context.copy(),
                    'portfolio_state': portfolio_state.copy(),
                    'rl_state': None,  # Will be set by RL agent
                    'entry_price': 0.0,  # Will be updated when actual entry is confirmed
                    'exit_price': 0.0,
                    'pnl_usd': 0.0,
                    'pnl_percentage': 0.0,
                    'duration_hours': 0.0,
                    'status': 'ACTIVE',
                    'close_reason': None
                }
                
                self.active_trades[symbol] = trade_info
                logging.debug(f"📊 Started tracking trade: {symbol.replace('/USDT:USDT', '')}")
                
        except Exception as e:
            logging.error(f"Error tracking trade opening: {e}")
    
    def update_trade_entry(self, symbol: str, entry_price: float, actual_size: float):
        """
        Aggiorna i dettagli dell'entrata per un trade attivo
        """
        try:
            with self._lock:
                if symbol in self.active_trades:
                    self.active_trades[symbol]['entry_price'] = entry_price
                    self.active_trades[symbol]['actual_size'] = actual_size
                    logging.debug(f"💰 Updated entry for {symbol.replace('/USDT:USDT', '')}: ${entry_price:.6f}")
                
        except Exception as e:
            logging.error(f"Error updating trade entry: {e}")
    
    def track_trade_closing(self, symbol: str, exit_price: float, pnl_usd: float, pnl_percentage: float, close_reason: str = "MANUAL"):
        """
        Traccia la chiusura di un trade e calcola le metriche per il feedback
        
        Args:
            symbol: Symbol del trade chiuso
            exit_price: Prezzo di uscita
            pnl_usd: PnL in USDT
            pnl_percentage: PnL in percentuale
            close_reason: Ragione della chiusura (MANUAL, STOP_LOSS, TAKE_PROFIT, TRAILING)
        """
        try:
            with self._lock:
                if symbol not in self.active_trades:
                    logging.warning(f"Trade closing tracked but no active trade found: {symbol}")
                    return
                
                trade_info = self.active_trades.pop(symbol)
                
                # Calculate duration
                open_time = datetime.fromisoformat(trade_info['open_timestamp'])
                close_time = datetime.now()
                duration_hours = (close_time - open_time).total_seconds() / 3600
                
                # Update trade info
                trade_info.update({
                    'close_timestamp': close_time.isoformat(),
                    'exit_price': exit_price,
                    'pnl_usd': pnl_usd,
                    'pnl_percentage': pnl_percentage,
                    'duration_hours': duration_hours,
                    'status': 'CLOSED',
                    'close_reason': close_reason,
                    'success': pnl_percentage > 0
                })
                
                # STEP 5 FIX: Enforced memory management for completed trades
                self.completed_trades.append(trade_info)
                
                # STEP 5 FIX: Strict enforcement of memory limits
                if len(self.completed_trades) > self.max_completed_history:
                    # FIFO cleanup - remove oldest trades
                    overflow = len(self.completed_trades) - self.max_completed_history
                    self.completed_trades = self.completed_trades[overflow:]
                    logging.debug(f"📝 Learning manager: cleaned {overflow} old completed trades")
                
                # Additional safety check
                if len(self.completed_trades) > self.max_completed_history:
                    logging.warning(f"⚠️ Completed trades still exceed limit: {len(self.completed_trades)} > {self.max_completed_history}")
                    self.completed_trades = self.completed_trades[-self.max_completed_history:]
                
                # Update statistics
                self.learning_stats['total_trades_tracked'] += 1
                if trade_info['success']:
                    self.learning_stats['successful_trades'] += 1
                else:
                    self.learning_stats['failed_trades'] += 1
                
                self.learning_stats['total_pnl'] += pnl_usd
                self.learning_stats['avg_win_rate'] = (
                    self.learning_stats['successful_trades'] / 
                    max(self.learning_stats['total_trades_tracked'], 1)
                ) * 100
                
                # Trigger RL learning from this trade
                asyncio.create_task(self._process_trade_feedback(trade_info))
                
                # Log the completion
                symbol_short = symbol.replace('/USDT:USDT', '')
                status_color = 'green' if trade_info['success'] else 'red'
                status_emoji = '✅' if trade_info['success'] else '❌'
                
                logging.info(colored(
                    f"{status_emoji} Trade completed: {symbol_short} "
                    f"({pnl_percentage:+.2f}% | {duration_hours:.1f}h | {close_reason})",
                    status_color
                ))
                
                # Auto-save learning data
                self.save_learning_data()
                
        except Exception as e:
            logging.error(f"Error tracking trade closing: {e}")
    
    async def _process_trade_feedback(self, trade_info: Dict):
        """
        Processa il feedback di un trade completato per l'apprendimento RL
        """
        try:
            if not self.rl_agent or not self.learning_active:
                return
            
            # Rebuild the RL state from the stored data
            signal_data = trade_info['signal_data']
            market_context = trade_info['market_context'] 
            portfolio_state = trade_info['portfolio_state']
            
            # Build RL state vector
            rl_state = self.rl_agent.build_rl_state(signal_data, market_context, portfolio_state)
            
            # Calculate reward based on trade outcome
            trade_result = {
                'final_pnl_pct': trade_info['pnl_percentage'],
                'duration_hours': trade_info['duration_hours'],
                'close_reason': trade_info['close_reason']
            }
            
            reward = self.rl_agent.calculate_reward(trade_result, portfolio_state)
            
            # Record the experience
            action = True  # Trade was executed
            self.rl_agent.record_trade_result(rl_state, action, reward)
            
            # Update model if we have enough experience
            await asyncio.to_thread(self.rl_agent.update_model, batch_size=32)
            
            self.learning_stats['model_updates'] += 1
            self.learning_stats['last_update'] = datetime.now().isoformat()
            self.learning_stats['avg_reward_per_trade'] = (
                (self.learning_stats['avg_reward_per_trade'] * (self.learning_stats['total_trades_tracked'] - 1) + reward) /
                self.learning_stats['total_trades_tracked']
            )
            
            # Update adaptive threshold based on recent performance
            await self._update_adaptive_threshold()
            
            logging.debug(f"🧠 RL feedback processed: reward={reward:.3f}, threshold={self.learning_stats['adaptive_threshold']:.2f}")
            
        except Exception as e:
            logging.error(f"Error processing RL feedback: {e}")
    
    async def _update_adaptive_threshold(self):
        """
        Aggiorna dinamicamente la soglia di esecuzione basandosi sulle performance recenti
        """
        try:
            if len(self.completed_trades) < self.short_term_window:
                return  # Not enough data yet
            
            # Analyze recent performance
            recent_trades = self.completed_trades[-self.short_term_window:]
            recent_win_rate = sum(1 for trade in recent_trades if trade['success']) / len(recent_trades)
            recent_avg_pnl = np.mean([trade['pnl_percentage'] for trade in recent_trades])
            
            # Calculate performance trend
            if len(self.completed_trades) >= self.medium_term_window:
                older_trades = self.completed_trades[-self.medium_term_window:-self.short_term_window]
                older_win_rate = sum(1 for trade in older_trades if trade['success']) / len(older_trades)
                
                if recent_win_rate > older_win_rate + 0.05:  # 5% improvement
                    self.learning_stats['performance_trend'] = 'improving'
                    # Lower threshold slightly to allow more trades
                    threshold_adjustment = -self.threshold_adjustment_factor
                elif recent_win_rate < older_win_rate - 0.05:  # 5% decline
                    self.learning_stats['performance_trend'] = 'declining'
                    # Raise threshold to be more selective
                    threshold_adjustment = self.threshold_adjustment_factor
                else:
                    self.learning_stats['performance_trend'] = 'stable'
                    threshold_adjustment = 0
                
                # Apply threshold adjustment
                new_threshold = self.learning_stats['adaptive_threshold'] + threshold_adjustment
                self.learning_stats['adaptive_threshold'] = np.clip(
                    new_threshold, self.min_threshold, self.max_threshold
                )
                
                # Update RL agent threshold
                if hasattr(self.rl_agent, 'execution_threshold'):
                    self.rl_agent.execution_threshold = self.learning_stats['adaptive_threshold']
                
        except Exception as e:
            logging.error(f"Error updating adaptive threshold: {e}")
    
    def get_learning_performance_summary(self) -> Dict:
        """
        Restituisce un riassunto delle performance di apprendimento
        """
        try:
            if not self.completed_trades:
                return {
                    'status': 'No completed trades yet',
                    'total_trades': 0
                }
            
            # Calculate various metrics
            total_trades = len(self.completed_trades)
            successful_trades = sum(1 for trade in self.completed_trades if trade['success'])
            win_rate = (successful_trades / total_trades) * 100 if total_trades > 0 else 0
            
            total_pnl = sum(trade['pnl_usd'] for trade in self.completed_trades)
            avg_pnl_per_trade = total_pnl / total_trades if total_trades > 0 else 0
            
            # Recent performance (last 20 trades)
            recent_trades = self.completed_trades[-min(20, total_trades):]
            recent_win_rate = (sum(1 for trade in recent_trades if trade['success']) / len(recent_trades)) * 100
            recent_pnl = sum(trade['pnl_usd'] for trade in recent_trades)
            
            # Best and worst trades
            best_trade = max(self.completed_trades, key=lambda x: x['pnl_percentage'])
            worst_trade = min(self.completed_trades, key=lambda x: x['pnl_percentage'])
            
            # Average duration
            avg_duration = np.mean([trade['duration_hours'] for trade in self.completed_trades])
            
            return {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'recent_win_rate': recent_win_rate,
                'total_pnl_usd': total_pnl,
                'avg_pnl_per_trade': avg_pnl_per_trade,
                'recent_pnl_usd': recent_pnl,
                'best_trade': {
                    'symbol': best_trade['symbol'],
                    'pnl_pct': best_trade['pnl_percentage'],
                    'duration_hours': best_trade['duration_hours']
                },
                'worst_trade': {
                    'symbol': worst_trade['symbol'],
                    'pnl_pct': worst_trade['pnl_percentage'],
                    'duration_hours': worst_trade['duration_hours']
                },
                'avg_duration_hours': avg_duration,
                'model_updates': self.learning_stats['model_updates'],
                'adaptive_threshold': self.learning_stats['adaptive_threshold'],
                'performance_trend': self.learning_stats['performance_trend'],
                'learning_active': self.learning_active
            }
            
        except Exception as e:
            logging.error(f"Error generating learning performance summary: {e}")
            return {'error': str(e)}
    
    def display_learning_dashboard(self):
        """
        Mostra una dashboard di apprendimento nel terminale
        """
        try:
            summary = self.get_learning_performance_summary()
            
            if 'error' in summary:
                print(colored(f"❌ Learning Dashboard Error: {summary['error']}", "red"))
                return
            
            if summary.get('total_trades', 0) == 0:
                print(colored("🧠 LEARNING DASHBOARD: No completed trades yet", "yellow"))
                return
            
            print(colored("\n🧠 ONLINE LEARNING DASHBOARD", "cyan", attrs=['bold']))
            print(colored("=" * 80, "cyan"))
            
            # Overall Performance
            print(colored("📊 OVERALL PERFORMANCE:", "yellow", attrs=['bold']))
            win_rate = summary['win_rate']
            win_rate_color = 'green' if win_rate >= 60 else 'yellow' if win_rate >= 45 else 'red'
            print(f"  🎯 Total Trades: {colored(str(summary['total_trades']), 'cyan')}")
            print(f"  🏆 Win Rate: {colored(f'{win_rate:.1f}%', win_rate_color, attrs=['bold'])}")
            
            total_pnl = summary['total_pnl_usd']
            pnl_color = 'green' if total_pnl > 0 else 'red' if total_pnl < 0 else 'yellow'
            print(f"  💰 Total P&L: {colored(f'{total_pnl:+.2f} USDT', pnl_color, attrs=['bold'])}")
            avg_pnl_text = f'{summary["avg_pnl_per_trade"]:+.2f} USDT'
            print(f"  📈 Avg P&L/Trade: {colored(avg_pnl_text, pnl_color)}")
            avg_duration_text = f'{summary["avg_duration_hours"]:.1f}h'
            print(f"  ⏰ Avg Duration: {colored(avg_duration_text, 'cyan')}")
            
            # Recent Performance  
            print(colored("\n📈 RECENT PERFORMANCE (Last 20 trades):", "yellow", attrs=['bold']))
            recent_win_rate = summary['recent_win_rate']
            recent_win_color = 'green' if recent_win_rate >= 60 else 'yellow' if recent_win_rate >= 45 else 'red'
            print(f"  🎯 Recent Win Rate: {colored(f'{recent_win_rate:.1f}%', recent_win_color, attrs=['bold'])}")
            
            recent_pnl = summary['recent_pnl_usd']
            recent_pnl_color = 'green' if recent_pnl > 0 else 'red' if recent_pnl < 0 else 'yellow'
            print(f"  💵 Recent P&L: {colored(f'{recent_pnl:+.2f} USDT', recent_pnl_color, attrs=['bold'])}")
            
            # Performance Trend
            trend = summary['performance_trend']
            trend_colors = {'improving': 'green', 'stable': 'yellow', 'declining': 'red'}
            trend_emojis = {'improving': '📈', 'stable': '➡️', 'declining': '📉'}
            print(f"  📊 Trend: {trend_emojis.get(trend, '❓')} {colored(trend.upper(), trend_colors.get(trend, 'white'), attrs=['bold'])}")
            
            # Adaptive Learning Status
            print(colored("\n🤖 ADAPTIVE LEARNING STATUS:", "yellow", attrs=['bold']))
            threshold = summary['adaptive_threshold']
            threshold_color = 'green' if 0.4 <= threshold <= 0.6 else 'yellow'
            print(f"  🎚️ Current Threshold: {colored(f'{threshold:.2f}', threshold_color, attrs=['bold'])}")
            print(f"  🔄 Model Updates: {colored(str(summary['model_updates']), 'cyan')}")
            
            learning_status = "ACTIVE" if summary['learning_active'] else "INACTIVE"
            learning_color = 'green' if summary['learning_active'] else 'red'
            print(f"  🧠 Learning Status: {colored(learning_status, learning_color, attrs=['bold'])}")
            
            # Best & Worst Trades
            print(colored("\n🏆 TRADE HIGHLIGHTS:", "yellow", attrs=['bold']))
            best = summary['best_trade']
            worst = summary['worst_trade']
            
            best_symbol = best['symbol'].replace('/USDT:USDT', '')
            best_pnl_text = f'{best["pnl_pct"]:+.2f}%'
            worst_symbol = worst['symbol'].replace('/USDT:USDT', '')
            worst_pnl_text = f'{worst["pnl_pct"]:+.2f}%'
            
            print(f"  🥇 Best Trade: {colored(best_symbol, 'green')} "
                  f"{colored(best_pnl_text, 'green', attrs=['bold'])} "
                  f"({best['duration_hours']:.1f}h)")
                  
            print(f"  🥉 Worst Trade: {colored(worst_symbol, 'red')} "
                  f"{colored(worst_pnl_text, 'red', attrs=['bold'])} "
                  f"({worst['duration_hours']:.1f}h)")
            
            print(colored("=" * 80, "cyan"))
            
        except Exception as e:
            logging.error(f"Error displaying learning dashboard: {e}")
            print(colored(f"❌ Dashboard Error: {e}", "red"))
    
    def save_learning_data(self):
        """Salva i dati di apprendimento su file"""
        try:
            self.learning_data_path.parent.mkdir(exist_ok=True)
            
            learning_data = {
                'learning_stats': self.learning_stats,
                'completed_trades': self.completed_trades[-100:],  # Save last 100 trades only
                'adaptive_threshold': self.learning_stats['adaptive_threshold'],
                'save_timestamp': datetime.now().isoformat()
            }
            
            with open(self.learning_data_path, 'w') as f:
                json.dump(learning_data, f, indent=2, default=str)
            
        except Exception as e:
            logging.error(f"Error saving learning data: {e}")
    
    def load_learning_data(self):
        """Carica i dati di apprendimento da file"""
        try:
            if self.learning_data_path.exists():
                with open(self.learning_data_path, 'r') as f:
                    learning_data = json.load(f)
                
                self.learning_stats.update(learning_data.get('learning_stats', {}))
                self.completed_trades = learning_data.get('completed_trades', [])
                
                # Update RL agent threshold if available
                if self.rl_agent and hasattr(self.rl_agent, 'execution_threshold'):
                    self.rl_agent.execution_threshold = self.learning_stats.get('adaptive_threshold', 0.5)
                
                logging.info(f"📚 Loaded learning data: {len(self.completed_trades)} completed trades")
            
        except Exception as e:
            logging.warning(f"Error loading learning data: {e}")
    
    def get_active_trades_count(self) -> int:
        """Restituisce il numero di trade attualmente attivi"""
        return len(self.active_trades)
    
    def get_active_trades_info(self) -> List[Dict]:
        """Restituisce informazioni sui trade attualmente attivi"""
        try:
            active_info = []
            for symbol, trade_info in self.active_trades.items():
                duration_hours = (
                    datetime.now() - datetime.fromisoformat(trade_info['open_timestamp'])
                ).total_seconds() / 3600
                
                active_info.append({
                    'symbol': symbol.replace('/USDT:USDT', ''),
                    'signal': trade_info['signal_data']['signal_name'],
                    'entry_price': trade_info['entry_price'],
                    'duration_hours': duration_hours,
                    'confidence': trade_info['signal_data']['confidence']
                })
            
            return active_info
            
        except Exception as e:
            logging.error(f"Error getting active trades info: {e}")
            return []


# Global instance (will be initialized by the RL agent)
global_online_learning_manager = None


def initialize_online_learning_manager(rl_agent=None):
    """Initialize the global online learning manager"""
    global global_online_learning_manager
    if global_online_learning_manager is None:
        global_online_learning_manager = OnlineLearningManager(rl_agent)
    return global_online_learning_manager
