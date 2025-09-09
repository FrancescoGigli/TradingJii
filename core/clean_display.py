#!/usr/bin/env python3
"""
📊 CLEAN DISPLAY SYSTEM

SINGLE RESPONSIBILITY: Position & trading status display
- Show active positions with TP/SL details
- Display session summary
- Trading performance metrics
- Clean, readable format

GARANTISCE: Display accurato usando i nuovi moduli puliti
"""

from termcolor import colored
from typing import List, Dict
import logging

def display_trading_status(position_manager, order_manager, balance: float):
    """
    Display comprehensive trading status using clean modules
    
    Args:
        position_manager: PositionManager instance
        order_manager: OrderManager instance  
        balance: Current account balance
    """
    try:
        # Get data from clean modules
        positions = position_manager.get_active_positions()
        session_summary = position_manager.get_session_summary()
        order_summary = order_manager.get_placed_orders_summary()
        
        print(colored("💼 CLEAN TRADING STATUS", "cyan", attrs=['bold']))
        print(colored("═" * 100, "cyan"))
        
        # Wallet summary
        used_margin = session_summary['used_margin']
        available = session_summary['available_balance']
        total_pnl_usd = session_summary['total_pnl_usd']
        
        print(f"{colored('💰 Balance:', 'white')} {colored(f'${balance:.2f}', 'yellow', attrs=['bold'])}")
        print(f"{colored('📊 Used Margin:', 'white')} {colored(f'${used_margin:.2f}', 'white')} | {colored('📈 Available:', 'white')} {colored(f'${available:.2f}', 'green')}")
        orders_text = f"SL:{order_summary['stop_losses']} TP:{order_summary['take_profits']}"
        print(f"{colored('🎯 Active Positions:', 'white')} {colored(str(len(positions)), 'cyan')} | {colored('📋 Orders Placed:', 'white')} {colored(orders_text, 'white')}")
        
        # PnL status
        if total_pnl_usd >= 0:
            pnl_color = 'green'
            pnl_sign = '+'
        else:
            pnl_color = 'red' 
            pnl_sign = ''
        
        print(f"{colored('💵 Session PnL:', 'white')} {colored(f'{pnl_sign}${total_pnl_usd:.2f}', pnl_color, attrs=['bold'])}")
        
        print(colored("═" * 100, "cyan"))
        
        # Active positions table
        if positions:
            print(colored("📋 ACTIVE POSITIONS (Clean Module Data)", "yellow", attrs=['bold']))
            print(colored("─" * 130, "yellow"))
            
            # Header
            header = f"{'#':<2} {'SYMBOL':<10} {'SIDE':<4} {'ENTRY':<12} {'CURRENT':<12} {'STOP LOSS':<12} {'TAKE PROFIT':<12} {'PnL%':<8} {'PnL$':<8} {'STATUS':<10}"
            print(colored(header, "white", attrs=['bold']))
            print(colored("─" * 130, "white"))
            
            # Position rows
            for i, position in enumerate(positions, 1):
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
                    pnl_usd_colored = colored(f"-${abs(pnl_usd):.2f}", 'red', attrs=['bold'])
                
                # Status
                if position.trailing_active:
                    status = colored('🎪 TRAIL', 'yellow')
                elif pnl_pct > 1.0:
                    status = colored('📈 PROFIT', 'green')
                elif pnl_pct < -2.0:
                    status = colored('📉 LOSS', 'red')
                else:
                    status = colored('⚪ OPEN', 'white')
                
                # Print position row
                row = f"{i:<2} {symbol_short:<10} {side:<4} {entry_str:<12} {current_str:<12} {sl_str:<12} {tp_str:<12} {pnl_pct_colored:<8} {pnl_usd_colored:<8} {status}"
                print(row)
                
                # Additional details
                if position.stop_loss > 0 or position.take_profit > 0:
                    # Calculate distances
                    if position.side == 'buy':
                        sl_dist = ((position.current_price - position.stop_loss) / position.current_price) * 100 if position.stop_loss > 0 else 0
                        tp_dist = ((position.take_profit - position.current_price) / position.current_price) * 100 if position.take_profit > 0 else 0
                    else:
                        sl_dist = ((position.stop_loss - position.current_price) / position.current_price) * 100 if position.stop_loss > 0 else 0
                        tp_dist = ((position.current_price - position.take_profit) / position.current_price) * 100 if position.take_profit > 0 else 0
                    
                    # Order IDs
                    sl_id_display = position.sl_order_id[-8:] if position.sl_order_id else "N/A"
                    tp_id_display = position.tp_order_id[-8:] if position.tp_order_id else "N/A"
                    
                    details = f"   ├─ 🎯 TP Distance: {colored(f'{tp_dist:+.2f}%', 'green') if position.take_profit > 0 else colored('N/A', 'gray')} | 🛡️ SL Distance: {colored(f'{sl_dist:+.2f}%', 'red') if position.stop_loss > 0 else colored('N/A', 'gray')}"
                    print(colored(details, 'cyan'))
                    
                    order_details = f"   └─ 📋 Orders: SL ID:{sl_id_display} | TP ID:{tp_id_display} | 🎯 Confidence: {colored(f'{position.confidence*100:.0f}%', 'cyan')}"
                    print(colored(order_details, 'cyan'))
            
            print(colored("─" * 130, "yellow"))
            
            # Summary for multiple positions
            if len(positions) > 1:
                best_pos = max(positions, key=lambda x: x.unrealized_pnl_pct)
                worst_pos = min(positions, key=lambda x: x.unrealized_pnl_pct)
                
                print(f"{colored('📊 Portfolio:', 'cyan')} {colored(f'Total PnL: {pnl_sign}${total_pnl_usd:.2f}', pnl_color)} | {colored('🏆 Best:', 'green')} {colored(f'{best_pos.unrealized_pnl_pct:+.2f}%', 'green')} | {colored('📉 Worst:', 'red')} {colored(f'{worst_pos.unrealized_pnl_pct:+.2f}%', 'red')}")
        
        else:
            print(colored("📋 NO ACTIVE POSITIONS", "yellow", attrs=['bold']))
            print(colored("─" * 50, "yellow"))
            print(colored("💡 Waiting for trading signals...", "cyan"))
        
        print(colored("═" * 100, "cyan"))
        print()  # Spacing
        
    except Exception as e:
        logging.error(f"Error displaying trading status: {e}")
        print(colored(f"❌ Display Error: {str(e)}", "red"))

def display_protection_summary(protection_results: Dict):
    """
    Display summary of position protection results
    
    Args:
        protection_results: Dict from TradingOrchestrator.protect_existing_positions
    """
    try:
        if not protection_results:
            return
        
        print(colored("🛡️ POSITION PROTECTION SUMMARY", "yellow", attrs=['bold']))
        print(colored("─" * 80, "yellow"))
        
        for symbol, result in protection_results.items():
            symbol_short = symbol.replace('/USDT:USDT', '')
            
            if result.success:
                sl_id = result.order_ids.get('stop_loss', 'N/A')
                tp_id = result.order_ids.get('take_profit', 'N/A')
                print(f"✅ {symbol_short:<15} | SL: {sl_id[-8:] if sl_id != 'N/A' else 'N/A'} | TP: {tp_id[-8:] if tp_id != 'N/A' else 'N/A'}")
            else:
                print(f"❌ {symbol_short:<15} | Error: {result.error[:40]}...")
        
        successful = sum(1 for r in protection_results.values() if r.success)
        total = len(protection_results)
        success_rate = (successful / total) * 100 if total > 0 else 0
        
        print(colored("─" * 80, "yellow"))
        print(f"{colored('📊 Protection Rate:', 'cyan')} {colored(f'{successful}/{total} ({success_rate:.0f}%)', 'green' if success_rate > 80 else 'yellow')}")
        print(colored("─" * 80, "yellow"))
        print()
        
    except Exception as e:
        logging.error(f"Error displaying protection summary: {e}")

def display_order_execution_result(symbol: str, result):
    """
    Display clean order execution result
    
    Args:
        symbol: Trading symbol
        result: TradingResult from TradingOrchestrator
    """
    try:
        symbol_short = symbol.replace('/USDT:USDT', '')
        
        if result.success:
            print(colored(f"✅ TRADE SUCCESS: {symbol_short}", "green", attrs=['bold']))
            print(colored(f"   📊 Position ID: {result.position_id}", "white"))
            
            if result.order_ids:
                main_id = result.order_ids.get('main', 'N/A')
                sl_id = result.order_ids.get('stop_loss', 'N/A')
                tp_id = result.order_ids.get('take_profit', 'N/A')
                
                print(colored(f"   📋 Orders: Main:{main_id[-8:]} | SL:{sl_id[-8:] if sl_id != 'N/A' else 'N/A'} | TP:{tp_id[-8:] if tp_id != 'N/A' else 'N/A'}", "cyan"))
        else:
            print(colored(f"❌ TRADE FAILED: {symbol_short}", "red", attrs=['bold']))
            print(colored(f"   💥 Error: {result.error}", "red"))
        
        print()  # Spacing
        
    except Exception as e:
        logging.error(f"Error displaying execution result: {e}")
