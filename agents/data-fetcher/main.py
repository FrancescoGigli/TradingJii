"""
🤖 Data Fetcher Agent - Main Entry Point

Daemon mode:
- On startup: uses saved Top 100 list (if exists) and refreshes OHLCV data
- If no saved list: does initial full refresh (top 100 + candles)
- Every 15 minutes: automatic OHLCV data update (keeps existing list)

Manual triggers (via signal files):
- 'refresh_signal.txt' → Refresh OHLCV data only (keeps current Top 100 list)
- 'update_list_signal.txt' → Update Top 100 ranking by volume + refresh all data

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


# Shared path for signal files
SHARED_PATH = os.getenv("SHARED_DATA_PATH", "/app/shared")
REFRESH_SIGNAL_FILE = f"{SHARED_PATH}/refresh_signal.txt"  # Refresh OHLCV data only
UPDATE_LIST_SIGNAL_FILE = f"{SHARED_PATH}/update_list_signal.txt"  # Update top 100 list + refresh data


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
💾 Database: {config.SHARED_DATA_PATH}/data_cache/trading_data.db
{'='*60}
""", "cyan"))


def check_refresh_signal():
    """Check if OHLCV data refresh signal exists (refresh data only, keep existing list)"""
    if Path(REFRESH_SIGNAL_FILE).exists():
        Path(REFRESH_SIGNAL_FILE).unlink()  # Delete signal file
        return True
    return False


def check_update_list_signal():
    """Check if update list signal exists (update top 100 list + refresh all data)"""
    if Path(UPDATE_LIST_SIGNAL_FILE).exists():
        Path(UPDATE_LIST_SIGNAL_FILE).unlink()  # Delete signal file
        return True
    return False


async def run_daemon():
    """Run the daemon that fetches data periodically"""
    print(colored("\n🤖 DAEMON MODE - Bot will stay active and update data automatically", "yellow", attrs=['bold']))
    
    db_cache = DatabaseCache()
    exchange = ccxt.bybit(config.exchange_config)
    
    try:
        # Check if we have saved symbols in DB
        saved_symbols = db_cache.get_top_symbols_list()
        
        if not saved_symbols:
            # No saved list - do initial full refresh (list + data)
            print(colored("\n🚀 DAEMON START - No saved list, doing initial full refresh...", "green", attrs=['bold']))
            stats = await full_refresh(exchange, db_cache)
        else:
            # We have a saved list - just refresh OHLCV data
            print(colored(f"\n🚀 DAEMON START - Found {len(saved_symbols)} saved symbols, refreshing data...", "green", attrs=['bold']))
            stats = await fetch_candles_for_symbols(exchange, db_cache, saved_symbols)
        
        display_download_summary(stats)
        db_cache.print_db_stats()
        
        print(colored("\n✅ Initial load complete!", "green", attrs=['bold']))
        print_next_update_info()
        
        # Main loop - update every 15 minutes
        while True:
            signal_type = None
            
            # Wait with signal check
            for _ in range(config.UPDATE_INTERVAL_MINUTES * 60):
                await asyncio.sleep(1)
                
                # Check for update list signal (priority)
                if check_update_list_signal():
                    signal_type = "UPDATE_LIST"
                    print(colored("\n🔔 Update Top 100 List signal detected!", "yellow", attrs=['bold']))
                    break
                
                # Check for data refresh signal
                if check_refresh_signal():
                    signal_type = "REFRESH_DATA"
                    print(colored("\n🔔 Refresh Data signal detected!", "yellow", attrs=['bold']))
                    break
            
            # Execute based on signal type
            if signal_type == "UPDATE_LIST":
                # Update top 100 list + refresh all data
                print(colored("\n📋 Updating Top 100 List + Refreshing Data...", "magenta", attrs=['bold']))
                stats = await full_refresh(exchange, db_cache)
                
            elif signal_type == "REFRESH_DATA":
                # Only refresh OHLCV data for existing list
                print(colored("\n🔄 Refreshing OHLCV Data (using saved list)...", "cyan", attrs=['bold']))
                stats = await fetch_candles_for_symbols(exchange, db_cache)
                
            else:
                # Normal periodic update - only candles
                print(colored(f"\n🔄 Periodic data update... [{datetime.now().strftime('%H:%M:%S')}]", "cyan"))
                stats = await fetch_candles_for_symbols(exchange, db_cache)
            
            display_download_summary(stats)
            db_cache.print_db_stats()
            print_next_update_info()
            
    except asyncio.CancelledError:
        print(colored("\n⚠️ Daemon stopped", "yellow"))
    except Exception as e:
        print(colored(f"\n❌ Daemon error: {e}", "red"))
        raise
    finally:
        if exchange:
            await exchange.close()


def print_next_update_info():
    """Print info about next update and available signals"""
    print(colored(f"\n⏰ Next automatic update in {config.UPDATE_INTERVAL_MINUTES} minutes", "cyan"))
    print(colored("💡 Manual triggers available:", "cyan"))
    print(colored("   • 'refresh_signal.txt' → Refresh OHLCV data (keeps current list)", "white"))
    print(colored("   • 'update_list_signal.txt' → Update Top 100 ranking + refresh data", "white"))


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
