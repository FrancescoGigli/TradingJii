"""
📊 Training Data Agent - Main Entry Point

Downloads OHLCV + indicators for ML training with:
- Date alignment between 15m and 1h timeframes
- No NULL values (warmup candles are fetched but discarded)
- Manual trigger from frontend (no auto-update)

Usage:
    python main.py              # Wait for trigger file
    python main.py --status     # Show current status
"""

import asyncio
import argparse
import logging
import signal
import sys
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from termcolor import colored

import config
from core.database import TrainingDatabase, BackfillStatus, get_aligned_date_range, WARMUP_CANDLES
from core.indicators import calculate_all_indicators, INDICATOR_COLUMNS
from fetcher.bybit_historical import BybitHistoricalFetcher, print_download_progress

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global shutdown_requested
    logger.info("🛑 Shutdown requested...")
    shutdown_requested = True


# Target number of successful downloads per timeframe
TARGET_SUCCESSFUL_DOWNLOADS = 100


class TrainingDataAgent:
    """
    Agent for downloading ML training data.
    
    Features:
    - Downloads OHLCV + 16 technical indicators
    - Aligns dates between 15m and 1h timeframes  
    - Discards warmup candles (no NULL values in final data)
    - Stops at TARGET_SUCCESSFUL_DOWNLOADS (100) per timeframe
    - Skips coins without historical data (SKIPPED status, not ERROR)
    """
    
    def __init__(self):
        self.db = TrainingDatabase()
    
    async def download_training_data(
        self, 
        symbols: List[str],
        timeframes: List[str],
        start_date: datetime,
        end_date: datetime
    ):
        """
        Download training data for specified symbols and date range.
        
        Args:
            symbols: List of symbols to download
            timeframes: List of timeframes ('15m', '1h')
            start_date: Start date
            end_date: End date
        """
        # Align dates to hour boundaries
        aligned_start, aligned_end = get_aligned_date_range(start_date, end_date)
        
        # Calculate warmup start (200 candles before aligned_start)
        # Use 1h timeframe for warmup calculation (200 hours = ~8 days)
        warmup_start = aligned_start - timedelta(hours=WARMUP_CANDLES)
        
        print(colored("\n" + "="*70, "cyan", attrs=['bold']))
        print(colored("📥 TRAINING DATA DOWNLOAD", "cyan", attrs=['bold']))
        print(colored("="*70, "cyan", attrs=['bold']))
        print(colored(f"  Symbols: {len(symbols)}", "white"))
        print(colored(f"  Timeframes: {', '.join(timeframes)}", "white"))
        print(colored(f"  Requested range: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}", "white"))
        print(colored(f"  Aligned range: {aligned_start.strftime('%Y-%m-%d %H:%M')} → {aligned_end.strftime('%Y-%m-%d %H:%M')}", "green"))
        print(colored(f"  Warmup start: {warmup_start.strftime('%Y-%m-%d %H:%M')} ({WARMUP_CANDLES} extra candles)", "yellow"))
        print(colored("="*70, "cyan", attrs=['bold']))
        
        total_start = time.time()
        successful = 0
        failed = 0
        total_candles_saved = 0
        
        # Initialize backfill_status for ALL symbols and timeframes at the start
        print(colored("\n📋 Initializing backfill status for all symbols...", "cyan"))
        for tf in timeframes:
            for symbol in symbols:
                self.db.init_backfill_status(symbol, tf)
        print(colored(f"   ✅ Initialized {len(symbols) * len(timeframes)} records", "green"))
        
        async with BybitHistoricalFetcher() as fetcher:
            await fetcher.load_markets()
            
            for tf in timeframes:
                print(colored(f"\n⏰ TIMEFRAME: {tf}", "magenta", attrs=['bold']))
                print(colored("-"*50, "magenta"))
                
                # Calculate warmup for this timeframe
                if tf == '15m':
                    # 200 candles × 15 min = 3000 min = 50 hours
                    tf_warmup_start = aligned_start - timedelta(minutes=WARMUP_CANDLES * 15)
                else:
                    # 200 candles × 60 min = 12000 min = 200 hours
                    tf_warmup_start = warmup_start
                
                # Track successful downloads for this timeframe
                tf_successful = 0
                tf_skipped = 0
                
                for i, symbol in enumerate(symbols):
                    if shutdown_requested:
                        logger.info("🛑 Shutdown requested, stopping download...")
                        return
                    
                    # Stop if we reached TARGET (100 successful downloads)
                    if tf_successful >= TARGET_SUCCESSFUL_DOWNLOADS:
                        print(colored(f"\n✅ Reached {TARGET_SUCCESSFUL_DOWNLOADS} successful downloads for {tf}. Moving to next timeframe.", "green", attrs=['bold']))
                        
                        # Mark remaining symbols as SKIPPED (target reached)
                        remaining_symbols = symbols[i:]
                        for remaining_symbol in remaining_symbols:
                            self.db.update_backfill_status(
                                symbol=remaining_symbol,
                                timeframe=tf,
                                status=BackfillStatus.SKIPPED,
                                error_message="Target 100 reached - not processed"
                            )
                        print(colored(f"   ⏭️ Marked {len(remaining_symbols)} remaining symbols as SKIPPED", "yellow"))
                        break
                    
                    # Initialize backfill status
                    self.db.init_backfill_status(symbol, tf)
                    
                    # Update status to IN_PROGRESS
                    self.db.update_backfill_status(
                        symbol=symbol,
                        timeframe=tf,
                        status=BackfillStatus.IN_PROGRESS
                    )
                    
                    try:
                        print(colored(f"\n[{i+1}/{len(symbols)}] {symbol} (success: {tf_successful}/{TARGET_SUCCESSFUL_DOWNLOADS})", "yellow"))
                        
                        # Download with warmup (extra candles before aligned_start)
                        df = await fetcher.fetch_historical_ohlcv(
                            symbol=symbol,
                            timeframe=tf,
                            start_date=tf_warmup_start,
                            end_date=aligned_end,
                            progress_callback=print_download_progress
                        )
                        
                        if df is None or df.empty:
                            raise Exception("No data received")
                        
                        print(colored(f"   📊 Downloaded {len(df):,} candles (incl. warmup)", "cyan"))
                        
                        # Calculate technical indicators on FULL data (including warmup)
                        print(colored(f"   📐 Calculating {len(INDICATOR_COLUMNS)} indicators...", "cyan"))
                        df = calculate_all_indicators(df)
                        
                        # Trim to aligned range (discard warmup - they have NULL indicators anyway)
                        df_aligned = df[df.index >= aligned_start].copy()
                        df_aligned = df_aligned[df_aligned.index <= aligned_end].copy()
                        
                        # If no data in aligned range (coin listed after start_date), use available data
                        if df_aligned.empty:
                            # Use all data after warmup period (first ~200 candles may have NULL indicators)
                            # Find the first row without NULL indicators
                            indicator_cols = ['sma_20', 'sma_50', 'ema_12', 'ema_26', 'bb_upper', 'rsi', 'macd', 'atr']
                            existing_cols = [c for c in indicator_cols if c in df.columns]
                            
                            if existing_cols:
                                df_valid = df.dropna(subset=existing_cols)
                            else:
                                df_valid = df.copy()
                            
                            # Filter to end date only
                            df_aligned = df_valid[df_valid.index <= aligned_end].copy()
                            
                            if df_aligned.empty:
                                raise Exception("No valid data available (coin may not be listed yet)")
                            
                            actual_start = df_aligned.index.min()
                            print(colored(f"   ⚠️ Coin listed after {aligned_start.strftime('%Y-%m-%d')}, using data from {actual_start.strftime('%Y-%m-%d')}", "yellow"))
                        
                        # Clear old data for this symbol/timeframe
                        self.db.clear_training_data(symbol, tf)
                        
                        # Save to database (will skip rows with NULL indicators)
                        saved = self.db.save_training_data(symbol, tf, df_aligned)
                        
                        print(colored(f"   ✅ Saved {saved:,} candles (no NULL values)", "green"))
                        
                        # Update backfill status to COMPLETE
                        self.db.update_backfill_status(
                            symbol=symbol,
                            timeframe=tf,
                            status=BackfillStatus.COMPLETE,
                            oldest_timestamp=df_aligned.index.min(),
                            newest_timestamp=df_aligned.index.max(),
                            total_candles=saved,
                            training_candles=saved,
                            completeness_pct=100.0
                        )
                        
                        successful += 1
                        tf_successful += 1  # Track per-timeframe success
                        total_candles_saved += saved
                        
                    except Exception as e:
                        error_msg = str(e)
                        
                        # Determine if this is a "no data" issue (SKIPPED) or actual error (ERROR)
                        no_data_keywords = ["No valid data", "No data received", "may not be listed"]
                        is_no_data = any(kw.lower() in error_msg.lower() for kw in no_data_keywords)
                        
                        if is_no_data:
                            # SKIPPED - Coin doesn't have historical data (not an error)
                            print(colored(f"   ⏭️ {symbol}[{tf}]: Skipped (no historical data)", "yellow"))
                            self.db.update_backfill_status(
                                symbol=symbol,
                                timeframe=tf,
                                status=BackfillStatus.SKIPPED,
                                error_message=error_msg[:200]
                            )
                            # Remove from top_symbols to clean up dashboard
                            self.db.remove_from_top_symbols(symbol)
                            tf_skipped += 1
                        else:
                            # ERROR - Actual technical error
                            logger.error(f"❌ {symbol}[{tf}]: {error_msg}")
                            self.db.update_backfill_status(
                                symbol=symbol,
                                timeframe=tf,
                                status=BackfillStatus.ERROR,
                                error_message=error_msg[:200]
                            )
                            failed += 1
        
        total_duration = time.time() - total_start
        
        print(colored("\n" + "="*70, "cyan", attrs=['bold']))
        print(colored("📊 DOWNLOAD COMPLETE", "cyan", attrs=['bold']))
        print(colored("="*70, "cyan", attrs=['bold']))
        print(colored(f"  ✅ Successful: {successful}", "green"))
        print(colored(f"  ❌ Failed: {failed}", "red" if failed > 0 else "white"))
        print(colored(f"  🕯️ Total candles saved: {total_candles_saved:,}", "white"))
        print(colored(f"  ⏱️ Duration: {total_duration/60:.1f} minutes", "white"))
        print(colored("="*70, "cyan", attrs=['bold']))
        
        # Print database stats
        self.db.print_stats()
    
    def print_status(self):
        """Print current data status"""
        print(colored("\n" + "="*70, "cyan", attrs=['bold']))
        print(colored("📊 TRAINING DATA STATUS", "cyan", attrs=['bold']))
        print(colored("="*70, "cyan", attrs=['bold']))
        
        symbol_stats = self.db.get_symbol_stats()
        
        if not symbol_stats:
            print(colored("  No training data found. Run download first.", "yellow"))
        else:
            # Group by timeframe
            by_tf = {}
            for s in symbol_stats:
                tf = s['timeframe']
                if tf not in by_tf:
                    by_tf[tf] = []
                by_tf[tf].append(s)
            
            for tf, items in by_tf.items():
                print(colored(f"\n  ⏰ {tf}: {len(items)} symbols", "white", attrs=['bold']))
                
                # Show date range for first symbol
                if items:
                    first = items[0]
                    print(colored(f"     Date range: {first['start_date'][:10]} → {first['end_date'][:10]}", "green"))
                    
                    total_candles = sum(i['candles'] for i in items)
                    print(colored(f"     Total candles: {total_candles:,}", "white"))
        
        print(colored("\n" + "="*70, "cyan", attrs=['bold']))
        
        # Print database stats
        self.db.print_stats()


def wait_for_trigger_file() -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Wait for trigger file from frontend.
    
    Returns:
        Tuple of (found, start_date, end_date)
    """
    trigger_path = Path(config.TRIGGER_FILE_PATH)
    
    logger.info(f"⏳ Waiting for trigger file: {trigger_path}")
    logger.info("   (Click 'Start Download' in frontend to begin)")
    
    while not shutdown_requested:
        if trigger_path.exists():
            logger.info(f"✅ Trigger file found! Reading configuration...")
            
            start_date = None
            end_date = None
            
            try:
                content = trigger_path.read_text()
                trigger_data = json.loads(content)
                start_date = trigger_data.get('start_date')
                end_date = trigger_data.get('end_date')
                logger.info(f"   📅 Date range: {start_date} → {end_date}")
            except Exception as e:
                logger.warning(f"Could not parse trigger file: {e}")
            
            # Delete trigger file after reading
            try:
                trigger_path.unlink()
            except:
                pass
            
            return True, start_date, end_date
        
        time.sleep(2)  # Check every 2 seconds
    
    return False, None, None


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Training Data Agent")
    parser.add_argument("--status", action="store_true", help="Show current status")
    args = parser.parse_args()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Print config
    config.print_config()
    
    agent = TrainingDataAgent()
    
    if args.status:
        agent.print_status()
        return
    
    # Main loop: wait for trigger file
    while not shutdown_requested:
        logger.info("⏳ Waiting for download trigger from frontend...")
        
        found, start_date, end_date = wait_for_trigger_file()
        
        if not found:
            break  # Shutdown requested
        
        if not start_date or not end_date:
            logger.error("❌ start_date and end_date are required!")
            continue
        
        # Parse dates
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except Exception as e:
            logger.error(f"❌ Invalid date format: {e}")
            continue
        
        # Get symbols from data-fetcher
        symbols = agent.db.get_symbols_from_data_fetcher()
        if not symbols:
            logger.error("❌ No symbols found. Run data-fetcher first!")
            continue
        
        # Get timeframes
        timeframes = config.HISTORICAL_TIMEFRAMES
        
        # Run download
        logger.info(f"🚀 Starting download: {start_date} → {end_date}")
        await agent.download_training_data(
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_dt,
            end_date=end_dt
        )
        
        logger.info("📦 Download complete. Waiting for next trigger...")


if __name__ == "__main__":
    print(colored("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     📊 TRAINING DATA AGENT                                   ║
║     Downloads ML training data (OHLCV + indicators)          ║
║                                                              ║
║     Features:                                                ║
║     • Date aligned between 15m and 1h                        ║
║     • No NULL values (warmup discarded)                      ║
║     • Manual trigger from frontend                           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """, "cyan", attrs=['bold']))
    
    asyncio.run(main())
