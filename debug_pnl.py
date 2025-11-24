import asyncio
import os
import sys
import ccxt.async_support as ccxt
from config import API_KEY, API_SECRET

# Hardcoded for debugging purposes, assuming mainnet based on user context or defaulting to False
BYBIT_TESTNET = False 

async def main():
    # Initialize exchange
    exchange = ccxt.bybit({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'options': {
            'defaultType': 'swap',
        }
    })
    
    if BYBIT_TESTNET:
        exchange.set_sandbox_mode(True)
        print("Using Bybit Testnet")
    else:
        print("Using Bybit Mainnet")

    try:
        print("Fetching positions...")
        positions = await exchange.fetch_positions(None, {"limit": 100, "type": "swap"})
        
        print(f"Found {len(positions)} positions.")
        
        active_positions = [p for p in positions if float(p['info']['size']) > 0]
        print(f"Active positions: {len(active_positions)}")
        
        for p in active_positions:
            symbol = p['symbol']
            side = p['side']
            size = p['contracts']
            entry_price = p['entryPrice']
            mark_price = p.get('markPrice')
            unrealized_pnl = p.get('unrealizedPnl')
            initial_margin = p.get('initialMargin')
            info_unrealized_pnl = p['info'].get('unrealizedPnl')
            
            print(f"\nSymbol: {symbol}")
            print(f"Side: {side}")
            print(f"Size: {size}")
            print(f"Entry Price: {entry_price}")
            print(f"Mark Price: {mark_price}")
            print(f"Initial Margin: {initial_margin}")
            print(f"CCXT Unrealized PnL: {unrealized_pnl}")
            print(f"Raw Info Unrealized PnL: {info_unrealized_pnl}")
            
            # Calculate manually
            if entry_price and mark_price:
                if side == 'long':
                    calc_pnl = (float(mark_price) - float(entry_price)) * float(size)
                else:
                    calc_pnl = (float(entry_price) - float(mark_price)) * float(size)
                print(f"Calculated PnL (Mark Price): {calc_pnl}")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
