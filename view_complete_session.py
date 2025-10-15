#!/usr/bin/env python3
"""
📊 COMPLETE SESSION VIEWER

Visualizza l'intera sessione di trading con:
1. Tutte le decisioni ML (BUY/SELL signals)
2. Decisioni eseguite vs rifiutate
3. Trade aperti attualmente
4. Trade chiusi con motivazione

Usage: python view_complete_session.py
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from termcolor import colored


def get_ml_decisions():
    """Get all ML decisions from this session"""
    db_path = Path("data_cache") / "trade_decisions.db"
    
    if not db_path.exists():
        return []
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get decisions from today
    today = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute("""
        SELECT 
            decision_time,
            symbol,
            decision,
            confidence,
            was_executed,
            rejection_reason,
            entry_price,
            exit_price,
            pnl_pct,
            close_reason
        FROM trade_decisions
        WHERE DATE(decision_time) = ?
        ORDER BY decision_time DESC
    """, (today,))
    
    decisions = cursor.fetchall()
    conn.close()
    
    return decisions


def format_decision_table(decisions):
    """Format decisions as a table"""
    if not decisions:
        print(colored("📭 Nessuna decisione ML in questa sessione", "yellow"))
        return
    
    print("=" * 150)
    print(colored("🤖 ML DECISIONS - SESSIONE CORRENTE", "cyan", attrs=['bold']))
    print("=" * 150)
    
    # Group by status
    executed = [d for d in decisions if d[4] == 1]  # was_executed = 1
    rejected = [d for d in decisions if d[4] == 0]  # was_executed = 0
    opened = [d for d in executed if d[7] is None]  # exit_price is None
    closed = [d for d in executed if d[7] is not None]  # exit_price is not None
    
    print(f"\n📊 RIEPILOGO:")
    print(f"   Totali decisioni: {len(decisions)}")
    print(f"   ✅ Eseguite: {len(executed)} ({len(opened)} aperte, {len(closed)} chiuse)")
    print(f"   ❌ Rifiutate: {len(rejected)}")
    print()
    
    # 1. DECISIONI ESEGUITE - APERTE
    if opened:
        print(colored("\n🟢 TRADE APERTI (ESEGUITI)", "green", attrs=['bold']))
        print("-" * 150)
        print(f"{'Time':<10} {'Symbol':<10} {'Decision':<8} {'Conf':<6} {'Entry':<12} {'Current Status':<30}")
        print("-" * 150)
        
        for d in opened:
            time_str = datetime.fromisoformat(d[0]).strftime("%H:%M:%S")
            symbol = d[1].replace('/USDT:USDT', '')
            decision = d[2]
            confidence = f"{d[3]:.1%}"
            entry = f"${d[6]:.6f}" if d[6] else "N/A"
            
            decision_color = "green" if decision == "BUY" else "red"
            decision_str = colored(f"{'↑ LONG' if decision == 'BUY' else '↓ SHORT'}", decision_color)
            
            print(f"{time_str:<10} {symbol:<10} {decision_str:<16} {confidence:<6} {entry:<12} {'POSIZIONE ATTIVA':<30}")
    
    # 2. DECISIONI ESEGUITE - CHIUSE
    if closed:
        print(colored("\n🔵 TRADE CHIUSI (ESEGUITI)", "blue", attrs=['bold']))
        print("-" * 150)
        print(f"{'Time':<10} {'Symbol':<10} {'Decision':<8} {'Conf':<6} {'Entry→Exit':<25} {'PnL':<12} {'Reason':<30}")
        print("-" * 150)
        
        for d in closed:
            time_str = datetime.fromisoformat(d[0]).strftime("%H:%M:%S")
            symbol = d[1].replace('/USDT:USDT', '')
            decision = d[2]
            confidence = f"{d[3]:.1%}"
            entry = d[6] if d[6] else 0
            exit_price = d[7] if d[7] else 0
            pnl_pct = d[8] if d[8] else 0
            close_reason = d[9] if d[9] else "UNKNOWN"
            
            entry_exit = f"${entry:.6f} → ${exit_price:.6f}"
            
            # Format PnL with color
            if pnl_pct > 0:
                pnl_str = colored(f"+{pnl_pct:.2f}%", "green")
            else:
                pnl_str = colored(f"{pnl_pct:.2f}%", "red")
            
            # Format close reason
            if "TRAILING" in close_reason:
                reason_str = colored("🎪 Trailing", "green")
            elif "STOP_LOSS" in close_reason:
                if pnl_pct > 0:
                    reason_str = colored("✅ SL (profit)", "green")
                else:
                    reason_str = colored("❌ SL (loss)", "red")
            else:
                reason_str = "❓ Unknown"
            
            decision_color = "green" if decision == "BUY" else "red"
            decision_str = colored(f"{'↑ LONG' if decision == 'BUY' else '↓ SHORT'}", decision_color)
            
            print(f"{time_str:<10} {symbol:<10} {decision_str:<16} {confidence:<6} {entry_exit:<25} {pnl_str:<20} {reason_str:<30}")
    
    # 3. DECISIONI RIFIUTATE
    if rejected:
        print(colored("\n❌ DECISIONI RIFIUTATE (NON ESEGUITE)", "yellow", attrs=['bold']))
        print("-" * 150)
        print(f"{'Time':<10} {'Symbol':<10} {'Decision':<8} {'Conf':<6} {'Rejection Reason':<80}")
        print("-" * 150)
        
        for d in rejected:
            time_str = datetime.fromisoformat(d[0]).strftime("%H:%M:%S")
            symbol = d[1].replace('/USDT:USDT', '')
            decision = d[2]
            confidence = f"{d[3]:.1%}"
            rejection = d[5] if d[5] else "N/A"
            
            decision_color = "green" if decision == "BUY" else "red"
            decision_str = colored(f"{'↑ LONG' if decision == 'BUY' else '↓ SHORT'}", decision_color)
            
            print(f"{time_str:<10} {symbol:<10} {decision_str:<16} {confidence:<6} {rejection:<80}")
    
    print("=" * 150)


def main():
    """Main entry point"""
    print("\n" + "=" * 150)
    print(colored("📊 COMPLETE SESSION VIEWER - TUTTE LE DECISIONI ML", "cyan", attrs=['bold']))
    print("=" * 150)
    
    decisions = get_ml_decisions()
    format_decision_table(decisions)
    
    print("\n" + colored("💡 TIP:", "yellow", attrs=['bold']))
    print("   - Verde = LONG positions")
    print("   - Rosso = SHORT positions")
    print("   - ✅ = Trade chiuso in profit")
    print("   - ❌ = Trade chiuso in loss")
    print("   - 🎪 = Chiuso da trailing stop")
    print()


if __name__ == "__main__":
    main()
