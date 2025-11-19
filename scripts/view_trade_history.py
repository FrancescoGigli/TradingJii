#!/usr/bin/env python3
"""
📊 TRADE HISTORY VIEWER

Script per visualizzare e analizzare la storia dei trade dal file JSON.
Uso: python scripts/view_trade_history.py
"""

import json
import os
from datetime import datetime
from typing import Dict, List
from termcolor import colored


def load_trade_history(json_file: str = "data_cache/trade_history.json") -> Dict:
    """Carica il file JSON con la storia dei trade"""
    if not os.path.exists(json_file):
        print(colored(f"❌ File non trovato: {json_file}", "red"))
        print(colored("💡 Il file verrà creato automaticamente quando il bot inizia a tradare", "yellow"))
        return {'trades': [], 'metadata': {}}
    
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_timestamp(iso_string: str) -> str:
    """Formatta timestamp ISO in formato leggibile"""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y %H:%M:%S')
    except:
        return iso_string


def display_metadata(metadata: Dict):
    """Mostra metadata del file"""
    print(colored("=" * 80, "cyan"))
    print(colored("📊 TRADE HISTORY METADATA", "cyan", attrs=['bold']))
    print(colored("=" * 80, "cyan"))
    
    if metadata:
        print(f"📅 Created: {format_timestamp(metadata.get('created', 'N/A'))}")
        print(f"🔄 Last Updated: {format_timestamp(metadata.get('last_updated', 'N/A'))}")
        print(f"📈 Total Trades: {metadata.get('total_trades', 0)}")
        print(f"🟢 Open Trades: {metadata.get('open_trades', 0)}")
        print(f"🔴 Closed Trades: {metadata.get('closed_trades', 0)}")
        print(f"🏷️  Version: {metadata.get('version', 'N/A')}")
    else:
        print(colored("⚠️ No metadata available", "yellow"))
    
    print(colored("=" * 80, "cyan"))
    print()


def display_trade_summary(trades: List[Dict]):
    """Mostra sommario dei trade"""
    if not trades:
        print(colored("📭 No trades recorded yet", "yellow"))
        return
    
    open_trades = [t for t in trades if t['status'] == 'OPEN']
    closed_trades = [t for t in trades if t['status'] == 'CLOSED']
    
    print(colored("=" * 80, "green"))
    print(colored("📊 TRADE SUMMARY", "green", attrs=['bold']))
    print(colored("=" * 80, "green"))
    
    # Open trades
    if open_trades:
        print(colored(f"\n🟢 OPEN POSITIONS ({len(open_trades)}):", "green", attrs=['bold']))
        print(colored("-" * 80, "green"))
        
        for trade in open_trades:
            symbol_short = trade['symbol_short']
            side = trade['side']
            entry = trade['entry_price']
            margin = trade['initial_margin']
            lev = trade['leverage']
            sl = trade.get('stop_loss', 'N/A')
            
            side_emoji = "🟢" if side == 'BUY' else "🔴"
            
            print(f"{side_emoji} {symbol_short:12} | {side:4} | Entry: ${entry:10.6f} | "
                  f"Margin: ${margin:7.2f} | Lev: {lev}x | SL: ${sl if isinstance(sl, str) else f'{sl:.6f}'}")
    else:
        print(colored("\n🟢 No open positions", "yellow"))
    
    # Closed trades
    if closed_trades:
        print(colored(f"\n🔴 CLOSED POSITIONS ({len(closed_trades)}):", "red", attrs=['bold']))
        print(colored("-" * 80, "red"))
        
        total_pnl = 0
        wins = 0
        losses = 0
        total_fees = 0
        
        for trade in closed_trades:
            symbol_short = trade['symbol_short']
            side = trade['side']
            entry = trade['entry_price']
            exit_price = trade.get('exit_price', 0)
            pnl_usd = trade.get('realized_pnl_usd', 0)
            pnl_pct = trade.get('realized_pnl_pct', 0)
            duration = trade.get('duration_minutes', 0)
            reason = trade.get('close_reason', 'N/A')
            total_fee = trade.get('total_fee', 0)
            
            if pnl_usd:
                total_pnl += pnl_usd
                if pnl_usd > 0:
                    wins += 1
                else:
                    losses += 1
            
            if total_fee:
                total_fees += total_fee
            
            side_emoji = "🟢" if side == 'BUY' else "🔴"
            pnl_color = "green" if pnl_usd >= 0 else "red"
            pnl_sign = "+" if pnl_usd >= 0 else ""
            
            print(f"{side_emoji} {symbol_short:12} | {side:4} | "
                  f"Entry: ${entry:10.6f} → Exit: ${exit_price:10.6f} | "
                  f"PnL: {colored(f'{pnl_sign}{pnl_pct:+6.2f}% (${pnl_sign}{pnl_usd:.2f})', pnl_color)} | "
                  f"{duration:.0f}min | {reason}")
        
        # Statistics
        print(colored("-" * 80, "white"))
        print(colored("STATISTICS:", "white", attrs=['bold']))
        
        win_rate = (wins / len(closed_trades) * 100) if closed_trades else 0
        avg_pnl = total_pnl / len(closed_trades) if closed_trades else 0
        
        pnl_color = "green" if total_pnl >= 0 else "red"
        pnl_sign = "+" if total_pnl >= 0 else ""
        
        print(f"💰 Total PnL: {colored(f'{pnl_sign}${total_pnl:.2f}', pnl_color)}")
        print(f"📊 Win Rate: {win_rate:.1f}% ({wins} wins, {losses} losses)")
        print(f"📈 Avg PnL per trade: {pnl_sign}${avg_pnl:.2f}")
        print(f"💸 Total Fees: ${total_fees:.2f}")
    else:
        print(colored("\n🔴 No closed positions", "yellow"))
    
    print(colored("=" * 80, "green"))
    print()


def display_recent_trades(trades: List[Dict], limit: int = 5):
    """Mostra gli ultimi N trade"""
    if not trades:
        return
    
    print(colored("=" * 80, "yellow"))
    print(colored(f"📅 LAST {min(limit, len(trades))} TRADES (Most Recent First)", "yellow", attrs=['bold']))
    print(colored("=" * 80, "yellow"))
    
    # Sort by logged_at descending
    sorted_trades = sorted(trades, key=lambda t: t.get('logged_at', ''), reverse=True)
    
    for i, trade in enumerate(sorted_trades[:limit], 1):
        symbol_short = trade['symbol_short']
        status = trade['status']
        side = trade['side']
        entry = trade['entry_price']
        open_time = format_timestamp(trade.get('open_time', ''))
        
        status_emoji = "🟢" if status == 'OPEN' else "🔴"
        side_emoji = "🟢" if side == 'BUY' else "🔴"
        
        print(f"\n{i}. {status_emoji} {symbol_short} ({status})")
        print(f"   {side_emoji} {side} @ ${entry:.6f}")
        print(f"   📅 Opened: {open_time}")
        
        if status == 'CLOSED':
            exit_price = trade.get('exit_price', 0)
            pnl_usd = trade.get('realized_pnl_usd', 0)
            pnl_pct = trade.get('realized_pnl_pct', 0)
            close_time = format_timestamp(trade.get('close_time', ''))
            reason = trade.get('close_reason', 'N/A')
            
            pnl_color = "green" if pnl_usd >= 0 else "red"
            pnl_sign = "+" if pnl_usd >= 0 else ""
            
            print(f"   🏁 Exit: ${exit_price:.6f}")
            print(f"   💰 PnL: {colored(f'{pnl_sign}{pnl_pct:.2f}% (${pnl_sign}{pnl_usd:.2f})', pnl_color)}")
            print(f"   📅 Closed: {close_time}")
            print(f"   ❓ Reason: {reason}")
    
    print(colored("=" * 80, "yellow"))
    print()


def main():
    """Main function"""
    print()
    print(colored("╔════════════════════════════════════════════════════════════════════════════╗", "cyan", attrs=['bold']))
    print(colored("║                         📊 TRADE HISTORY VIEWER                            ║", "cyan", attrs=['bold']))
    print(colored("╚════════════════════════════════════════════════════════════════════════════╝", "cyan", attrs=['bold']))
    print()
    
    # Load data
    data = load_trade_history()
    
    if not data or not data.get('trades'):
        print(colored("📭 No trade history available yet", "yellow"))
        print(colored("💡 Start the bot to begin recording trades", "cyan"))
        return
    
    # Display sections
    display_metadata(data.get('metadata', {}))
    display_trade_summary(data['trades'])
    display_recent_trades(data['trades'], limit=10)
    
    # Export option
    print(colored("💡 TIP: You can analyze this data programmatically:", "cyan"))
    print(colored("   import json", "white"))
    print(colored("   with open('data_cache/trade_history.json') as f:", "white"))
    print(colored("       data = json.load(f)", "white"))
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(colored(f"\n❌ Error: {e}", "red"))
        import traceback
        traceback.print_exc()
