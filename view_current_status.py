#!/usr/bin/env python3
"""
Script per visualizzare stato corrente delle posizioni e analisi
"""

import json
from datetime import datetime
from termcolor import colored

def view_current_status():
    """Visualizza stato corrente del bot"""
    
    print("\n" + "="*80)
    print(colored("📊 STATO CORRENTE TRADING BOT", "cyan", attrs=['bold']))
    print("="*80)
    
    # Leggi file positions
    try:
        with open('thread_safe_positions.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(colored("\n❌ File thread_safe_positions.json non trovato", "red"))
        print("Avvia il bot per generare i dati.")
        return
    
    # Session info
    balance = data.get('session_balance', 0)
    start_balance = data.get('session_start_balance', 0)
    pnl = balance - start_balance
    pnl_pct = (pnl / start_balance * 100) if start_balance > 0 else 0
    
    print(f"\n💰 SESSION SUMMARY")
    print(f"Starting Balance: ${start_balance:.2f}")
    print(f"Current Balance:  ${balance:.2f}")
    print(f"Session PnL:      ${pnl:+.2f} ({pnl_pct:+.2f}%)")
    
    # Open positions
    open_positions = data.get('open_positions', {})
    print(f"\n📊 OPEN POSITIONS ({len(open_positions)})")
    print("-" * 80)
    
    if not open_positions:
        print("  No open positions")
    else:
        total_unrealized = 0
        for pos_id, pos in open_positions.items():
            symbol = pos['symbol'].replace('/USDT:USDT', '')
            side = "🟢 LONG" if pos['side'] == 'buy' else "🔴 SHORT"
            entry = pos['entry_price']
            current = pos['current_price']
            pnl_pct = pos['unrealized_pnl_pct']
            pnl_usd = pos['unrealized_pnl_usd']
            total_unrealized += pnl_usd
            
            # Color based on PnL
            if pnl_pct >= 0:
                pnl_color = 'green'
                pnl_symbol = '✅'
            else:
                pnl_color = 'red'
                pnl_symbol = '❌'
            
            print(f"\n  {symbol} {side}")
            print(f"    Entry:   ${entry:.6f}")
            print(f"    Current: ${current:.6f}")
            print(colored(f"    PnL:     {pnl_symbol} {pnl_pct:+.2f}% (${pnl_usd:+.2f})", pnl_color))
            print(f"    SL:      ${pos['stop_loss']:.6f}")
            
            # Entry time
            entry_time = datetime.fromisoformat(pos['entry_time'])
            duration = datetime.now() - entry_time
            hours = duration.total_seconds() / 3600
            print(f"    Duration: {hours:.1f}h")
    
    if len(open_positions) > 0:
        print(f"\n  {'─'*76}")
        print(colored(f"  Total Unrealized PnL: ${total_unrealized:+.2f}", 
                     'green' if total_unrealized >= 0 else 'red', attrs=['bold']))
    
    # Closed positions
    closed_positions = data.get('closed_positions', {})
    print(f"\n📁 CLOSED POSITIONS ({len(closed_positions)})")
    print("-" * 80)
    
    if not closed_positions:
        print("  No closed positions in this session")
    else:
        total_realized = 0
        winners = 0
        losers = 0
        
        for pos_id, pos in closed_positions.items():
            symbol = pos['symbol'].replace('/USDT:USDT', '')
            side = "🟢 LONG" if pos['side'] == 'buy' else "🔴 SHORT"
            pnl_pct = pos['unrealized_pnl_pct']
            pnl_usd = pos['unrealized_pnl_usd']
            total_realized += pnl_usd
            
            if pnl_pct >= 0:
                winners += 1
                pnl_color = 'green'
                pnl_symbol = '✅'
            else:
                losers += 1
                pnl_color = 'red'
                pnl_symbol = '❌'
            
            status = pos.get('status', 'CLOSED')
            close_reason = status.replace('CLOSED_', '')
            
            print(f"\n  {symbol} {side} - {close_reason}")
            print(colored(f"    Final PnL: {pnl_symbol} {pnl_pct:+.2f}% (${pnl_usd:+.2f})", pnl_color))
            
            # Duration
            if pos['entry_time'] and pos['close_time']:
                entry = datetime.fromisoformat(pos['entry_time'])
                close = datetime.fromisoformat(pos['close_time'])
                duration = close - entry
                hours = duration.total_seconds() / 3600
                print(f"    Duration: {hours:.1f}h")
        
        print(f"\n  {'─'*76}")
        print(f"  Winners: {winners} | Losers: {losers}")
        if winners + losers > 0:
            win_rate = (winners / (winners + losers)) * 100
            print(f"  Win Rate: {win_rate:.1f}%")
        print(colored(f"  Total Realized PnL: ${total_realized:+.2f}", 
                     'green' if total_realized >= 0 else 'red', attrs=['bold']))
    
    # Post-mortem info
    print(f"\n📝 POST-MORTEM STATUS")
    print("-" * 80)
    
    import os
    from pathlib import Path
    
    pm_dir = Path('trade_postmortem')
    pm_count = len(list(pm_dir.glob('*.json'))) if pm_dir.exists() else 0
    
    dec_dir = Path('trade_decisions')
    dec_count = len(list(dec_dir.glob('*.json'))) if dec_dir.exists() else 0
    
    print(f"  Post-mortem reports: {pm_count}")
    print(f"  Decision files:      {dec_count}")
    
    if pm_count == 0:
        print(colored("\n  ℹ️  No post-mortems yet (only created for losing trades)", "yellow"))
    
    if dec_count == 0:
        print(colored("  ℹ️  No decision files yet (created when opening new positions)", "yellow"))
    
    # Predictions for current positions
    if len(open_positions) > 0:
        print(f"\n🔮 POSITION OUTLOOK")
        print("-" * 80)
        for pos_id, pos in open_positions.items():
            symbol = pos['symbol'].replace('/USDT:USDT', '')
            pnl_pct = pos['unrealized_pnl_pct']
            
            if pnl_pct < -5:
                print(colored(f"  ⚠️  {symbol}: Heavy loss ({pnl_pct:.1f}%) - Consider manual close or wait for SL", "red"))
            elif pnl_pct < 0:
                print(colored(f"  ⚠️  {symbol}: In loss ({pnl_pct:.1f}%) - Monitor closely", "yellow"))
            elif pnl_pct > 5:
                print(colored(f"  ✅ {symbol}: Good profit ({pnl_pct:.1f}%) - Consider taking profit", "green"))
            else:
                print(f"  ℹ️  {symbol}: Small profit ({pnl_pct:.1f}%) - Hold position")
    
    print("\n" + "="*80)
    print(colored("📖 For detailed post-mortem analysis, see GUIDA_CONSULTAZIONE_DATI.md", "cyan"))
    print("="*80 + "\n")

if __name__ == "__main__":
    view_current_status()
