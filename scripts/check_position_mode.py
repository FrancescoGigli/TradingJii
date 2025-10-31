#!/usr/bin/env python3
"""
🔍 VERIFICA POSITION MODE SU BYBIT

Controlla se l'account è in One-Way o Hedge Mode.
Questo è CRITICO per capire come impostare gli stop loss.
"""

import asyncio
import sys
import os
import platform

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ccxt.async_support as ccxt
from config import API_KEY, API_SECRET
from termcolor import colored

# FIX for Windows: Use SelectorEventLoop instead of ProactorEventLoop
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def check_position_mode():
    """
    Verifica il position mode dell'account Bybit
    """
    exchange = None
    try:
        # Initialize Bybit exchange
        exchange = ccxt.bybit({
            'apiKey': API_KEY,
            'secret': API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'recvWindow': 10000
            }
        })
        
        print(colored("=" * 80, "cyan"))
        print(colored("🔍 CHECKING BYBIT POSITION MODE", "cyan", attrs=['bold']))
        print(colored("=" * 80, "cyan"))
        print()
        
        # Fetch account info
        print("📊 Fetching account configuration...")
        
        # Method 1: Check via position info
        positions = await exchange.fetch_positions()
        
        if not positions:
            print(colored("⚠️  No positions found. Creating test...", "yellow"))
        else:
            print(colored(f"✅ Found {len(positions)} positions", "green"))
            print()
            
            # Analyze position mode from positionIdx
            position_modes = {}
            for pos in positions[:5]:  # Check first 5
                if float(pos.get('contracts', 0)) != 0:
                    symbol = pos.get('symbol', 'N/A')
                    position_idx = pos.get('info', {}).get('positionIdx', 'N/A')
                    side = pos.get('side', 'N/A')
                    
                    position_modes[symbol] = {
                        'positionIdx': position_idx,
                        'side': side,
                        'contracts': pos.get('contracts', 0)
                    }
                    
                    print(f"  📍 {symbol}")
                    print(f"      Side: {side}")
                    print(f"      Position Index: {position_idx}")
                    print(f"      Contracts: {pos.get('contracts', 0)}")
                    print()
            
            # Determine mode
            if position_modes:
                idx_values = [v['positionIdx'] for v in position_modes.values()]
                
                if all(idx == 0 or idx == '0' for idx in idx_values):
                    print(colored("=" * 80, "green"))
                    print(colored("🎯 POSITION MODE: ONE-WAY MODE", "green", attrs=['bold']))
                    print(colored("=" * 80, "green"))
                    print()
                    print("✅ Correct configuration:")
                    print("   - Use position_idx = 0 for ALL positions")
                    print("   - Same stop loss for both LONG and SHORT")
                    print()
                    return "oneway"
                elif any(idx in [1, '1', 2, '2'] for idx in idx_values):
                    print(colored("=" * 80, "yellow"))
                    print(colored("🎯 POSITION MODE: HEDGE MODE", "yellow", attrs=['bold']))
                    print(colored("=" * 80, "yellow"))
                    print()
                    print("⚠️  Required configuration:")
                    print("   - Use position_idx = 1 for LONG positions")
                    print("   - Use position_idx = 2 for SHORT positions")
                    print("   - Separate stop losses for LONG/SHORT")
                    print()
                    return "hedge"
        
        # Method 2: Direct API check (if available)
        try:
            # Try to get account configuration
            result = await exchange.private_get_v5_account_info()
            print("📋 Account Info:", result)
        except Exception as e:
            print(f"ℹ️  Could not fetch account info: {e}")
        
        print(colored("=" * 80, "cyan"))
        
    except Exception as e:
        print(colored(f"❌ ERROR: {e}", "red", attrs=['bold']))
        import traceback
        traceback.print_exc()
        
    finally:
        if exchange:
            await exchange.close()


if __name__ == "__main__":
    asyncio.run(check_position_mode())
