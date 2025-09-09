"""
Advanced Terminal Display System for Trading Bot

FEATURES:
- Colorful trading dashboard
- Signal summary tables
- Performance metrics display
- Real-time portfolio overview
- Enhanced visual indicators
"""

import os
import logging
from termcolor import colored
from datetime import datetime
import pandas as pd
from typing import Dict, List, Optional, Any

class TradingTerminalDisplay:
    """
    Enhanced terminal display system for professional trading bot interface
    """
    
    def __init__(self):
        self.signals_history = []
        self.session_stats = {
            'total_signals': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'neutral_signals': 0,
            'start_time': datetime.now()
        }
        
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def print_header(self, mode="DEMO"):
        """Print colorful header with bot info"""
        print(colored("=" * 100, "cyan"))
        print(colored("🤖 TRAE TRADING BOT - RISTRUTTURATO & OTTIMIZZATO", "yellow", attrs=['bold']))
        print(colored("=" * 100, "cyan"))
        
        mode_color = "magenta" if mode == "DEMO" else "red"
        mode_icon = "🎮" if mode == "DEMO" else "🔴"
        
        print(f"{colored('MODE:', 'white')} {colored(mode_icon + ' ' + mode, mode_color, attrs=['bold'])}")
        print(f"{colored('TIME:', 'white')} {colored(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'green')}")
        print(f"{colored('STATUS:', 'white')} {colored('✅ OPERATIONAL', 'green', attrs=['bold'])}")
        print(colored("-" * 100, "blue"))
        
    def print_session_summary(self):
        """Print session statistics summary"""
        runtime = datetime.now() - self.session_stats['start_time']
        hours, remainder = divmod(runtime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        print(colored("📊 SESSION SUMMARY", "yellow", attrs=['bold']))
        print(colored("-" * 50, "yellow"))
        
        print(f"{colored('⏰ Runtime:', 'cyan')} {colored(f'{hours:02d}h {minutes:02d}m {seconds:02d}s', 'white')}")
        print(f"{colored('🎯 Total Signals:', 'cyan')} {colored(str(self.session_stats['total_signals']), 'white')}")
        print(f"{colored('📈 BUY Signals:', 'cyan')} {colored(str(self.session_stats['buy_signals']), 'green')}")
        print(f"{colored('📉 SELL Signals:', 'cyan')} {colored(str(self.session_stats['sell_signals']), 'red')}")
        print(f"{colored('😐 NEUTRAL Signals:', 'cyan')} {colored(str(self.session_stats['neutral_signals']), 'yellow')}")
        
        if self.session_stats['total_signals'] > 0:
            buy_pct = (self.session_stats['buy_signals'] / self.session_stats['total_signals']) * 100
            sell_pct = (self.session_stats['sell_signals'] / self.session_stats['total_signals']) * 100
            print(f"{colored('📊 Signal Distribution:', 'cyan')} {colored(f'{buy_pct:.1f}% BUY', 'green')} | {colored(f'{sell_pct:.1f}% SELL', 'red')}")
        
        print(colored("-" * 50, "yellow"))
        
    def print_signal_table(self, recent_signals_limit=10):
        """Print recent signals in a formatted table"""
        if not self.signals_history:
            return
            
        print(colored("📋 RECENT TRADING SIGNALS", "yellow", attrs=['bold']))
        print(colored("-" * 100, "yellow"))
        
        # Table header
        header = f"{'TIME':<8} {'SYMBOL':<20} {'SIGNAL':<6} {'CONFIDENCE':<10} {'PRICE':<12} {'STOP LOSS':<12} {'RISK':<8}"
        print(colored(header, "white", attrs=['bold']))
        print(colored("-" * 100, "white"))
        
        # Recent signals (last N)
        recent_signals = self.signals_history[-recent_signals_limit:]
        for signal in recent_signals:
            time_str = signal['time'].strftime("%H:%M")
            symbol_short = signal['symbol'].replace('/USDT:USDT', '').ljust(20)
            
            # Color coding for signals
            if signal['signal'] == 'BUY':
                signal_colored = colored('📈 BUY', 'green', attrs=['bold'])
            elif signal['signal'] == 'SELL':
                signal_colored = colored('📉 SELL', 'red', attrs=['bold'])
            else:
                signal_colored = colored('😐 NEUT', 'yellow')
            
            confidence_str = f"{signal.get('confidence', 0):.3f}".ljust(10)
            price_str = f"${signal.get('price', 0):.6f}".ljust(12)
            stop_loss_str = f"${signal.get('stop_loss', 0):.6f}".ljust(12)
            risk_str = f"{signal.get('risk_pct', 0):.2f}%".ljust(8)
            
            row = f"{time_str:<8} {symbol_short} {signal_colored} {confidence_str} {price_str} {stop_loss_str} {risk_str}"
            print(row)
        
        print(colored("-" * 100, "yellow"))
    
    def print_market_overview(self, symbols_data: List[Dict]):
        """Print market overview with top movers"""
        if not symbols_data:
            return
            
        print(colored("📈 MARKET OVERVIEW - TOP PERFORMERS", "cyan", attrs=['bold']))
        print(colored("-" * 80, "cyan"))
        
        # Sort by volatility for top movers
        sorted_symbols = sorted(symbols_data, key=lambda x: abs(x.get('volatility', 0)), reverse=True)[:8]
        
        # Table header
        header = f"{'SYMBOL':<20} {'PRICE':<12} {'RSI':<6} {'VOL%':<8} {'TREND':<8}"
        print(colored(header, "white", attrs=['bold']))
        print(colored("-" * 60, "white"))
        
        for data in sorted_symbols:
            symbol_short = data['symbol'].replace('/USDT:USDT', '').ljust(20)
            price_str = f"${data.get('price', 0):.6f}".ljust(12)
            rsi = data.get('rsi', 50)
            rsi_str = f"{rsi:.1f}".ljust(6)
            vol = data.get('volatility', 0)
            vol_str = f"{vol:+.2f}%".ljust(8)
            
            # Color coding
            if rsi > 70:
                rsi_colored = colored(rsi_str, 'red')
            elif rsi < 30:
                rsi_colored = colored(rsi_str, 'green')
            else:
                rsi_colored = colored(rsi_str, 'yellow')
                
            if vol > 0:
                vol_colored = colored(vol_str, 'green')
                trend_colored = colored('📈', 'green')
            elif vol < 0:
                vol_colored = colored(vol_str, 'red')
                trend_colored = colored('📉', 'red')
            else:
                vol_colored = colored(vol_str, 'yellow')
                trend_colored = colored('➡️', 'yellow')
            
            row = f"{symbol_short} {price_str} {rsi_colored} {vol_colored} {trend_colored}"
            print(row)
        
        print(colored("-" * 80, "cyan"))
    
    def print_portfolio_status(self, balance: float, open_positions: int = 0, risk_level: str = "LOW"):
        """Print portfolio status with risk indicators"""
        print(colored("💼 PORTFOLIO STATUS", "green", attrs=['bold']))
        print(colored("-" * 50, "green"))
        
        # Balance display
        balance_str = f"${balance:,.2f}"
        print(f"{colored('💰 Balance:', 'cyan')} {colored(balance_str, 'yellow', attrs=['bold'])}")
        # Import from config to avoid hardcoding
        from config import MAX_CONCURRENT_POSITIONS
        print(f"{colored('🔢 Open Positions:', 'cyan')} {colored(str(open_positions), 'white')} / {MAX_CONCURRENT_POSITIONS} max")
        
        # Risk level color coding
        risk_colors = {'LOW': 'green', 'MEDIUM': 'yellow', 'HIGH': 'red', 'CRITICAL': 'magenta'}
        risk_color = risk_colors.get(risk_level, 'white')
        risk_icon = {'LOW': '🟢', 'MEDIUM': '🟡', 'HIGH': '🔴', 'CRITICAL': '🚨'}
        
        print(f"{colored('🛡️ Risk Level:', 'cyan')} {colored(risk_icon.get(risk_level, '⚪') + ' ' + risk_level, risk_color, attrs=['bold'])}")
        print(colored("-" * 50, "green"))
    
    def display_signal_decision(self, symbol: str, signal: str, confidence: float, 
                              price: float, stop_loss: float = None, position_size: float = None,
                              risk_pct: float = None, atr: float = None):
        """Display trading signal with enhanced formatting"""
        
        # Store signal for history
        signal_data = {
            'time': datetime.now(),
            'symbol': symbol,
            'signal': signal,
            'confidence': confidence,
            'price': price,
            'stop_loss': stop_loss,
            'position_size': position_size,
            'risk_pct': risk_pct
        }
        self.signals_history.append(signal_data)
        
        # Update session stats
        self.session_stats['total_signals'] += 1
        if signal == 'BUY':
            self.session_stats['buy_signals'] += 1
        elif signal == 'SELL':
            self.session_stats['sell_signals'] += 1
        else:
            self.session_stats['neutral_signals'] += 1
        
        # Display signal box
        symbol_short = symbol.replace('/USDT:USDT', '')
        
        if signal == 'BUY':
            signal_color = 'green'
            signal_icon = '🚀'
            signal_text = 'BUY SIGNAL'
        elif signal == 'SELL':
            signal_color = 'red'
            signal_icon = '📉'
            signal_text = 'SELL SIGNAL'
        else:
            signal_color = 'yellow'
            signal_icon = '😐'
            signal_text = 'NEUTRAL'
        
        print(colored("╔" + "=" * 78 + "╗", signal_color, attrs=['bold']))
        print(colored(f"║ {signal_icon} {signal_text.center(72)} ║", signal_color, attrs=['bold']))
        print(colored("╠" + "=" * 78 + "╣", signal_color))
        
        # Signal details
        print(colored(f"║ 📊 Symbol: {colored(symbol_short, 'yellow', attrs=['bold']).ljust(28)} Confidence: {colored(f'{confidence:.1%}', 'white', attrs=['bold'])} ║", signal_color))
        print(colored(f"║ 💰 Price: {colored(f'${price:.6f}', 'yellow').ljust(28)} Size: {colored(f'{position_size:.2f}' if position_size else 'N/A', 'white')} ║", signal_color))
        
        if stop_loss and risk_pct:
            stop_distance = abs(price - stop_loss) / price * 100
            print(colored(f"║ 🛡️ Stop Loss: {colored(f'${stop_loss:.6f}', 'cyan').ljust(24)} Risk: {colored(f'{risk_pct:.2f}%', 'white')} ║", signal_color))
            print(colored(f"║ 📏 Stop Distance: {colored(f'{stop_distance:.2f}%', 'cyan').ljust(20)} ATR: {colored(f'{atr:.6f}' if atr else 'N/A', 'white')} ║", signal_color))
        
        print(colored("╚" + "=" * 78 + "╝", signal_color, attrs=['bold']))
        print()  # Add spacing
    
    def display_analysis_progress(self, current: int, total: int, symbol: str):
        """Display analysis progress with progress bar"""
        progress = current / total
        bar_length = 50
        filled = int(bar_length * progress)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        symbol_short = symbol.replace('/USDT:USDT', '')
        progress_line = f"[{current:2d}/{total:2d}] {bar} {progress:.1%} | Analyzing {symbol_short}"
        
        print(colored(progress_line, "cyan"), end='\r')
        
    def display_cycle_complete(self):
        """Display active and closed positions summary"""
        try:
            from core.smart_position_manager import global_smart_position_manager
            
            print(colored("\n📊 TRADING SESSION STATUS", "green", attrs=['bold']))
            print(colored("=" * 100, "green"))
            
            # Get position data
            open_positions = global_smart_position_manager.get_active_positions()
            closed_positions = global_smart_position_manager.get_closed_positions()
            session_summary = global_smart_position_manager.get_session_summary()
            
            # Display open positions
            if open_positions:
                print(colored("🟢 POSIZIONI ATTUALMENTE APERTE", "green", attrs=['bold']))
                print(colored("┌─────┬────────┬──────┬─────────────┬─────────────┬──────────┬───────────┐", "cyan"))
                print(colored("│  #  │ SYMBOL │ SIDE │    ENTRY    │   CURRENT   │  PNL %   │   PNL $   │", "white", attrs=['bold']))
                print(colored("├─────┼────────┼──────┼─────────────┼─────────────┼──────────┼───────────┤", "cyan"))
                
                for i, pos in enumerate(open_positions, 1):
                    symbol = pos.symbol.replace('/USDT:USDT', '')[:6]
                    side_color = "green" if pos.side == "buy" else "red"
                    pnl_color = "green" if pos.unrealized_pnl_pct > 0 else "red" if pos.unrealized_pnl_pct < 0 else "white"
                    
                    print(colored(f"│{i:^5}│", "white") + 
                          colored(f"{symbol:^8}", "cyan") + colored("│", "white") +
                          colored(f"{pos.side.upper():^6}", side_color) + colored("│", "white") +
                          colored(f"${pos.entry_price:.6f}".center(13), "white") + colored("│", "white") +
                          colored(f"${pos.current_price:.6f}".center(13), "white") + colored("│", "white") +
                          colored(f"{pos.unrealized_pnl_pct:+.2f}%".center(10), pnl_color) + colored("│", "white") +
                          colored(f"${pos.unrealized_pnl_usd:+.2f}".center(11), pnl_color) + colored("│", "white"))
                
                print(colored("└─────┴────────┴──────┴─────────────┴─────────────┴──────────┴───────────┘", "cyan"))
                
                # Total for open positions
                total_pnl_usd = session_summary.get('unrealized_pnl', 0)
                total_pnl_pct = session_summary.get('total_pnl_pct', 0)
                pnl_color = "green" if total_pnl_usd > 0 else "red" if total_pnl_usd < 0 else "white"
                
                print(colored(f"💰 TOTALE APERTE: {len(open_positions)} posizioni | ", "white") + 
                      colored(f"P&L: ${total_pnl_usd:+.2f} ({total_pnl_pct:+.2f}%)", pnl_color, attrs=['bold']))
            else:
                print(colored("📭 NESSUNA POSIZIONE APERTA AL MOMENTO", "yellow"))
            
            print()
            
            # Display closed positions (this session)
            if closed_positions:
                recent_closed = closed_positions[-5:]  # Show last 5
                print(colored("🔴 POSIZIONI CHIUSE (SESSIONE CORRENTE)", "red", attrs=['bold']))
                print(colored("┌─────┬────────┬──────┬─────────────┬─────────────┬──────────┬───────────┐", "cyan"))
                print(colored("│  #  │ SYMBOL │ SIDE │   CLOSE $   │   REASON    │  PNL %   │   PNL $   │", "white", attrs=['bold']))
                print(colored("├─────┼────────┼──────┼─────────────┼─────────────┼──────────┼───────────┤", "cyan"))
                
                for i, pos in enumerate(recent_closed, 1):
                    symbol = pos.symbol.replace('/USDT:USDT', '')[:6]
                    side_color = "green" if pos.side == "buy" else "red"
                    pnl_color = "green" if pos.final_pnl_pct > 0 else "red"
                    reason = (pos.close_reason or "UNKNOWN")[:11]
                    
                    print(colored(f"│{i:^5}│", "white") + 
                          colored(f"{symbol:^8}", "cyan") + colored("│", "white") +
                          colored(f"{pos.side.upper():^6}", side_color) + colored("│", "white") +
                          colored(f"${pos.current_price:.6f}".center(13), "white") + colored("│", "white") +
                          colored(f"{reason:^13}", "yellow") + colored("│", "white") +
                          colored(f"{pos.final_pnl_pct:+.2f}%".center(10), pnl_color) + colored("│", "white") +
                          colored(f"${pos.final_pnl_usd:+.2f}".center(11), pnl_color) + colored("│", "white"))
                
                print(colored("└─────┴────────┴──────┴─────────────┴─────────────┴──────────┴───────────┘", "cyan"))
                
                # Total for closed positions
                total_realized = sum(pos.final_pnl_usd for pos in closed_positions if pos.final_pnl_usd)
                realized_color = "green" if total_realized > 0 else "red" if total_realized < 0 else "white"
                
                print(colored(f"💰 TOTALE CHIUSE: {len(closed_positions)} posizioni | ", "white") + 
                      colored(f"Realized P&L: ${total_realized:+.2f}", realized_color, attrs=['bold']))
            else:
                print(colored("📋 NESSUNA POSIZIONE CHIUSA QUESTA SESSIONE", "yellow"))
            
            print(colored("=" * 100, "green"))
            print(colored("⏳ Prossimo ciclo in 5 minuti...", "blue", attrs=['bold']))
            print()
            
        except Exception as e:
            logging.error(f"Error displaying trading session status: {e}")
            # Fallback display
            print(colored("📊 SESSION STATUS", "yellow"))
            print(colored("⏳ Next cycle in 5 minutes...", "blue"))
    
    def display_model_loading_status(self, timeframes: List[str], status: Dict[str, bool]):
        """Display model loading status with visual indicators"""
        print(colored("🧠 ML MODELS STATUS", "purple", attrs=['bold']))
        print(colored("-" * 40, "purple"))
        
        for tf in timeframes:
            if status.get(tf, False):
                icon = "✅"
                color = "green"
                text = "LOADED"
            else:
                icon = "❌"
                color = "red"
                text = "FAILED"
            
            print(f"{icon} {colored(f'Model {tf}:', 'cyan')} {colored(text, color)}")
        
        working_models = sum(1 for s in status.values() if s)
        total_models = len(status)
        
        if working_models == total_models:
            overall_status = colored("🎉 ALL MODELS OPERATIONAL", "green", attrs=['bold'])
        elif working_models > 0:
            overall_status = colored(f"⚠️ {working_models}/{total_models} MODELS WORKING", "yellow", attrs=['bold'])
        else:
            overall_status = colored("🚨 NO MODELS AVAILABLE", "red", attrs=['bold'])
        
        print(f"\n{overall_status}")
        print(colored("-" * 40, "purple"))
        print()
    
    def display_countdown_enhanced(self, seconds: int):
        """Enhanced countdown with visual elements"""
        minutes, secs = divmod(seconds, 60)
        countdown_str = f"⏳ Next cycle: {minutes:02d}:{secs:02d}"
        
        # Color changes based on time left
        if seconds > 180:  # > 3 minutes
            color = "green"
        elif seconds > 60:  # > 1 minute
            color = "yellow"
        else:  # < 1 minute
            color = "red"
        
        print(colored(countdown_str, color, attrs=['bold']), end='\r')


# Global display instance
terminal_display = TradingTerminalDisplay()

def init_terminal_display(mode="DEMO"):
    """Initialize enhanced terminal display"""
    terminal_display.clear_screen()
    terminal_display.print_header(mode)

def display_enhanced_signal(symbol: str, signal: str, confidence: float, 
                          price: float, stop_loss: float = None, 
                          position_size: float = None, risk_pct: float = None, 
                          atr: float = None):
    """Display enhanced signal with all details"""
    terminal_display.display_signal_decision(
        symbol, signal, confidence, price, stop_loss, 
        position_size, risk_pct, atr
    )

def display_analysis_progress(current: int, total: int, symbol: str):
    """Display analysis progress"""
    terminal_display.display_analysis_progress(current, total, symbol)

def display_cycle_complete():
    """Display cycle completion"""
    terminal_display.display_cycle_complete()

def display_model_status(timeframes: List[str], status: Dict[str, bool]):
    """Display model loading status"""
    terminal_display.display_model_loading_status(timeframes, status)

def display_portfolio_status(balance: float, open_positions: int = 0, risk_level: str = "LOW"):
    """Display portfolio status"""
    terminal_display.print_portfolio_status(balance, open_positions, risk_level)

def display_wallet_and_positions(position_tracker_summary: Dict, leverage: int = 10):
    """
    Display enhanced wallet status and active positions table
    """
    try:
        # Import here to avoid circular imports
        from core.position_tracker import global_position_tracker
        
        summary = position_tracker_summary
        
        print(colored("💼 TRAE WALLET STATUS", "cyan", attrs=['bold']))
        print(colored("═" * 80, "cyan"))
        
        # Wallet info
        wallet_balance = summary['wallet_balance']
        available_balance = summary['available_balance']
        total_invested = summary['total_invested']
        active_count = summary['active_positions']
        
        # Calculate position size per trade (5% of current wallet)
        position_size_per_trade = wallet_balance * 0.05
        
        print(f"{colored('💰 Wallet:', 'white')} {colored(f'{wallet_balance:.2f} USDT', 'yellow', attrs=['bold'])}")
        print(f"{colored('📊 Position Size per Trade:', 'white')} {colored(f'{position_size_per_trade:.2f} USDT', 'white')} {colored(f'(5% of wallet)', 'cyan')}")
        print(f"{colored('🎯 Active Positions:', 'white')} {colored(str(active_count), 'green' if active_count > 0 else 'yellow')}")
        print(f"{colored('💵 Total Invested:', 'white')} {colored(f'{total_invested:.2f} USDT', 'white')} {colored(f'({active_count} × {position_size_per_trade:.0f} USDT)', 'cyan')}")
        print(f"{colored('📈 Available Capital:', 'white')} {colored(f'{available_balance:.2f} USDT', 'green')}")
        
        # Trading parameters
        base_risk = 3.0
        sl_pct = base_risk / leverage
        tp_pct = sl_pct * 2
        
        print(f"{colored('⚖️ Leverage:', 'white')} {colored(f'{leverage}x', 'white')} | {colored('🛡️ Risk per Trade:', 'white')} {colored(f'{base_risk}%', 'red')} | {colored('🎪 Trailing:', 'white')} {colored('ON', 'green')}")
        print(f"{colored('📉 Stop Loss:', 'white')} {colored(f'{sl_pct:.2f}%', 'red')} | {colored('📈 Take Profit:', 'white')} {colored(f'{tp_pct:.2f}%', 'green')} | {colored('🔄 Trail Start:', 'white')} {colored('1.0%', 'yellow')}")
        
        print(colored("═" * 80, "cyan"))
        
        # Active positions table with complete TP/SL details
        if active_count > 0:
            print(colored("📋 ACTIVE POSITIONS (Complete Details)", "yellow", attrs=['bold']))
            print(colored("─" * 130, "yellow"))
            
            # Wider table header with TP included
            header = f"{'#':<2} {'SYMBOL':<10} {'SIDE':<4} {'ENTRY':<12} {'CURRENT':<12} {'STOP LOSS':<12} {'TAKE PROFIT':<12} {'PnL%':<8} {'PnL$':<8} {'STATUS':<12}"
            print(colored(header, "white", attrs=['bold']))
            print(colored("─" * 130, "white"))
            
            # Active positions rows with full details
            for i, (pos_id, position) in enumerate(global_position_tracker.active_positions.items(), 1):
                symbol_short = position['symbol'].replace('/USDT:USDT', '')[:10]
                side = position['side'][:4]
                entry = position['entry_price']
                current = position['current_price']
                sl = position.get('stop_loss', 0)
                tp = position.get('take_profit', 0)
                pnl_pct = position['unrealized_pnl_pct']
                pnl_usd = position['unrealized_pnl_usd']
                
                # Enhanced status with trailing info
                if position.get('trailing_active', False):
                    status = colored('🎪 TRAILING', 'yellow', attrs=['bold'])
                elif pnl_pct > 1.0:  # In profit > 1%
                    status = colored('📈 PROFIT', 'green')
                elif pnl_pct < -1.0:  # In loss > 1%
                    status = colored('📉 LOSS', 'red')
                else:
                    status = colored('⚪ OPEN', 'white')
                
                # Color PnL based on profit/loss with enhanced formatting
                if pnl_pct > 0:
                    pnl_pct_colored = colored(f"+{pnl_pct:.2f}%", 'green', attrs=['bold'])
                    pnl_usd_colored = colored(f"+${pnl_usd:.2f}", 'green', attrs=['bold'])
                elif pnl_pct < -2.0:  # Significant loss
                    pnl_pct_colored = colored(f"{pnl_pct:.2f}%", 'red', attrs=['bold'])
                    pnl_usd_colored = colored(f"-${abs(pnl_usd):.2f}", 'red', attrs=['bold'])
                else:
                    pnl_pct_colored = colored(f"{pnl_pct:.2f}%", 'red')
                    pnl_usd_colored = colored(f"-${abs(pnl_usd):.2f}", 'red')
                
                # Format prices with proper precision
                entry_str = f"${entry:.6f}"
                current_str = f"${current:.6f}"
                sl_str = f"${sl:.6f}" if sl > 0 else "N/A"
                tp_str = f"${tp:.6f}" if tp > 0 else "N/A"
                
                row = f"{i:<2} {symbol_short:<10} {side:<4} {entry_str:<12} {current_str:<12} {sl_str:<12} {tp_str:<12} {pnl_pct_colored:<8} {pnl_usd_colored:<8} {status}"
                print(row)
                
                # Additional details row for each position
                if sl > 0 or tp > 0:
                    # Calculate distances to TP/SL
                    if side == 'BUY':
                        sl_dist = ((current - sl) / current) * 100 if sl > 0 else 0
                        tp_dist = ((tp - current) / current) * 100 if tp > 0 else 0
                    else:  # SELL
                        sl_dist = ((sl - current) / current) * 100 if sl > 0 else 0  
                        tp_dist = ((current - tp) / current) * 100 if tp > 0 else 0
                    
                    # Enhanced details row
                    details = f"   ├─ 🎯 Distance to TP: {colored(f'{tp_dist:+.2f}%', 'green') if tp > 0 else colored('N/A', 'gray')} | 🛡️ Distance to SL: {colored(f'{sl_dist:+.2f}%', 'red') if sl > 0 else colored('N/A', 'gray')}"
                    print(colored(details, 'cyan'))
                    
                    # Show max favorable move
                    max_favorable = position.get('max_favorable_pnl', 0)
                    confidence = position.get('confidence', 0) * 100
                    details2 = f"   └─ 📈 Max Profit Seen: {colored(f'{max_favorable:+.2f}%', 'green')} | 🎯 Signal Confidence: {colored(f'{confidence:.0f}%', 'cyan')}"
                    print(colored(details2, 'cyan'))
            
            print(colored("─" * 130, "yellow"))
            
            # Session totals
            unrealized_pnl_pct, unrealized_pnl_usd = global_position_tracker.get_total_unrealized_pnl()
            best_position = max(global_position_tracker.active_positions.values(), key=lambda x: x['unrealized_pnl_pct'], default={'unrealized_pnl_pct': 0})
            worst_position = min(global_position_tracker.active_positions.values(), key=lambda x: x['unrealized_pnl_pct'], default={'unrealized_pnl_pct': 0})
            
            pnl_color = 'green' if unrealized_pnl_usd >= 0 else 'red'
            pnl_sign = '+' if unrealized_pnl_usd >= 0 else ''
            
            best_pnl = best_position["unrealized_pnl_pct"]
            worst_pnl = worst_position["unrealized_pnl_pct"]
            print(f"{colored('📊 Session PnL:', 'cyan')} {colored(f'{pnl_sign}${unrealized_pnl_usd:.2f}', pnl_color)} | {colored('🏆 Best:', 'green')} {colored(f'+{best_pnl:.2f}%', 'green')} | {colored('📉 Worst:', 'red')} {colored(f'{worst_pnl:.2f}%', 'red')}")
            
        else:
            print(colored("📋 NO ACTIVE POSITIONS", "yellow", attrs=['bold']))
            print(colored("─" * 50, "yellow"))
            print(colored("💡 Waiting for new trading signals...", "cyan"))
        
        print(colored("═" * 80, "cyan"))
        print()  # Add spacing
        
    except Exception as e:
        logging.error(f"Error displaying wallet and positions: {e}")
