#!/usr/bin/env python3
"""
🔍 CHECK ACTUAL CLOSE REASON FROM BYBIT

Interroga direttamente Bybit per capire esattamente come è stata chiusa una posizione:
- Controlla Order History
- Identifica tipo di ordine (Market, Stop Loss, Take Profit, Liquidation)
- Mostra timestamp e dettagli esatti

Usage:
    python scripts/check_close_reason.py SYMBOL [--days N]
    
Example:
    python scripts/check_close_reason.py XAUT --days 1
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ccxt.async_support as ccxt
from termcolor import colored
import config


async def check_close_reason(symbol: str, days: int = 1):
    """Check actual close reason from Bybit order history"""
    
    print(colored(f"\n🔍 Investigating closes for {symbol} in last {days} day(s)...\n", "cyan", attrs=['bold']))
    
    # Initialize exchange
    exchange = ccxt.bybit({
        'apiKey': config.BYBIT_API_KEY,
        'secret': config.BYBIT_API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
            'recvWindow': 10000,
        }
    })
    
    try:
        # Format symbol for Bybit
        bybit_symbol = f"{symbol}/USDT:USDT"
        
        # Calculate time range
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        print(colored("📋 Fetching Order History from Bybit...", "white"))
        
        # Fetch order history (includes stop orders)
        orders = await exchange.fetch_orders(
            symbol=bybit_symbol,
            since=start_time,
            params={'category': 'linear'}
        )
        
        if not orders:
            print(colored(f"❌ No orders found for {symbol} in last {days} day(s)", "red"))
            return
        
        print(colored(f"✅ Found {len(orders)} orders\n", "green"))
        
        # Group by position (entry + exit)
        positions = {}
        for order in orders:
            # Skip non-filled orders
            if order['status'] not in ['closed', 'filled']:
                continue
            
            order_id = order['id']
            timestamp = order['timestamp']
            dt = datetime.fromtimestamp(timestamp / 1000)
            
            side = order['side']  # buy or sell
            order_type = order['type']  # market, limit, stop, etc
            price = order['price']
            amount = order['amount']
            filled = order['filled']
            
            # Check if it's a closing order (reduceOnly or opposite side)
            is_close = order.get('reduceOnly', False)
            
            # Get stop order type if available
            stop_order_type = order.get('info', {}).get('stopOrderType', 'N/A')
            trigger_price = order.get('stopPrice')
            
            # Display order
            close_flag = "🔴 CLOSE" if is_close else "🟢 OPEN"
            type_display = f"{order_type.upper()}"
            if trigger_price:
                type_display += f" @ ${trigger_price:.2f}"
            
            print(colored(f"{'─' * 80}", "white"))
            print(colored(f"Time: {dt.strftime('%Y-%m-%d %H:%M:%S')}", "cyan"))
            print(colored(f"Order ID: {order_id}", "white"))
            print(f"{close_flag} {colored(side.upper(), 'green' if side == 'buy' else 'red')} | Type: {colored(type_display, 'yellow')}")
            print(f"Price: ${price:.6f} | Amount: {amount:.4f} | Filled: {filled:.4f}")
            
            # Identify close reason
            if is_close or (side == 'sell' and 'LONG' in str(positions)) or (side == 'buy' and 'SHORT' in str(positions)):
                close_reason = "UNKNOWN"
                
                if 'stop' in order_type.lower():
                    info = order.get('info', {})
                    stop_order_type = info.get('stopOrderType', '')
                    
                    if 'StopLoss' in stop_order_type or 'sl' in order_type.lower():
                        close_reason = "🔴 STOP LOSS HIT"
                    elif 'TakeProfit' in stop_order_type or 'tp' in order_type.lower():
                        close_reason = "🟢 TAKE PROFIT HIT"
                    elif 'Trailing' in stop_order_type:
                        close_reason = "🟢 TRAILING STOP HIT"
                    else:
                        close_reason = f"⚠️ STOP ORDER ({stop_order_type})"
                        
                elif order_type == 'market':
                    close_reason = "⚪ MANUAL CLOSE (Market Order)"
                elif order_type == 'limit':
                    close_reason = "⚪ MANUAL CLOSE (Limit Order)"
                else:
                    close_reason = f"⚠️ {order_type.upper()}"
                
                print(colored(f"\n🎯 CLOSE REASON: {close_reason}", "yellow", attrs=['bold']))
            
            print()
        
        # Also check closed PnL endpoint for summary
        print(colored(f"\n{'═' * 80}", "cyan"))
        print(colored("📊 Checking Closed P&L Summary from Bybit...", "white"))
        
        try:
            closed_pnl_data = await exchange.privateGetV5PositionClosedPnl({
                'category': 'linear',
                'symbol': symbol.replace('/', ''),
                'limit': 5
            })
            
            if closed_pnl_data and 'result' in closed_pnl_data:
                result_list = closed_pnl_data['result'].get('list', [])
                
                if result_list:
                    print(colored(f"✅ Found {len(result_list)} closed position(s)\n", "green"))
                    
                    for idx, pos in enumerate(result_list, 1):
                        close_pnl = float(pos.get('closedPnl', 0))
                        avg_entry = float(pos.get('avgEntryPrice', 0))
                        avg_exit = float(pos.get('avgExitPrice', 0))
                        qty = float(pos.get('qty', 0))
                        side = pos.get('side', 'N/A')
                        
                        close_timestamp = int(pos.get('updatedTime', 0))
                        close_dt = datetime.fromtimestamp(close_timestamp / 1000)
                        
                        print(colored(f"Position #{idx}:", "cyan", attrs=['bold']))
                        print(f"  Close Time: {close_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                        print(f"  Side: {colored(side.upper(), 'green' if side == 'Buy' else 'red')}")
                        print(f"  Qty: {qty:.4f}")
                        print(f"  Entry: ${avg_entry:.6f}")
                        print(f"  Exit: ${avg_exit:.6f}")
                        
                        pnl_color = "green" if close_pnl >= 0 else "red"
                        print(colored(f"  Realized P&L: ${close_pnl:+.2f}", pnl_color, attrs=['bold']))
                        
                        # Check if exit near entry (might indicate SL)
                        price_diff_pct = abs((avg_exit - avg_entry) / avg_entry) * 100
                        if price_diff_pct < 1.0 and close_pnl < 0:
                            print(colored(f"  ⚠️ Small loss + quick close → Likely STOP LOSS HIT", "red"))
                        
                        print()
                        
                        # Show raw data
                        print(colored("  Raw Data:", "white"))
                        print(json.dumps(pos, indent=4, default=str))
                        print()
                else:
                    print(colored("❌ No closed positions found in summary", "yellow"))
        except Exception as e:
            print(colored(f"⚠️ Could not fetch closed PnL summary: {e}", "yellow"))
        
    except Exception as e:
        print(colored(f"\n❌ Error: {e}", "red"))
        import traceback
        traceback.print_exc()
        
    finally:
        await exchange.close()


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Check actual close reason from Bybit')
    parser.add_argument('symbol', help='Symbol to check (e.g., XAUT, BTC)')
    parser.add_argument('--days', type=int, default=1, help='Days to look back (default: 1)')
    
    args = parser.parse_args()
    
    await check_close_reason(args.symbol, args.days)


if __name__ == '__main__':
    asyncio.run(main())
