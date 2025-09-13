#!/usr/bin/env python3
"""
🚫 EXCLUSION UTILITIES

Utilità per gestire manualmente le esclusioni di simboli
"""

import logging
from termcolor import colored
from core.symbol_exclusion_manager import global_symbol_exclusion_manager

def print_exclusion_status():
    """Stampa lo stato completo delle esclusioni"""
    print(colored("\n🚫 SYMBOL EXCLUSION STATUS", "yellow", attrs=['bold']))
    
    summary = global_symbol_exclusion_manager.get_exclusion_summary()
    
    print(colored(f"📊 Total excluded symbols: {summary['total_excluded_count']}", "white"))
    print(colored(f"   🤖 Auto-excluded: {summary['auto_excluded_count']}", "cyan"))
    print(colored(f"   👤 Manual-excluded: {summary['manual_excluded_count']}", "blue"))
    print(colored(f"   🆕 Session-excluded: {summary['session_excluded_count']}", "yellow"))
    
    if summary['auto_excluded_symbols']:
        print(colored("\n🤖 Auto-excluded symbols:", "cyan"))
        for symbol in summary['auto_excluded_symbols']:
            symbol_short = symbol.replace('/USDT:USDT', '')
            print(colored(f"   - {symbol_short}", "white"))
    
    if summary['session_excluded_symbols']:
        print(colored("\n🆕 Excluded this session:", "yellow"))
        for symbol in summary['session_excluded_symbols']:
            symbol_short = symbol.replace('/USDT:USDT', '')
            print(colored(f"   - {symbol_short}", "yellow"))

def reset_exclusions():
    """Reset tutte le esclusioni automatiche"""
    print(colored("\n🔄 Resetting auto-excluded symbols...", "yellow"))
    global_symbol_exclusion_manager.reset_auto_excluded()
    print(colored("✅ Auto-excluded symbols cleared. Next run will re-test all symbols.", "green"))

if __name__ == "__main__":
    # Comando standalone per gestire esclusioni
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "status":
            print_exclusion_status()
        elif command == "reset":
            reset_exclusions()
        else:
            print("Usage: python utils/exclusion_utils.py [status|reset]")
    else:
        print_exclusion_status()
