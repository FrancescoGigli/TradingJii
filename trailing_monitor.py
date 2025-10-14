#!/usr/bin/env python3
"""
🎪 TRAILING STOP MONITOR - Standalone

Script che monitora e aggiorna i trailing stop OGNI 60 SECONDI
in parallelo al bot principale.

USO:
1. Avvia il bot principale (python main.py)
2. Avvia questo script in un terminale separato (python trailing_monitor.py)

FUNZIONI:
- Controlla trailing stop ogni 60s
- Auto-correzione SL ogni 5 minuti
- Indipendente dal ciclo principale
"""

import asyncio
import logging
import time
from datetime import datetime
from termcolor import colored
import ccxt.async_support as ccxt

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

async def initialize_exchange():
    """Initialize Bybit exchange connection"""
    try:
        from config import BYBIT_API_KEY, BYBIT_API_SECRET
        
        exchange = ccxt.bybit({
            'apiKey': BYBIT_API_KEY,
            'secret': BYBIT_API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'recvWindow': 60000,
            }
        })
        
        await exchange.load_markets()
        logging.info(colored("✅ Bybit exchange connected", "green"))
        return exchange
        
    except Exception as e:
        logging.error(colored(f"❌ Failed to initialize exchange: {e}", "red"))
        raise


async def trailing_monitor_loop(exchange):
    """Main trailing monitor loop"""
    try:
        from core.thread_safe_position_manager import global_thread_safe_position_manager
        from core.enhanced_logging_system import enhanced_logger
        
        position_manager = global_thread_safe_position_manager
        
        logging.info(colored("🎪 TRAILING MONITOR STARTED", "magenta", attrs=['bold']))
        logging.info(colored("⏰ Checking every 60 seconds...", "cyan"))
        
        last_autofix_time = 0
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                current_time = time.time()
                
                # 1. UPDATE TRAILING STOPS (every 60s)
                logging.info(colored(f"\n{'='*80}", "cyan"))
                logging.info(colored(f"🎪 TRAILING CYCLE #{cycle_count} - {datetime.now().strftime('%H:%M:%S')}", "magenta", attrs=['bold']))
                logging.info(colored(f"{'='*80}\n", "cyan"))
                
                updates_count = await position_manager.update_trailing_stops(exchange)
                
                if updates_count > 0:
                    enhanced_logger.display_table(
                        f"🎪 Trailing: {updates_count} positions updated", 
                        "magenta"
                    )
                else:
                    logging.info(colored("ℹ️  No trailing updates needed", "cyan"))
                
                # 2. AUTO-FIX SL (every 5 minutes = 5 cycles)
                time_since_autofix = current_time - last_autofix_time
                if time_since_autofix >= 300:  # 5 minutes
                    logging.info(colored("\n🔧 AUTO-FIX: Checking stop losses...", "yellow"))
                    fixed_count = await position_manager.check_and_fix_stop_losses(exchange)
                    
                    if fixed_count > 0:
                        enhanced_logger.display_table(
                            f"🔧 Auto-Fix: Corrected {fixed_count} stop losses", 
                            "green"
                        )
                    else:
                        logging.info(colored("✅ All stop losses correct", "green"))
                    
                    last_autofix_time = current_time
                
                # 3. Wait 60 seconds
                logging.info(colored(f"\n⏰ Next check in 60 seconds...\n", "cyan"))
                await asyncio.sleep(60)
                
            except KeyboardInterrupt:
                logging.info(colored("\n⚠️  Trailing monitor stopped by user", "yellow"))
                break
            except Exception as cycle_error:
                logging.error(colored(f"❌ Error in trailing cycle: {cycle_error}", "red"))
                await asyncio.sleep(60)  # Continue after error
        
    except Exception as e:
        logging.error(colored(f"❌ Fatal error in trailing monitor: {e}", "red"))
        raise


async def main():
    """Main entry point"""
    exchange = None
    try:
        # Initialize
        exchange = await initialize_exchange()
        
        # Display info
        print(colored("\n" + "="*80, "magenta"))
        print(colored("🎪 TRAILING STOP MONITOR - STANDALONE", "magenta", attrs=['bold']))
        print(colored("="*80, "magenta"))
        print(colored("\n📋 CONFIGURATION:", "cyan"))
        print(colored("   ⏰ Update Interval: 60 seconds", "white"))
        print(colored("   🔧 Auto-Fix Interval: 5 minutes", "white"))
        print(colored("   🎪 Trailing Trigger: +1% profit", "white"))
        print(colored("   📏 Trailing Distance: -8% from current", "white"))
        print(colored("\n⚡ STATUS: ACTIVE\n", "green", attrs=['bold']))
        print(colored("="*80 + "\n", "magenta"))
        
        # Run monitor
        await trailing_monitor_loop(exchange)
        
    except KeyboardInterrupt:
        logging.info(colored("\n👋 Shutting down gracefully...", "yellow"))
    except Exception as e:
        logging.error(colored(f"\n❌ Fatal error: {e}", "red"))
    finally:
        if exchange:
            await exchange.close()
            logging.info(colored("✅ Exchange connection closed", "green"))


if __name__ == "__main__":
    asyncio.run(main())
