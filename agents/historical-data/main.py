"""
📊 Historical Data Agent - Main Entry Point

Downloads and maintains 12+ months of historical OHLCV data for ML training.

Features:
- Initial backfill of 12 months + warmup
- Incremental updates every 15 minutes
- Data validation and gap filling
- Progress tracking via database

Usage:
    python main.py              # Run full agent (backfill + update loop)
    python main.py --backfill   # Run backfill only
    python main.py --status     # Show current status
"""

import asyncio
import argparse
import logging
import signal
import sys
import time
from datetime import datetime, timedelta
from typing import List, Optional

from termcolor import colored

import config
from core.database import HistoricalDatabase, BackfillStatus
from core.validation import DataValidator, validate_and_fill_gaps
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


class HistoricalDataAgent:
    """
    Main agent class for managing historical data.
    
    Responsibilities:
    - Initial backfill (12 months + warmup)
    - Incremental updates
    - Data validation
    - Status tracking
    """
    
    def __init__(self):
        self.db = HistoricalDatabase()
        self.validator = DataValidator()
    
    async def initialize_backfill_status(self, symbols: List[str]):
        """Initialize backfill status for all symbols/timeframes"""
        logger.info(f"📋 Initializing backfill status for {len(symbols)} symbols...")
        
        for symbol in symbols:
            for tf in config.HISTORICAL_TIMEFRAMES:
                self.db.init_backfill_status(symbol, tf)
        
        logger.info("✅ Backfill status initialized")
    
    async def run_backfill(
        self, 
        symbols: List[str] = None,
        timeframes: List[str] = None,
        force: bool = False
    ):
        """
        Run backfill for all or specified symbols.
        
        Args:
            symbols: List of symbols (default: from database)
            timeframes: List of timeframes (default: from config)
            force: Force re-download even if complete
        """
        # Get symbols from data-fetcher if not provided
        if symbols is None:
            symbols = self.db.get_symbols_from_data_fetcher()
            if not symbols:
                logger.error("❌ No symbols found. Run data-fetcher first!")
                return
        
        if timeframes is None:
            timeframes = config.HISTORICAL_TIMEFRAMES
        
        # Initialize status
        await self.initialize_backfill_status(symbols)
        
        print(colored("\n" + "="*70, "cyan", attrs=['bold']))
        print(colored("📥 HISTORICAL DATA BACKFILL", "cyan", attrs=['bold']))
        print(colored("="*70, "cyan", attrs=['bold']))
        print(colored(f"  Symbols: {len(symbols)}", "white"))
        print(colored(f"  Timeframes: {', '.join(timeframes)}", "white"))
        print(colored(f"  Target: {config.HISTORICAL_MONTHS} months + {config.WARMUP_CANDLES} warmup", "white"))
        print(colored("="*70, "cyan", attrs=['bold']))
        
        total_start = time.time()
        successful = 0
        failed = 0
        
        async with BybitHistoricalFetcher() as fetcher:
            await fetcher.load_markets()
            
            for tf in timeframes:
                print(colored(f"\n⏰ TIMEFRAME: {tf}", "magenta", attrs=['bold']))
                print(colored("-"*50, "magenta"))
                
                for i, symbol in enumerate(symbols):
                    if shutdown_requested:
                        logger.info("🛑 Shutdown requested, stopping backfill...")
                        return
                    
                    # Check if already complete (unless force)
                    status = self.db.get_backfill_status(symbol, tf)
                    if status and status.status == BackfillStatus.COMPLETE and not force:
                        logger.debug(f"⏭️ {symbol}[{tf}]: Already complete, skipping")
                        continue
                    
                    # Mark as in progress
                    self.db.update_backfill_status(
                        symbol, tf,
                        status=BackfillStatus.IN_PROGRESS
                    )
                    
                    try:
                        print(colored(f"\n[{i+1}/{len(symbols)}] {symbol}", "yellow"))
                        
                        # Download historical data
                        df = await fetcher.fetch_historical_ohlcv(
                            symbol=symbol,
                            timeframe=tf,
                            progress_callback=print_download_progress
                        )
                        
                        if df is None or df.empty:
                            raise Exception("No data received")
                        
                        # Validate and fill gaps
                        df, validation = validate_and_fill_gaps(df, tf)
                        
                        # Calculate technical indicators
                        print(colored(f"   📊 Calculating {len(INDICATOR_COLUMNS)} indicators...", "cyan"))
                        df = calculate_all_indicators(df)
                        
                        # Save to database (with indicators)
                        saved = self.db.save_candles(symbol, tf, df)
                        
                        # Calculate warmup/training split
                        warmup_end = df.index.min() + timedelta(
                            minutes=config.WARMUP_CANDLES * (15 if tf == '15m' else 60)
                        )
                        warmup_candles = len(df[df.index < warmup_end])
                        training_candles = len(df) - warmup_candles
                        
                        # Calculate training_start safely (avoid index out of bounds)
                        if warmup_candles >= len(df):
                            training_start_ts = df.index.max().to_pydatetime()
                        elif warmup_end in df.index:
                            training_start_ts = warmup_end.to_pydatetime()
                        else:
                            training_start_ts = df.index[min(warmup_candles, len(df)-1)].to_pydatetime()
                        
                        # Update status
                        self.db.update_backfill_status(
                            symbol, tf,
                            status=BackfillStatus.COMPLETE,
                            oldest_timestamp=df.index.min().to_pydatetime(),
                            warmup_start=df.index.min().to_pydatetime(),
                            training_start=training_start_ts,
                            newest_timestamp=df.index.max().to_pydatetime(),
                            total_candles=len(df),
                            warmup_candles=warmup_candles,
                            training_candles=training_candles,
                            completeness_pct=validation.completeness_pct,
                            gap_count=validation.gap_count,
                            error_message=None
                        )
                        
                        print(colored(f"   ✅ Saved {saved:,} candles ({validation.completeness_pct}% complete)", "green"))
                        successful += 1
                        
                    except Exception as e:
                        logger.error(f"❌ {symbol}[{tf}]: {e}")
                        self.db.update_backfill_status(
                            symbol, tf,
                            status=BackfillStatus.ERROR,
                            error_message=str(e)
                        )
                        failed += 1
        
        total_duration = time.time() - total_start
        
        print(colored("\n" + "="*70, "cyan", attrs=['bold']))
        print(colored("📊 BACKFILL COMPLETE", "cyan", attrs=['bold']))
        print(colored("="*70, "cyan", attrs=['bold']))
        print(colored(f"  ✅ Successful: {successful}", "green"))
        print(colored(f"  ❌ Failed: {failed}", "red" if failed > 0 else "white"))
        print(colored(f"  ⏱️ Duration: {total_duration/60:.1f} minutes", "white"))
        print(colored("="*70, "cyan", attrs=['bold']))
        
        # Print database stats
        self.db.print_stats()
    
    async def run_incremental_update(self, symbols: List[str] = None):
        """
        Run incremental update for all symbols.
        Only downloads new candles since last update.
        """
        if symbols is None:
            symbols = self.db.get_symbols_from_data_fetcher()
            if not symbols:
                logger.warning("No symbols found for incremental update")
                return
        
        logger.info(f"🔄 Starting incremental update for {len(symbols)} symbols...")
        
        updated = 0
        errors = 0
        
        async with BybitHistoricalFetcher() as fetcher:
            await fetcher.load_markets()
            
            for tf in config.HISTORICAL_TIMEFRAMES:
                for symbol in symbols:
                    if shutdown_requested:
                        return
                    
                    try:
                        # Get last timestamp
                        last_ts = self.db.get_newest_timestamp(symbol, tf)
                        
                        if last_ts is None:
                            # No data yet, skip (needs backfill)
                            continue
                        
                        # Fetch only new candles
                        df = await fetcher.fetch_incremental(symbol, tf, last_ts)
                        
                        if df is not None and len(df) > 0:
                            # Save new candles
                            saved = self.db.save_candles(symbol, tf, df)
                            
                            if saved > 0:
                                # Update status
                                new_count = self.db.get_candle_count(symbol, tf)
                                newest = self.db.get_newest_timestamp(symbol, tf)
                                
                                self.db.update_backfill_status(
                                    symbol, tf,
                                    newest_timestamp=newest,
                                    total_candles=new_count
                                )
                                
                                updated += 1
                                logger.debug(f"  {symbol}[{tf}]: +{saved} candles")
                        
                    except Exception as e:
                        logger.error(f"Error updating {symbol}[{tf}]: {e}")
                        errors += 1
        
        logger.info(f"✅ Incremental update complete: {updated} updated, {errors} errors")
    
    async def run_update_loop(self):
        """
        Run continuous update loop.
        Checks for updates every UPDATE_INTERVAL_MINUTES.
        """
        logger.info(f"🔄 Starting update loop (interval: {config.UPDATE_INTERVAL_MINUTES}m)")
        
        while not shutdown_requested:
            try:
                await self.run_incremental_update()
            except Exception as e:
                logger.error(f"Update loop error: {e}")
            
            # Wait for next update
            for _ in range(config.UPDATE_INTERVAL_MINUTES * 60):
                if shutdown_requested:
                    break
                await asyncio.sleep(1)
    
    def print_status(self):
        """Print current backfill status"""
        print(colored("\n" + "="*70, "cyan", attrs=['bold']))
        print(colored("📊 HISTORICAL DATA STATUS", "cyan", attrs=['bold']))
        print(colored("="*70, "cyan", attrs=['bold']))
        
        statuses = self.db.get_all_backfill_status()
        
        if not statuses:
            print(colored("  No backfill status found. Run backfill first.", "yellow"))
        else:
            # Group by status
            by_status = {}
            for s in statuses:
                status_name = s.status.value
                if status_name not in by_status:
                    by_status[status_name] = []
                by_status[status_name].append(s)
            
            for status_name, items in by_status.items():
                icon = "✅" if status_name == "COMPLETE" else "🔄" if status_name == "IN_PROGRESS" else "⏳" if status_name == "PENDING" else "❌"
                print(colored(f"\n  {icon} {status_name}: {len(items)} symbol/timeframe pairs", "white", attrs=['bold']))
                
                if status_name == "COMPLETE":
                    # Show sample
                    for item in items[:3]:
                        print(colored(f"     {item.symbol}[{item.timeframe}]: {item.total_candles:,} candles, {item.completeness_pct}%", "green"))
                    if len(items) > 3:
                        print(colored(f"     ... and {len(items)-3} more", "white"))
                
                elif status_name == "ERROR":
                    for item in items[:5]:
                        print(colored(f"     {item.symbol}[{item.timeframe}]: {item.error_message}", "red"))
        
        print(colored("\n" + "="*70, "cyan", attrs=['bold']))
        
        # Print database stats
        self.db.print_stats()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Historical Data Agent")
    parser.add_argument("--backfill", action="store_true", help="Run backfill only")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--force", action="store_true", help="Force re-download even if complete")
    parser.add_argument("--symbol", type=str, help="Process single symbol only")
    args = parser.parse_args()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Print config
    config.print_config()
    
    agent = HistoricalDataAgent()
    
    if args.status:
        agent.print_status()
        return
    
    # Prepare symbols
    symbols = None
    if args.symbol:
        symbols = [args.symbol]
    
    if args.backfill:
        # Run backfill only
        await agent.run_backfill(symbols=symbols, force=args.force)
    else:
        # Full mode: backfill (if needed) + update loop
        
        # First, run backfill for any pending/incomplete
        pending = agent.db.get_pending_backfills()
        if pending or args.force:
            await agent.run_backfill(symbols=symbols, force=args.force)
        else:
            logger.info("✅ All backfills complete, starting update loop...")
        
        # Then run update loop
        if not shutdown_requested:
            await agent.run_update_loop()


if __name__ == "__main__":
    print(colored("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     📊 HISTORICAL DATA AGENT                                 ║
║     Downloads and maintains ML training data                 ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """, "cyan", attrs=['bold']))
    
    asyncio.run(main())
