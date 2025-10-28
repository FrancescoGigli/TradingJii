#!/usr/bin/env python3
"""
📊 STOP LOSS SIMPLE ANALYZER

Analizza i trade LOSS senza scaricare dati aggiuntivi.
Usa solo i metadata esistenti per calcolare statistiche.

UTILIZZO:
    python analyze_sl_simple.py
"""

import json
import numpy as np
from pathlib import Path
from termcolor import colored

def load_trades():
    """Carica trade dal JSON"""
    file_path = Path("backtest_visualization_data.json")
    
    if not file_path.exists():
        print(colored("❌ File not found!", "red"))
        return None
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    all_trades = []
    for symbol, symbol_data in data.items():
        for trade in symbol_data['trades']:
            trade['symbol'] = symbol
            all_trades.append(trade)
    
    return all_trades


def main():
    print(colored("\n📊 STOP LOSS SIMPLE ANALYZER", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan"))
    
    # Load
    all_trades = load_trades()
    if not all_trades:
        return
    
    # Filter
    loss_trades = [t for t in all_trades if t['result'] == 'LOSS']
    sl_trades = [t for t in loss_trades if t.get('exit_reason') == 'stop_loss']
    trailing_losses = [t for t in loss_trades if t.get('exit_reason') == 'trailing_stop']
    other_losses = [t for t in loss_trades if t.get('exit_reason') not in ['stop_loss', 'trailing_stop']]
    
    print(colored(f"✅ Loaded {len(all_trades)} trades\n", "green"))
    
    # Statistics
    print(colored("="*80, "cyan"))
    print(colored("📊 LOSS BREAKDOWN", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan"))
    
    print(f"Total LOSS Trades: {len(loss_trades)}")
    print(f"  Stop Loss hits: {len(sl_trades)} ({len(sl_trades)/len(loss_trades)*100:.1f}%)")
    print(f"  Trailing Stop losses: {len(trailing_losses)} ({len(trailing_losses)/len(loss_trades)*100:.1f}%)")
    print(f"  Other (backtest_end): {len(other_losses)} ({len(other_losses)/len(loss_trades)*100:.1f}%)")
    
    # SL Analysis
    print(colored("\n" + "="*80, "cyan"))
    print(colored("🛡️ STOP LOSS ANALYSIS", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan"))
    
    if sl_trades:
        sl_pnls = [t['pnl_pct'] for t in sl_trades]
        avg_sl = np.mean(sl_pnls)
        min_sl = min(sl_pnls)
        max_sl = max(sl_pnls)
        
        # Count exact -30%
        exact_30 = sum(1 for p in sl_pnls if abs(p - (-30)) < 0.5)
        
        print(f"Stop Loss Trades: {len(sl_trades)}")
        print(f"  Avg PnL: {avg_sl:.2f}%")
        print(f"  Min PnL: {min_sl:.2f}%")
        print(f"  Max PnL: {max_sl:.2f}%")
        print(f"  Exact -30%: {exact_30}/{len(sl_trades)} ({exact_30/len(sl_trades)*100:.1f}%)")
        
        # Distribution
        worse_than_30 = sum(1 for p in sl_pnls if p < -30)
        better_than_30 = sum(1 for p in sl_pnls if p > -30)
        
        print(f"\n  Distribution:")
        print(f"    Worse than -30%: {worse_than_30} ({worse_than_30/len(sl_trades)*100:.1f}%)")
        print(f"    Exactly -30%: {exact_30} ({exact_30/len(sl_trades)*100:.1f}%)")
        print(f"    Better than -30%: {better_than_30} ({better_than_30/len(sl_trades)*100:.1f}%)")
    
    # Trailing Analysis
    print(colored("\n" + "="*80, "cyan"))
    print(colored("🎪 TRAILING STOP LOSSES", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan"))
    
    if trailing_losses:
        trail_pnls = [t['pnl_pct'] for t in trailing_losses]
        avg_trail = np.mean(trail_pnls)
        min_trail = min(trail_pnls)
        max_trail = max(trail_pnls)
        
        # Range distribution
        ranges = [
            ('> 0%', lambda p: p > 0),
            ('-10% to 0%', lambda p: -10 <= p <= 0),
            ('-20% to -10%', lambda p: -20 <= p < -10),
            ('-30% to -20%', lambda p: -30 <= p < -20),
            ('< -30%', lambda p: p < -30)
        ]
        
        print(f"Trailing Stop Losses: {len(trailing_losses)}")
        print(f"  Avg PnL: {avg_trail:.2f}%")
        print(f"  Min PnL: {min_trail:.2f}%")
        print(f"  Max PnL: {max_trail:.2f}%")
        
        print(f"\n  Distribution:")
        for range_name, condition in ranges:
            count = sum(1 for p in trail_pnls if condition(p))
            if count > 0:
                print(f"    {range_name}: {count} ({count/len(trailing_losses)*100:.1f}%)")
    
    # Duration Analysis
    print(colored("\n" + "="*80, "cyan"))
    print(colored("⏱️ DURATION ANALYSIS", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan"))
    
    sl_durations = [t['duration_hours'] for t in sl_trades if 'duration_hours' in t]
    trail_durations = [t['duration_hours'] for t in trailing_losses if 'duration_hours' in t]
    
    if sl_durations:
        print(f"Stop Loss Trades:")
        print(f"  Avg Duration: {np.mean(sl_durations):.1f} hours")
        print(f"  Median Duration: {np.median(sl_durations):.1f} hours")
        print(f"  Min/Max: {min(sl_durations):.1f}h / {max(sl_durations):.1f}h")
    
    if trail_durations:
        print(f"\nTrailing Stop Losses:")
        print(f"  Avg Duration: {np.mean(trail_durations):.1f} hours")
        print(f"  Median Duration: {np.median(trail_durations):.1f} hours")
        print(f"  Min/Max: {min(trail_durations):.1f}h / {max(trail_durations):.1f}h")
    
    # Confidence Analysis
    print(colored("\n" + "="*80, "cyan"))
    print(colored("🎯 CONFIDENCE VS LOSS TYPE", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan"))
    
    if sl_trades:
        sl_xgb = np.mean([t['xgb_confidence'] for t in sl_trades]) * 100
        sl_rl = np.mean([t['rl_confidence'] for t in sl_trades]) * 100
        print(f"Stop Loss Trades:")
        print(f"  Avg XGB Confidence: {sl_xgb:.1f}%")
        print(f"  Avg RL Confidence: {sl_rl:.1f}%")
    
    if trailing_losses:
        trail_xgb = np.mean([t['xgb_confidence'] for t in trailing_losses]) * 100
        trail_rl = np.mean([t['rl_confidence'] for t in trailing_losses]) * 100
        print(f"\nTrailing Stop Losses:")
        print(f"  Avg XGB Confidence: {trail_xgb:.1f}%")
        print(f"  Avg RL Confidence: {trail_rl:.1f}%")
    
    # Recommendations
    print(colored("\n" + "="*80, "cyan"))
    print(colored("💡 INSIGHTS & RECOMMENDATIONS", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan"))
    
    sl_ratio = len(sl_trades) / len(loss_trades) if loss_trades else 0
    trail_ratio = len(trailing_losses) / len(loss_trades) if loss_trades else 0
    
    print(f"1. Stop Loss Distribution:")
    if sl_ratio > 0.6:
        print(colored(f"   ⚠️ HIGH: {sl_ratio*100:.1f}% of losses are SL hits", "yellow"))
        print(colored("   → Consider: Early exit rules or adaptive SL", "yellow"))
    else:
        print(colored(f"   ✅ NORMAL: {sl_ratio*100:.1f}% of losses are SL hits", "green"))
    
    print(f"\n2. Trailing Stop Losses:")
    if trail_ratio > 0.3:
        print(colored(f"   ⚠️ {trail_ratio*100:.1f}% losses from trailing", "yellow"))
        if trailing_losses and np.mean([t['pnl_pct'] for t in trailing_losses]) < -15:
            print(colored("   → Many trailing losses are severe (< -15%)", "yellow"))
            print(colored("   → Consider: Tighter trailing distance", "yellow"))
    else:
        print(colored(f"   ✅ {trail_ratio*100:.1f}% losses from trailing", "green"))
    
    print(f"\n3. Overall:")
    win_trades = [t for t in all_trades if t['result'] == 'WIN']
    total_win_pnl = sum(t['pnl_pct'] for t in win_trades)
    total_loss_pnl = sum(t['pnl_pct'] for t in loss_trades)
    net_pnl = total_win_pnl + total_loss_pnl
    
    print(f"   Total WIN P&L: {colored(f'+{total_win_pnl:.1f}%', 'green')}")
    print(f"   Total LOSS P&L: {colored(f'{total_loss_pnl:.1f}%', 'red')}")
    print(f"   Net P&L: {colored(f'{net_pnl:+.1f}%', 'green' if net_pnl > 0 else 'red', attrs=['bold'])}")
    
    profit_factor = abs(total_win_pnl / total_loss_pnl) if total_loss_pnl != 0 else 0
    print(f"   Profit Factor: {colored(f'{profit_factor:.2f}', 'green' if profit_factor > 1.5 else 'yellow')}")
    
    print(colored("\n✅ Analysis complete!\n", "green"))


if __name__ == "__main__":
    main()
