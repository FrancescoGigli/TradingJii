"""
🤖 Data Fetcher Agent - Main Entry Point

Daemon mode:
- On startup: full refresh (top 100 symbols + candles for all timeframes)
- Every 15 minutes: candles update only
- When refresh signal file detected: full refresh

The bot runs in daemon mode and stays alive continuously.
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path
from termcolor import colored
import ccxt.async_support as ccxt

import config
from core.database_cache import DatabaseCache
from fetcher import full_refresh, fetch_candles_for_symbols, display_download_summary


# Shared path for signal file
SHARED_PATH = os.getenv("SHARED_DATA_PATH", "/app/shared")
REFRESH_SIGNAL_FILE = f"{SHARED_PATH}/refresh_signal.txt"


def print_header():
    """Print startup header"""
    print(colored(f"""
{'='*60}
🔄 DATA FETCHER AGENT - Bybit OHLCV
{'='*60}
⏰ Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📊 Symbols: Top {config.TOP_SYMBOLS_COUNT} by volume
⏱️  Timeframes: {', '.join(config.ENABLED_TIMEFRAMES)}
🕯️ Candles per symbol: {config.CANDLES_LIMIT}
🔁 Update interval: {config.UPDATE_INTERVAL_MINUTES} minutes
💾 Database: {config.SHARED_DATA_PATH}/trading_data.db
{'='*60}
""", "cyan"))


def check_refresh_signal():
    """Check if manual refresh signal exists"""
    if Path(REFRESH_SIGNAL_FILE).exists():
        Path(REFRESH_SIGNAL_FILE).unlink()  # Delete signal file
        return True
    return False


async def run_daemon():
    """Run the daemon that fetches data periodically"""
    print(colored("\n🤖 DAEMON MODE - Bot will stay active and update data automatically", "yellow", attrs=['bold']))
    
    db_cache = DatabaseCache()
    exchange = ccxt.bybit(config.exchange_config)
    
    try:
        print(colored("\n🚀 DAEMON START - Initial data load...", "green", attrs=['bold']))
        
        # Initial full refresh
        stats = await full_refresh(exchange, db_cache)
        display_download_summary(stats)
        db_cache.print_db_stats()
        
        print(colored("\n✅ Initial load complete!", "green", attrs=['bold']))
        print(colored(f"⏰ Next candles update in {config.UPDATE_INTERVAL_MINUTES} minutes", "cyan"))
        print(colored(f"💡 To force list refresh: create file 'refresh_signal.txt' in shared/", "cyan"))
        
        # Main loop - update every 15 minutes
        while True:
            # Wait with signal check
            for _ in range(config.UPDATE_INTERVAL_MINUTES * 60):
                await asyncio.sleep(1)
                
                # Check for manual refresh signal
                if check_refresh_signal():
                    print(colored("\n🔔 Manual refresh signal detected!", "yellow", attrs=['bold']))
                    break
            
            # Check if refresh was requested
            if check_refresh_signal():
                print(colored("\n🔄 Running FULL REFRESH (manually requested)...", "yellow"))
                stats = await full_refresh(exchange, db_cache)
            else:
                # Normal periodic update - only candles
                print(colored(f"\n🔄 Starting periodic update... [{datetime.now().strftime('%H:%M:%S')}]", "cyan"))
                stats = await fetch_candles_for_symbols(exchange, db_cache)
            
            display_download_summary(stats)
            db_cache.print_db_stats()
            
            print(colored(f"\n⏰ Next update in {config.UPDATE_INTERVAL_MINUTES} minutes", "cyan"))
            print(colored(f"💡 To force list refresh: create file 'refresh_signal.txt' in shared/", "cyan"))
            
    except asyncio.CancelledError:
        print(colored("\n⚠️ Daemon stopped", "yellow"))
    except Exception as e:
        print(colored(f"\n❌ Daemon error: {e}", "red"))
        raise
    finally:
        if exchange:
            await exchange.close()


async def main():
    """Main entry point"""
    print_header()
    await run_daemon()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(colored("\n\n👋 Bye!", "cyan"))
        sys.exit(0)
