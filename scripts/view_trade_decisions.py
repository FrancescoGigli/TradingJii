#!/usr/bin/env python3
"""
📊 TRADE DECISIONS VIEWER

Script per visualizzare e analizzare le decisioni di trading salvate nel database.

Uso:
    python view_trade_decisions.py --last 100
    python view_trade_decisions.py --symbol BTC --status closed
    python view_trade_decisions.py --stats
    python view_trade_decisions.py --detail 123
"""

import argparse
import sys
from datetime import datetime
from termcolor import colored
from tabulate import tabulate

# Add project root to path
sys.path.append('.')

from core.trade_decision_logger import global_trade_decision_logger


def display_decisions_table(decisions, show_details=False):
    """Display decisions in a formatted table"""
    if not decisions:
        print(colored("📭 No decisions found", "yellow"))
        return
    
    print(colored(f"\n📊 TRADING DECISIONS ({len(decisions)} total)", "cyan", attrs=['bold']))
    print(colored("=" * 120, "cyan"))
    
    # Prepare table data
    headers = ["ID", "Time", "Symbol", "Side", "Signal", "Entry $", "Exit $", "SL $", 
               "Leverage", "Margin $", "XGB %", "RL", "Status", "PnL %", "PnL $"]
    
    rows = []
    for d in decisions:
        # Format timestamp
        try:
            dt = datetime.fromisoformat(d.timestamp)
            time_str = dt.strftime("%m/%d %H:%M")
        except:
            time_str = d.timestamp[:16]
        
        # Format symbol
        symbol_short = d.symbol.replace('/USDT:USDT', '')
        
        # Format XGB confidence
        xgb_conf = f"{d.xgb_confidence*100:.1f}"
        
        # Format RL approval
        if d.rl_approved is not None:
            rl_str = "✅" if d.rl_approved else "❌"
        else:
            rl_str = "-"
        
        # Format exit price
        exit_str = f"{d.exit_price:.2f}" if d.exit_price else "-"
        
        # Format PnL with colors
        if d.status == "CLOSED":
            pnl_pct_str = f"{d.pnl_pct:+.2f}" if d.pnl_pct else "0.00"
            pnl_usd_str = f"{d.pnl_usd:+.2f}" if d.pnl_usd else "0.00"
        else:
            pnl_pct_str = "-"
            pnl_usd_str = "-"
        
        rows.append([
            d.id,
            time_str,
            symbol_short,
            d.position_side.upper(),
            d.signal_name,
            f"{d.entry_price:.2f}",
            exit_str,
            f"{d.stop_loss:.2f}",
            f"{d.leverage}x",
            f"{d.margin_used:.2f}",
            xgb_conf,
            rl_str,
            d.status,
            pnl_pct_str,
            pnl_usd_str
        ])
    
    # Print table
    print(tabulate(rows, headers=headers, tablefmt="grid"))
    
    if show_details:
        print(colored("\n📋 DECISION DETAILS", "yellow", attrs=['bold']))
        for d in decisions[:5]:  # Show details for first 5
            display_decision_detail(d)


def display_decision_detail(decision):
    """Display detailed information for a single decision"""
    symbol_short = decision.symbol.replace('/USDT:USDT', '')
    
    print(colored(f"\n{'='*80}", "cyan"))
    print(colored(f"📊 DECISION #{decision.id}: {symbol_short} {decision.signal_name}", "cyan", attrs=['bold']))
    print(colored(f"{'='*80}", "cyan"))
    
    # Basic info
    print(colored("\n🎯 BASIC INFORMATION:", "yellow"))
    print(f"  Entry Time: {decision.timestamp}")
    print(f"  Symbol: {decision.symbol}")
    print(f"  Signal: {decision.signal_name} ({decision.position_side.upper()})")
    print(f"  Entry Price: ${decision.entry_price:.6f}")
    print(f"  Position Size: {decision.position_size:.4f}")
    print(f"  Leverage: {decision.leverage}x")
    print(f"  Margin Used: ${decision.margin_used:.2f}")
    print(f"  Stop Loss: ${decision.stop_loss:.6f}")
    
    # XGBoost decision
    print(colored("\n🧠 ENSEMBLE XGBOOST DECISION:", "yellow"))
    print(f"  Overall Confidence: {decision.xgb_confidence*100:.1f}%")
    print(f"  Timeframe Votes:")
    if decision.tf_15m_vote is not None:
        vote_names = {0: 'SELL', 1: 'BUY', 2: 'NEUTRAL'}
        print(f"    15m: {vote_names.get(decision.tf_15m_vote, 'N/A')}")
        print(f"    30m: {vote_names.get(decision.tf_30m_vote, 'N/A')}")
        print(f"    1h: {vote_names.get(decision.tf_1h_vote, 'N/A')}")
    
    # RL decision
    if decision.rl_confidence is not None:
        print(colored("\n🤖 RL FILTER DECISION:", "yellow"))
        print(f"  RL Confidence: {decision.rl_confidence*100:.1f}%")
        print(f"  RL Approved: {'✅ YES' if decision.rl_approved else '❌ NO'}")
        if decision.rl_primary_reason:
            print(f"  Primary Reason: {decision.rl_primary_reason}")
    
    # Market context
    if decision.market_volatility is not None:
        print(colored("\n🌍 MARKET CONTEXT:", "yellow"))
        print(f"  Volatility: {decision.market_volatility*100:.2f}%")
        if decision.rsi_position:
            print(f"  RSI Position: {decision.rsi_position:.1f}")
        if decision.trend_strength:
            print(f"  Trend Strength (ADX): {decision.trend_strength:.1f}")
        if decision.volume_surge:
            print(f"  Volume Surge: {decision.volume_surge:.2f}x")
    
    # Portfolio state
    print(colored("\n💼 PORTFOLIO STATE:", "yellow"))
    print(f"  Available Balance: ${decision.available_balance:.2f}")
    print(f"  Active Positions: {decision.active_positions_count}")
    
    # Result
    if decision.status == "CLOSED":
        print(colored("\n💰 RESULT:", "yellow"))
        print(f"  Exit Time: {decision.exit_time}")
        print(f"  Exit Price: ${decision.exit_price:.6f}")
        print(f"  Close Reason: {decision.close_reason}")
        
        pnl_color = "green" if decision.pnl_pct and decision.pnl_pct > 0 else "red"
        print(colored(f"  PnL: {decision.pnl_pct:+.2f}% (${decision.pnl_usd:+.2f})", pnl_color, attrs=['bold']))
    else:
        print(colored(f"\n📈 Status: {decision.status}", "yellow"))


def display_statistics():
    """Display comprehensive statistics"""
    stats = global_trade_decision_logger.get_statistics()
    
    print(colored("\n📊 TRADE DECISION STATISTICS", "cyan", attrs=['bold']))
    print(colored("=" * 80, "cyan"))
    
    print(colored("\n📈 GENERAL STATS:", "yellow"))
    print(f"  Total Decisions Logged: {stats.get('total_decisions', 0)}")
    print(f"  Open Positions: {stats.get('open_positions', 0)}")
    print(f"  Closed Positions: {stats.get('closed_positions', 0)}")
    print(f"  Market Snapshots: {stats.get('total_snapshots', 0)}")
    
    if stats.get('closed_positions', 0) > 0:
        print(colored("\n💰 PERFORMANCE:", "yellow"))
        win_rate = stats.get('win_rate_pct', 0)
        win_color = "green" if win_rate >= 50 else "red"
        print(colored(f"  Win Rate: {win_rate:.1f}%", win_color))
        
        avg_pnl_pct = stats.get('avg_pnl_pct', 0)
        avg_color = "green" if avg_pnl_pct > 0 else "red"
        print(colored(f"  Average PnL: {avg_pnl_pct:+.2f}%", avg_color))
        print(colored(f"  Average PnL USD: ${stats.get('avg_pnl_usd', 0):+.2f}", avg_color))
    
    print(colored("\n📊 LOGGING STATS:", "yellow"))
    print(f"  Decisions Logged (session): {stats.get('decisions_logged', 0)}")
    print(f"  Snapshots Logged (session): {stats.get('snapshots_logged', 0)}")
    print(f"  Decisions Closed (session): {stats.get('decisions_closed', 0)}")


def display_trade_with_snapshots(decision_id):
    """Display trade with all market snapshots"""
    trade_data = global_trade_decision_logger.get_trade_with_snapshots(decision_id)
    
    if not trade_data:
        print(colored(f"❌ Trade #{decision_id} not found", "red"))
        return
    
    decision = trade_data['decision']
    snapshots = trade_data['snapshots']
    
    # Display decision details
    display_decision_detail(decision)
    
    # Display snapshots
    if snapshots:
        print(colored(f"\n📈 MARKET SNAPSHOTS ({len(snapshots)} total):", "magenta", attrs=['bold']))
        print(colored("=" * 80, "magenta"))
        
        for snap in snapshots:
            snap_time_str = snap['snapshot_time'][:16] if snap['snapshot_time'] else "N/A"
            snap_type = snap['snapshot_type']
            
            print(colored(f"\n  [{snap_type}] {snap_time_str}", "cyan", attrs=['bold']))
            
            # Display 15m data
            if snap.get('tf_15m_price'):
                print(f"    15m: Price=${snap['tf_15m_price']:.2f} | RSI={snap.get('tf_15m_rsi', 0):.1f} | "
                      f"EMA5=${snap.get('tf_15m_ema5', 0):.2f} | Vol={snap.get('tf_15m_volume', 0):.0f}")
            
            # Display 30m data
            if snap.get('tf_30m_price'):
                print(f"    30m: Price=${snap['tf_30m_price']:.2f} | RSI={snap.get('tf_30m_rsi', 0):.1f} | "
                      f"EMA5=${snap.get('tf_30m_ema5', 0):.2f} | Vol={snap.get('tf_30m_volume', 0):.0f}")
            
            # Display 1h data
            if snap.get('tf_1h_price'):
                print(f"    1h:  Price=${snap['tf_1h_price']:.2f} | RSI={snap.get('tf_1h_rsi', 0):.1f} | "
                      f"EMA5=${snap.get('tf_1h_ema5', 0):.2f} | Vol={snap.get('tf_1h_volume', 0):.0f}")
    else:
        print(colored("\n📭 No market snapshots available for this trade", "yellow"))


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="View and analyze trading decisions from database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python view_trade_decisions.py --last 50
  python view_trade_decisions.py --last 100 --status CLOSED
  python view_trade_decisions.py --stats
  python view_trade_decisions.py --detail 123
        """
    )
    
    parser.add_argument('--last', type=int, help='Show last N decisions (default: 20)', default=20)
    parser.add_argument('--status', choices=['OPEN', 'CLOSED', 'ALL'], 
                       help='Filter by status', default='ALL')
    parser.add_argument('--symbol', type=str, help='Filter by symbol (e.g., BTC)')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    parser.add_argument('--detail', type=int, help='Show detailed view for decision ID')
    parser.add_argument('--verbose', action='store_true', help='Show detailed info for all decisions')
    
    args = parser.parse_args()
    
    # Show statistics
    if args.stats:
        display_statistics()
        return
    
    # Show detail for specific decision
    if args.detail:
        display_trade_with_snapshots(args.detail)
        return
    
    # Get decisions
    status_filter = None if args.status == 'ALL' else args.status
    decisions = global_trade_decision_logger.get_last_n_positions(
        n=args.last,
        status=status_filter
    )
    
    # Filter by symbol if specified
    if args.symbol:
        symbol_upper = args.symbol.upper()
        decisions = [d for d in decisions if symbol_upper in d.symbol]
    
    # Display decisions
    display_decisions_table(decisions, show_details=args.verbose)
    
    # Show quick stats
    if decisions:
        closed_decisions = [d for d in decisions if d.status == 'CLOSED']
        if closed_decisions:
            wins = sum(1 for d in closed_decisions if d.pnl_pct and d.pnl_pct > 0)
            win_rate = (wins / len(closed_decisions)) * 100
            avg_pnl = sum(d.pnl_pct for d in closed_decisions if d.pnl_pct) / len(closed_decisions)
            
            print(colored(f"\n📊 QUICK STATS (from displayed trades):", "cyan"))
            print(f"  Closed Trades: {len(closed_decisions)}")
            win_color = "green" if win_rate >= 50 else "red"
            print(colored(f"  Win Rate: {win_rate:.1f}% ({wins}/{len(closed_decisions)})", win_color))
            pnl_color = "green" if avg_pnl > 0 else "red"
            print(colored(f"  Average PnL: {avg_pnl:+.2f}%", pnl_color))


if __name__ == "__main__":
    main()
