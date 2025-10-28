#!/usr/bin/env python3
"""
📊 EARLY EXIT SYSTEM ANALYZER

Analizza l'impatto dell'Early Exit System sui risultati del backtest
"""

import json
import pandas as pd
import numpy as np
from termcolor import colored

def analyze_early_exit():
    print(colored("\n📊 EARLY EXIT SYSTEM ANALYZER", "cyan", attrs=['bold']))
    print("=" * 80)
    
    # Load trades
    with open('backtest_visualization_data.json', 'r') as f:
        data = json.load(f)
    
    all_trades = []
    for symbol, symbol_data in data.items():
        all_trades.extend(symbol_data['trades'])
    
    df = pd.DataFrame(all_trades)
    
    print(f"\n✅ Loaded {len(df)} trades\n")
    print("=" * 80)
    
    # Exit reason breakdown
    print("📊 EXIT REASON BREAKDOWN")
    print("=" * 80)
    exit_counts = df['exit_reason'].value_counts()
    
    for reason, count in exit_counts.items():
        pct = (count / len(df)) * 100
        
        # Get win rate for this reason
        reason_trades = df[df['exit_reason'] == reason]
        wins = len(reason_trades[reason_trades['result'] == 'WIN'])
        win_rate = (wins / len(reason_trades)) * 100
        
        # Average PnL
        avg_pnl = reason_trades['pnl_pct'].mean()
        
        emoji = "🟢" if win_rate > 50 else "🔴"
        print(f"{emoji} {reason:25s}: {count:4d} ({pct:5.1f}%) | WR: {win_rate:5.1f}% | Avg PnL: {avg_pnl:+6.2f}%")
    
    print("\n" + "=" * 80)
    print("🔍 EARLY EXIT DETAILED ANALYSIS")
    print("=" * 80)
    
    # Early exit types
    early_exit_types = ['early_exit_immediate', 'early_exit_fast', 'early_exit_persistent']
    
    for exit_type in early_exit_types:
        trades = df[df['exit_reason'] == exit_type]
        if len(trades) == 0:
            continue
        
        wins = len(trades[trades['result'] == 'WIN'])
        losses = len(trades[trades['result'] == 'LOSS'])
        win_rate = (wins / len(trades)) * 100
        
        avg_pnl_win = trades[trades['result'] == 'WIN']['pnl_pct'].mean() if wins > 0 else 0
        avg_pnl_loss = trades[trades['result'] == 'LOSS']['pnl_pct'].mean() if losses > 0 else 0
        avg_pnl_total = trades['pnl_pct'].mean()
        
        avg_duration = trades['duration_hours'].mean()
        
        print(f"\n{exit_type}:")
        print(f"  Trades: {len(trades)} ({len(trades)/len(df)*100:.1f}% of total)")
        print(f"  Win Rate: {win_rate:.1f}% ({wins}W/{losses}L)")
        print(f"  Avg Duration: {avg_duration:.1f}h")
        print(f"  Avg PnL (Total): {avg_pnl_total:+.2f}%")
        print(f"  Avg PnL (WIN): {avg_pnl_win:+.2f}%")
        print(f"  Avg PnL (LOSS): {avg_pnl_loss:+.2f}%")
        
        # Lowest ROE reached
        if 'lowest_roe' in trades.columns:
            avg_lowest_roe = trades['lowest_roe'].mean()
            print(f"  Avg Lowest ROE: {avg_lowest_roe:.2f}%")
    
    print("\n" + "=" * 80)
    print("🎯 COMPARISON: EARLY EXIT vs TRAILING STOP")
    print("=" * 80)
    
    early_exits = df[df['exit_reason'].isin(early_exit_types)]
    trailing_wins = df[df['exit_reason'] == 'trailing_stop']
    
    if len(early_exits) > 0:
        print(f"\n🔴 EARLY EXITS:")
        print(f"  Total: {len(early_exits)}")
        print(f"  Win Rate: {len(early_exits[early_exits['result']=='WIN'])/len(early_exits)*100:.1f}%")
        print(f"  Avg PnL: {early_exits['pnl_pct'].mean():+.2f}%")
        print(f"  Total PnL: {early_exits['pnl_pct'].sum():+.2f}%")
    
    if len(trailing_wins) > 0:
        print(f"\n🟢 TRAILING STOP EXITS:")
        print(f"  Total: {len(trailing_wins)}")
        print(f"  Win Rate: {len(trailing_wins[trailing_wins['result']=='WIN'])/len(trailing_wins)*100:.1f}%")
        print(f"  Avg PnL: {trailing_wins['pnl_pct'].mean():+.2f}%")
        print(f"  Total PnL: {trailing_wins['pnl_pct'].sum():+.2f}%")
    
    print("\n" + "=" * 80)
    print("💰 OVERALL SUMMARY")
    print("=" * 80)
    
    wins = df[df['result'] == 'WIN']
    losses = df[df['result'] == 'LOSS']
    
    print(f"\nTotal Trades: {len(df)}")
    print(f"Win Rate: {len(wins)/len(df)*100:.1f}% ({len(wins)}W/{len(losses)}L)")
    print(f"Avg PnL: {df['pnl_pct'].mean():+.2f}%")
    print(f"Total PnL: {df['pnl_pct'].sum():+.2f}%")
    print(f"Profit Factor: {abs(wins['pnl_pct'].sum() / losses['pnl_pct'].sum()):.2f}")
    
    print("\n" + "=" * 80)
    print("🎯 RECOMMENDATIONS")
    print("=" * 80)
    
    # Percentage of early exits that are losses
    early_exit_losses = len(early_exits[early_exits['result'] == 'LOSS'])
    early_exit_pct = (early_exit_losses / len(losses)) * 100
    
    print(f"\n⚠️  {early_exit_pct:.1f}% of all losses are from Early Exit System")
    
    if early_exit_pct > 30:
        print(colored("\n⚠️  WARNING: Early Exit System is TOO aggressive!", "yellow", attrs=['bold']))
        print("\nConsiderations:")
        print("  1. Early exits have poor win rate")
        print("  2. Many trades could recover if given more time")
        print("  3. Consider:")
        print("     - Increasing time thresholds (15m -> 30m, 60m -> 90m)")
        print("     - Increasing ROE drop thresholds (-5% -> -7%, -10% -> -15%)")
        print("     - Disabling certain exit types (e.g., persistent)")
    
    print("\n✅ Analysis complete!\n")

if __name__ == "__main__":
    analyze_early_exit()
