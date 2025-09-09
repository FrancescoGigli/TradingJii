#!/usr/bin/env python3
"""
🚀 SMART DISPLAY SYSTEM

DUAL TABLE DISPLAY:
- 🟢 OPEN Positions: Solo posizioni realmente su Bybit
- 🔴 CLOSED Positions: Posizioni chiuse nella sessione con P&L
- Smart sync con Bybit real-time
- Session performance tracking

GARANTISCE: Display accurato e separazione open/closed
"""

import logging
from datetime import datetime
from typing import List, Dict
from termcolor import colored
from core.smart_position_manager import SmartPositionManager, Position

async def display_smart_trading_status(smart_manager: SmartPositionManager, exchange, balance: float):
    """
    🚀 SMART DISPLAY: Due tabelle separate per posizioni OPEN e CLOSED
    
    Args:
        smart_manager: SmartPositionManager instance
        exchange: Bybit exchange for real-time sync
        balance: Current account balance
    """
    try:
        # 1. SYNC WITH BYBIT FIRST
        newly_opened, newly_closed = await smart_manager.sync_with_bybit(exchange)
        
        # 2. GET CURRENT DATA
        open_positions = smart_manager.get_active_positions()
        closed_positions = smart_manager.get_closed_positions()
        session_summary = smart_manager.get_session_summary()
        
        # 3. HEADER
        print(colored("💼 SMART TRADING STATUS", "cyan", attrs=['bold']))
        print(colored("═" * 120, "cyan"))
        
        # 4. BALANCE & SUMMARY
        total_pnl_pct, total_pnl_usd = smart_manager.get_session_pnl()
        realized_pnl = session_summary['realized_pnl']
        unrealized_pnl = session_summary['unrealized_pnl']
        
        print(f"{colored('💰 Balance:', 'white')} {colored(f'${balance:.2f}', 'yellow', attrs=['bold'])}")
        print(f"{colored('📊 Session P&L:', 'white')} {colored(f'{total_pnl_pct:+.2f}%', 'green' if total_pnl_usd >= 0 else 'red', attrs=['bold'])} {colored(f'({total_pnl_usd:+.2f} USD)', 'white')}")
        print(f"{colored('💵 Realized:', 'white')} {colored(f'${realized_pnl:+.2f}', 'green' if realized_pnl >= 0 else 'red')} | {colored('💎 Unrealized:', 'white')} {colored(f'${unrealized_pnl:+.2f}', 'green' if unrealized_pnl >= 0 else 'red')}")
        
        print(colored("═" * 120, "cyan"))
        
        # 5. 🟢 OPEN POSITIONS TABLE (Solo quelle reali su Bybit)
        print(colored("🟢 ACTIVE POSITIONS ON BYBIT", "green", attrs=['bold']))
        print(colored("─" * 120, "green"))
        
        if open_positions:
            # Header
            header = f"{'#':<2} {'SYMBOL':<10} {'SIDE':<4} {'ENTRY':<12} {'CURRENT':<12} {'STOP LOSS':<12} {'TAKE PROFIT':<12} {'PnL%':<8} {'PnL$':<10} {'STATUS':<12}"
            print(colored(header, "white", attrs=['bold']))
            print(colored("─" * 120, "white"))
            
            # Open positions rows  
            for i, position in enumerate(open_positions, 1):
                symbol_short = position.symbol.replace('/USDT:USDT', '')[:10]
                side = position.side.upper()[:4]
                
                # Format prices
                entry_str = f"${position.entry_price:.6f}"
                current_str = f"${position.current_price:.6f}"
                sl_str = f"${position.stop_loss:.6f}" if position.stop_loss > 0 else "N/A"
                tp_str = f"${position.take_profit:.6f}" if position.take_profit > 0 else "N/A"
                
                # PnL formatting
                pnl_pct = position.unrealized_pnl_pct
                pnl_usd = position.unrealized_pnl_usd
                
                if pnl_pct > 0:
                    pnl_pct_colored = colored(f"+{pnl_pct:.2f}%", 'green', attrs=['bold'])
                    pnl_usd_colored = colored(f"+${pnl_usd:.2f}", 'green', attrs=['bold'])
                else:
                    pnl_pct_colored = colored(f"{pnl_pct:.2f}%", 'red', attrs=['bold']) 
                    pnl_usd_colored = colored(f"${pnl_usd:.2f}", 'red', attrs=['bold'])
                
                # Status with trailing info
                if position.trailing_active:
                    status = colored('🎪 TRAIL', 'yellow', attrs=['bold'])
                elif pnl_pct > 2.0:
                    status = colored('🚀 PROFIT', 'green')
                elif pnl_pct < -2.0:
                    status = colored('⚠️ LOSS', 'red')
                else:
                    status = colored('⚪ OPEN', 'white')
                
                # Position row
                row = f"{i:<2} {symbol_short:<10} {side:<4} {entry_str:<12} {current_str:<12} {sl_str:<12} {tp_str:<12} {pnl_pct_colored:<8} {pnl_usd_colored:<10} {status}"
                print(row)
                
                # Additional details (TP/SL distances, order IDs)
                if position.stop_loss > 0 or position.take_profit > 0:
                    # Calculate distances
                    if position.side == 'buy':
                        sl_dist = ((position.current_price - position.stop_loss) / position.current_price) * 100 if position.stop_loss > 0 else 0
                        tp_dist = ((position.take_profit - position.current_price) / position.current_price) * 100 if position.take_profit > 0 else 0
                    else:
                        sl_dist = ((position.stop_loss - position.current_price) / position.current_price) * 100 if position.stop_loss > 0 else 0
                        tp_dist = ((position.current_price - position.take_profit) / position.current_price) * 100 if position.take_profit > 0 else 0
                    
                    # Order IDs display
                    sl_id_display = position.sl_order_id[-8:] if position.sl_order_id else "N/A"
                    tp_id_display = position.tp_order_id[-8:] if position.tp_order_id else "N/A"
                    
                    details = f"   ├─ 🎯 TP Distance: {colored(f'{tp_dist:+.2f}%', 'green') if tp_dist > 0 else colored('N/A', 'gray')} | 🛡️ SL Distance: {colored(f'{sl_dist:+.2f}%', 'red') if sl_dist > 0 else colored('N/A', 'gray')}"
                    print(colored(details, 'cyan'))
                    
                    order_details = f"   └─ 📋 Orders: SL ID:{sl_id_display} | TP ID:{tp_id_display} | 🎯 Confidence: {colored(f'{position.confidence*100:.0f}%', 'cyan')}"
                    print(colored(order_details, 'cyan'))
            
            print(colored("─" * 120, "green"))
        else:
            print(colored("   📭 NO ACTIVE POSITIONS ON BYBIT", "yellow"))
            print(colored("   💡 Waiting for new trading signals...", "cyan"))
            print(colored("─" * 120, "green"))
        
        print()  # Spacing between tables
        
        # 6. 🔴 CLOSED POSITIONS TABLE (Con P&L della sessione)
        print(colored("🔴 CLOSED POSITIONS (SESSION HISTORY)", "red", attrs=['bold']))
        print(colored("─" * 120, "red"))
        
        if closed_positions:
            # Header for closed positions
            header = f"{'#':<2} {'SYMBOL':<10} {'SIDE':<4} {'ENTRY':<12} {'EXIT':<12} {'DURATION':<12} {'REASON':<8} {'PnL%':<8} {'PnL$':<10} {'RESULT':<12}"
            print(colored(header, "white", attrs=['bold']))
            print(colored("─" * 120, "white"))
            
            # Closed positions rows
            total_realized_pnl = 0
            wins = 0
            losses = 0
            
            for i, position in enumerate(closed_positions, 1):
                symbol_short = position.symbol.replace('/USDT:USDT', '')[:10]
                side = position.side.upper()[:4]
                
                # Format prices and times
                entry_str = f"${position.entry_price:.6f}"
                exit_str = f"${position.current_price:.6f}"
                
                # Calculate duration
                try:
                    entry_time = datetime.fromisoformat(position.entry_time)
                    close_time = datetime.fromisoformat(position.close_time) if position.close_time else datetime.now()
                    duration = close_time - entry_time
                    duration_str = f"{duration.seconds//3600:02d}h{(duration.seconds%3600)//60:02d}m"
                except:
                    duration_str = "N/A"
                
                reason = position.close_reason or "UNKNOWN"
                reason_short = reason.replace("CLOSED_", "")[:8]
                
                # P&L formatting
                pnl_pct = position.final_pnl_pct or 0
                pnl_usd = position.final_pnl_usd or 0
                
                total_realized_pnl += pnl_usd
                
                if pnl_pct > 0:
                    pnl_pct_colored = colored(f"+{pnl_pct:.2f}%", 'green', attrs=['bold'])
                    pnl_usd_colored = colored(f"+${pnl_usd:.2f}", 'green', attrs=['bold'])
                    result = colored('💰 WIN', 'green', attrs=['bold'])
                    wins += 1
                else:
                    pnl_pct_colored = colored(f"{pnl_pct:.2f}%", 'red', attrs=['bold'])
                    pnl_usd_colored = colored(f"${pnl_usd:.2f}", 'red', attrs=['bold'])
                    result = colored('📉 LOSS', 'red', attrs=['bold'])
                    losses += 1
                
                # Closed position row
                row = f"{i:<2} {symbol_short:<10} {side:<4} {entry_str:<12} {exit_str:<12} {duration_str:<12} {reason_short:<8} {pnl_pct_colored:<8} {pnl_usd_colored:<10} {result}"
                print(row)
            
            print(colored("─" * 120, "red"))
            
            # Session statistics
            total_trades = wins + losses
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            avg_pnl = total_realized_pnl / total_trades if total_trades > 0 else 0
            
            print(f"{colored('📊 Session Stats:', 'white')} {colored(f'{total_trades} trades', 'white')} | {colored(f'Win Rate: {win_rate:.1f}%', 'green' if win_rate >= 50 else 'red')} | {colored(f'Avg P&L: ${avg_pnl:+.2f}', 'green' if avg_pnl >= 0 else 'red')}")
            
        else:
            print(colored("   📭 NO CLOSED POSITIONS THIS SESSION", "yellow"))
            print(colored("   💡 Start trading to see session history here...", "cyan"))
            print(colored("─" * 120, "red"))
        
        print(colored("═" * 120, "cyan"))
        
        # 7. SYNC NOTIFICATIONS
        if newly_opened:
            print(colored(f"📥 SYNC ALERT: {len(newly_opened)} new positions detected on Bybit", "green", attrs=['bold']))
            for pos in newly_opened:
                symbol_short = pos.symbol.replace('/USDT:USDT', '')
                print(f"   ✅ {symbol_short} {pos.side.upper()} @ ${pos.entry_price:.6f}")
        
        if newly_closed:
            print(colored(f"🔒 SYNC ALERT: {len(newly_closed)} positions closed on Bybit", "yellow", attrs=['bold']))
            for pos in newly_closed:
                symbol_short = pos.symbol.replace('/USDT:USDT', '')
                pnl_color = 'green' if pos.final_pnl_pct >= 0 else 'red'
                print(f"   🔒 {symbol_short} {pos.side.upper()} → {colored(f'{pos.final_pnl_pct:+.2f}%', pnl_color)} ({pos.close_reason})")
        
        if newly_opened or newly_closed:
            print(colored("═" * 120, "cyan"))
        
        print()  # Final spacing
        
    except Exception as e:
        logging.error(f"Error in smart trading status display: {e}")
        print(colored(f"❌ Smart Display Error: {str(e)}", "red"))

async def display_bybit_sync_summary(smart_manager: SmartPositionManager, exchange):
    """
    Quick sync summary for debugging
    """
    try:
        print(colored("🔄 BYBIT SYNC SUMMARY", "cyan", attrs=['bold']))
        print(colored("─" * 60, "cyan"))
        
        # Get real Bybit positions
        bybit_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
        active_bybit = [p for p in bybit_positions if float(p.get('contracts', 0)) > 0]
        
        # Get tracked positions
        tracked_open = smart_manager.get_active_positions()
        tracked_closed = smart_manager.get_closed_positions()
        
        print(f"{colored('📊 Bybit Real:', 'white')} {colored(str(len(active_bybit)), 'yellow')} positions")
        print(f"{colored('📊 Tracked Open:', 'white')} {colored(str(len(tracked_open)), 'green')} positions") 
        print(f"{colored('📊 Tracked Closed:', 'white')} {colored(str(len(tracked_closed)), 'red')} positions")
        
        # Show symbols
        bybit_symbols = [p.get('symbol', '').replace('/USDT:USDT', '') for p in active_bybit]
        tracked_symbols = [p.symbol.replace('/USDT:USDT', '') for p in tracked_open]
        
        print(f"{colored('🎯 Bybit Symbols:', 'white')} {colored(', '.join(bybit_symbols), 'yellow')}")
        print(f"{colored('🎯 Tracked Symbols:', 'white')} {colored(', '.join(tracked_symbols), 'green')}")
        
        # Sync status
        symbols_match = set(bybit_symbols) == set(tracked_symbols)
        sync_status = colored('✅ IN SYNC', 'green') if symbols_match else colored('⚠️ DESYNC', 'yellow')
        print(f"{colored('🔄 Sync Status:', 'white')} {sync_status}")
        
        print(colored("─" * 60, "cyan"))
        print()
        
    except Exception as e:
        logging.error(f"Error in sync summary: {e}")

def display_position_performance_metrics(closed_positions: List[Position]):
    """
    Display detailed performance metrics for closed positions
    """
    try:
        if not closed_positions:
            return
        
        print(colored("📈 SESSION PERFORMANCE METRICS", "cyan", attrs=['bold']))
        print(colored("─" * 80, "cyan"))
        
        # Calculate metrics
        total_trades = len(closed_positions)
        wins = len([p for p in closed_positions if (p.final_pnl_pct or 0) > 0])
        losses = total_trades - wins
        
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        
        # P&L metrics
        profitable_trades = [p for p in closed_positions if (p.final_pnl_pct or 0) > 0]
        losing_trades = [p for p in closed_positions if (p.final_pnl_pct or 0) <= 0]
        
        avg_win = sum(p.final_pnl_pct or 0 for p in profitable_trades) / len(profitable_trades) if profitable_trades else 0
        avg_loss = sum(p.final_pnl_pct or 0 for p in losing_trades) / len(losing_trades) if losing_trades else 0
        
        # Best and worst trades
        best_trade = max(closed_positions, key=lambda p: p.final_pnl_pct or 0)
        worst_trade = min(closed_positions, key=lambda p: p.final_pnl_pct or 0)
        
        # Display metrics
        print(f"{colored('📊 Total Trades:', 'white')} {colored(str(total_trades), 'cyan')}")
        print(f"{colored('🏆 Wins:', 'white')} {colored(str(wins), 'green')} | {colored('📉 Losses:', 'white')} {colored(str(losses), 'red')} | {colored('🎯 Win Rate:', 'white')} {colored(f'{win_rate:.1f}%', 'green' if win_rate >= 50 else 'red')}")
        
        if profitable_trades:
            print(f"{colored('💰 Avg Win:', 'white')} {colored(f'{avg_win:+.2f}%', 'green')}")
        if losing_trades:
            print(f"{colored('📉 Avg Loss:', 'white')} {colored(f'{avg_loss:+.2f}%', 'red')}")
        
        if avg_win != 0 and avg_loss != 0:
            risk_reward = abs(avg_win / avg_loss)
            print(f"{colored('⚖️ Risk:Reward:', 'white')} {colored(f'1:{risk_reward:.1f}', 'green' if risk_reward > 1.5 else 'yellow')}")
        
        # Best/worst trades
        best_symbol = best_trade.symbol.replace('/USDT:USDT', '')
        worst_symbol = worst_trade.symbol.replace('/USDT:USDT', '')
        print(f"{colored('🏆 Best Trade:', 'white')} {colored(f'{best_symbol} {best_trade.final_pnl_pct:+.2f}%', 'green')}")
        print(f"{colored('📉 Worst Trade:', 'white')} {colored(f'{worst_symbol} {worst_trade.final_pnl_pct:+.2f}%', 'red')}")
        
        print(colored("─" * 80, "cyan"))
        print()
        
    except Exception as e:
        logging.error(f"Error displaying performance metrics: {e}")

# Global instance
smart_display_manager = None

def init_smart_display():
    """Initialize smart display system"""
    global smart_display_manager
    smart_display_manager = SmartPositionManager()
    logging.info("🚀 Smart display system initialized")
