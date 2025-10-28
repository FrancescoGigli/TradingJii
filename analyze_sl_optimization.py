#!/usr/bin/env python3
"""
📊 STOP LOSS OPTIMIZATION ANALYZER

Analizza i trade LOSS per identificare opportunità di early exit.
Scarica candele a 1m e calcola statistiche dettagliate.

UTILIZZO:
    python analyze_sl_optimization.py
"""

import json
import asyncio
import pandas as pd
import numpy as np
from pathlib import Path
from termcolor import colored
from datetime import datetime, timedelta
import ccxt.async_support as ccxt
from typing import Dict, List, Tuple
import sys

def load_trades():
    """Carica trade dal JSON"""
    file_path = Path("backtest_visualization_data.json")
    
    if not file_path.exists():
        print(colored("❌ File backtest_visualization_data.json not found!", "red"))
        print(colored("   Run: python backtest_calibration.py first", "yellow"))
        return None
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Estrai tutti i trade
    all_trades = []
    for symbol, symbol_data in data.items():
        for trade in symbol_data['trades']:
            trade['symbol'] = symbol
            all_trades.append(trade)
    
    return all_trades


async def download_1m_candles(symbol, start_time, end_time):
    """Scarica candele a 1m per il periodo del trade"""
    exchange = ccxt.bybit({'enableRateLimit': True, 'timeout': 30000})
    
    try:
        from fetcher import fetch_and_save_data
        df = await fetch_and_save_data(exchange, symbol, '1m')
        
        if df is None or len(df) == 0:
            return None
        
        # Filtra per range
        start = pd.to_datetime(start_time)
        end = pd.to_datetime(end_time)
        
        df_filtered = df[(df.index >= start) & (df.index <= end)]
        return df_filtered
        
    except Exception as e:
        print(colored(f"      Error: {str(e)[:50]}", "red"))
        return None
    finally:
        await exchange.close()


def analyze_trade_trajectory(trade, candles_df):
    """Analizza traiettoria del prezzo dopo entry"""
    entry_price = trade['entry_price']
    entry_time = pd.to_datetime(trade['entry_date'])
    
    candles_df = candles_df.copy()
    candles_df['price_change_pct'] = ((candles_df['close'] - entry_price) / entry_price) * 100
    candles_df['roe_10x'] = candles_df['price_change_pct'] * 10
    candles_df['minutes_elapsed'] = (candles_df.index - entry_time).total_seconds() / 60
    
    # Analisi minimi
    worst_price = candles_df['low'].min()
    worst_roe = ((worst_price - entry_price) / entry_price) * 1000
    worst_time_idx = candles_df['low'].idxmin()
    worst_minutes = (worst_time_idx - entry_time).total_seconds() / 60
    
    # Early warning signals
    early_signals = {}
    
    # Signal 1: Fast drop 15min
    first_15min = candles_df[candles_df['minutes_elapsed'] <= 15]
    if len(first_15min) > 0:
        worst_15min = first_15min['roe_10x'].min()
        early_signals['fast_drop_15min'] = worst_15min < -15
        early_signals['worst_15min_roe'] = worst_15min
    
    # Signal 2: Immediate reversal 5min
    first_5min = candles_df[candles_df['minutes_elapsed'] <= 5]
    if len(first_5min) > 0:
        worst_5min = first_5min['roe_10x'].min()
        early_signals['immediate_reversal'] = worst_5min < -10
        early_signals['worst_5min_roe'] = worst_5min
    
    # Signal 3: Persistent weakness
    first_hour = candles_df[candles_df['minutes_elapsed'] <= 60]
    if len(first_hour) > 0:
        candles_above = (first_hour['close'] > entry_price).sum()
        pct_above = (candles_above / len(first_hour) * 100)
        early_signals['persistent_weakness'] = pct_above < 20
        early_signals['pct_time_above_entry'] = pct_above
    
    # Potential savings
    potential_exits = []
    
    for exit_roe in [-15, -20]:
        candidates = candles_df[candles_df['roe_10x'] <= exit_roe]
        if len(candidates) > 0:
            first_hit = candidates.iloc[0]
            potential_exits.append({
                'strategy': f'exit_at_{exit_roe}_roe',
                'exit_roe': exit_roe,
                'actual_roe': trade['pnl_pct'],
                'savings': trade['pnl_pct'] - exit_roe,
                'minutes_to_exit': first_hit['minutes_elapsed']
            })
    
    return {
        'worst_price': worst_price,
        'worst_roe': worst_roe,
        'worst_minutes': worst_minutes,
        'early_signals': early_signals,
        'potential_exits': potential_exits,
        'candles_analyzed': len(candles_df)
    }


async def main():
    print(colored("\n📊 STOP LOSS OPTIMIZATION ANALYZER", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan"))
    
    # Load trades
    print(colored("📥 Loading trades...", "yellow"))
    all_trades = load_trades()
    
    if not all_trades:
        return
    
    # Filter LOSS trades
    loss_trades = [t for t in all_trades if t['result'] == 'LOSS']
    print(colored(f"✅ Loaded {len(all_trades)} trades ({len(loss_trades)} LOSS)\n", "green"))
    
    # Analyze
    results = []
    
    print(colored("🔍 Analyzing LOSS trades...\n", "yellow"))
    
    for idx, trade in enumerate(loss_trades, 1):
        symbol = trade['symbol']
        pnl = trade['pnl_pct']
        exit_reason = trade.get('exit_reason', 'unknown')
        
        print(colored(f"   [{idx}/{len(loss_trades)}] {symbol} ({pnl:+.1f}%, {exit_reason})", "cyan"), end=" ", flush=True)
        
        candles_df = await download_1m_candles(symbol, trade['entry_date'], trade['exit_date'])
        
        if candles_df is None or len(candles_df) < 5:
            print(colored("⚠️ Skip", "yellow"))
            continue
        
        analysis = analyze_trade_trajectory(trade, candles_df)
        
        result = {
            'trade': trade,
            'analysis': analysis
        }
        results.append(result)
        
        print(colored(f"✓ ({analysis['candles_analyzed']} candles)", "green"))
    
    # Statistics
    print(colored("\n" + "="*80, "cyan"))
    print(colored("📊 ANALYSIS RESULTS", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan"))
    
    if not results:
        print(colored("❌ No trades analyzed", "red"))
        return
    
    # Early exit opportunities
    trades_with_fast_drop = sum(1 for r in results if r['analysis']['early_signals'].get('fast_drop_15min', False))
    trades_with_immediate_rev = sum(1 for r in results if r['analysis']['early_signals'].get('immediate_reversal', False))
    trades_with_weakness = sum(1 for r in results if r['analysis']['early_signals'].get('persistent_weakness', False))
    
    print(colored("🚨 EARLY WARNING SIGNALS:", "yellow", attrs=['bold']))
    print(f"  Fast Drop (15min): {trades_with_fast_drop}/{len(results)} ({trades_with_fast_drop/len(results)*100:.1f}%)")
    print(f"  Immediate Reversal (5min): {trades_with_immediate_rev}/{len(results)} ({trades_with_immediate_rev/len(results)*100:.1f}%)")
    print(f"  Persistent Weakness (1h): {trades_with_weakness}/{len(results)} ({trades_with_weakness/len(results)*100:.1f}%)")
    
    # Savings analysis
    print(colored("\n💰 POTENTIAL SAVINGS WITH EARLY EXIT:", "yellow", attrs=['bold']))
    
    for strategy_name in ['exit_at_-15_roe', 'exit_at_-20_roe']:
        trades_with_strategy = [r for r in results if any(e['strategy'] == strategy_name for e in r['analysis']['potential_exits'])]
        
        if trades_with_strategy:
            total_actual_loss = sum(r['trade']['pnl_pct'] for r in trades_with_strategy)
            
            exit_roe = -15 if '15' in strategy_name else -20
            total_early_exit_loss = exit_roe * len(trades_with_strategy)
            
            total_savings = total_actual_loss - total_early_exit_loss
            avg_savings = total_savings / len(trades_with_strategy)
            
            avg_time_to_exit = np.mean([
                next(e['minutes_to_exit'] for e in r['analysis']['potential_exits'] if e['strategy'] == strategy_name)
                for r in trades_with_strategy
            ])
            
            print(f"\n  Strategy: {strategy_name}")
            print(f"    Applicable: {len(trades_with_strategy)}/{len(results)} trades ({len(trades_with_strategy)/len(results)*100:.1f}%)")
            print(f"    Total Actual Loss: {total_actual_loss:.1f}%")
            print(f"    Total Early Exit Loss: {total_early_exit_loss:.1f}%")
            print(f"    Total Savings: {colored(f'+{total_savings:.1f}%', 'green', attrs=['bold'])}")
            print(f"    Avg Savings per Trade: {colored(f'+{avg_savings:.1f}%', 'green')}")
            print(f"    Avg Time to Exit: {avg_time_to_exit:.1f} minutes")
    
    # SL Protection Value
    print(colored("\n🛡️ STOP LOSS PROTECTION VALUE:", "yellow", attrs=['bold']))
    
    sl_trades = [r for r in results if r['trade'].get('exit_reason') == 'stop_loss']
    if sl_trades:
        trades_worse_than_sl = sum(1 for r in sl_trades if r['analysis']['worst_roe'] < -30)
        avg_worst_roe = np.mean([r['analysis']['worst_roe'] for r in sl_trades])
        
        print(f"  Stop Loss Trades: {len(sl_trades)}")
        print(f"  Would Have Been Worse: {trades_worse_than_sl}/{len(sl_trades)} ({trades_worse_than_sl/len(sl_trades)*100:.1f}%)")
        print(f"  Avg Worst ROE: {avg_worst_roe:.1f}% (vs -30% SL)")
        
        if trades_worse_than_sl > 0:
            total_protection = sum(abs(r['analysis']['worst_roe']) - 30 for r in sl_trades if r['analysis']['worst_roe'] < -30)
            print(f"  Total Protection Value: {colored(f'+{total_protection:.1f}%', 'green', attrs=['bold'])}")
    
    # Overall recommendation
    print(colored("\n" + "="*80, "cyan"))
    print(colored("💡 RECOMMENDATIONS", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan"))
    
    early_exit_beneficial = trades_with_fast_drop > len(results) * 0.3
    
    if early_exit_beneficial:
        print(colored("✅ EARLY EXIT SYSTEM RECOMMENDED", "green", attrs=['bold']))
        print("  Reason: >30% trades show early warning signals")
        print("  Suggested: Implement -15% or -20% ROE early exit")
    else:
        print(colored("⚠️ CURRENT SL SEEMS ADEQUATE", "yellow", attrs=['bold']))
        print("  Reason: Most SL hits protected from worse losses")
        print("  Suggested: Keep current SL at -30% ROE")
    
    print(colored("\n✅ Analysis complete!", "green"))
    print(colored(f"📁 Analyzed {len(results)} LOSS trades\n", "cyan"))


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
