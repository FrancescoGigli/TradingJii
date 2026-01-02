"""
📥 Fetcher Module - Download OHLCV from Bybit

Data Fetcher Agent - Docker Container
Downloads OHLCV data and saves it to the shared SQLite database.
"""

import asyncio
import logging
import pandas as pd
from datetime import datetime
from asyncio import Semaphore
from termcolor import colored
from typing import List, Dict, Optional, Tuple

import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class CryptoDataFetcher:
    """
    Main class for downloading crypto data from Bybit.
    
    Usage:
        async with CryptoDataFetcher() as fetcher:
            symbols = await fetcher.fetch_and_save_top_symbols(db_cache, n=100)
            data = await fetcher.download_symbols(symbols, '15m')
    """
    
    def __init__(self, exchange=None):
        self._exchange = exchange
        self._own_exchange = False
        self.markets = None
        self.downloaded_symbols = []
    
    async def __aenter__(self):
        if self._exchange is None:
            import ccxt.async_support as ccxt
            self._exchange = ccxt.bybit(config.exchange_config)
            self._own_exchange = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._own_exchange and self._exchange:
            await self._exchange.close()
    
    @property
    def exchange(self):
        return self._exchange
    
    async def load_markets(self) -> Dict:
        if self.markets is None:
            self.markets = await self._exchange.load_markets()
        return self.markets
    
    async def get_usdt_perpetual_symbols(self) -> List[str]:
        """Get all USDT perpetual symbols, excluding options"""
        import re
        markets = await self.load_markets()
        
        # Pattern to detect options: contains date pattern like -260102- or -251226-
        option_pattern = re.compile(r'-\d{6}-')
        
        symbols = []
        for symbol in markets.keys():
            if '/USDT:USDT' not in symbol:
                continue
            if not markets[symbol].get('active', False):
                continue
            
            # Get base symbol (before /USDT)
            base = symbol.split('/')[0]
            
            # Exclude options (e.g.: BTC-251226-90000-C, ETH-260102-1000-P)
            if '-' in base:
                continue
            
            # Double check: exclude if matches option pattern in full symbol
            if option_pattern.search(symbol):
                continue
                
            symbols.append(symbol)
        
        return symbols
    
    async def get_ticker_volume(self, symbol: str) -> tuple:
        """Fetch 24h volume for a symbol"""
        try:
            ticker = await self._exchange.fetch_ticker(symbol)
            return symbol, ticker.get('quoteVolume', 0)
        except Exception as e:
            logging.debug(f"Ticker error {symbol}: {e}")
            return symbol, None
    
    async def fetch_top_symbols_with_volume(self, n: int = None, symbols: List[str] = None) -> List[Tuple[str, float]]:
        """
        Fetch top N symbols by volume with their volumes.
        
        Returns:
            List of tuples (symbol, volume_24h) sorted by volume descending
        """
        if n is None:
            n = config.TOP_SYMBOLS_COUNT
        
        if symbols is None:
            symbols = await self.get_usdt_perpetual_symbols()
        
        print(colored(f"\n📊 Analyzing volumes for {len(symbols)} symbols...", "cyan"))
        
        semaphore = Semaphore(20)
        
        async def fetch_with_semaphore(symbol):
            async with semaphore:
                return await self.get_ticker_volume(symbol)
        
        tasks = [fetch_with_semaphore(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        symbol_volumes = []
        for result in results:
            if isinstance(result, tuple) and result[1] is not None:
                symbol_volumes.append(result)
        
        # Sort by volume descending
        symbol_volumes.sort(key=lambda x: x[1], reverse=True)
        
        # Take top N
        top_symbols = symbol_volumes[:n]
        
        print(colored(f"✅ Top {len(top_symbols)} symbols by volume:", "green"))
        self._print_symbols_table(top_symbols)
        
        return top_symbols
    
    async def fetch_and_save_top_symbols(self, db_cache, n: int = None) -> List[str]:
        """
        Fetch top N symbols and save them to database.
        
        Args:
            db_cache: DatabaseCache instance
            n: Number of symbols (default: config.TOP_SYMBOLS_COUNT)
            
        Returns:
            List of symbol names
        """
        top_symbols_with_volume = await self.fetch_top_symbols_with_volume(n)
        
        # Save to database
        db_cache.save_top_symbols(top_symbols_with_volume)
        
        # Return only symbols
        return [symbol for symbol, _ in top_symbols_with_volume]
    
    def _print_symbols_table(self, volumes: List[Tuple[str, float]]):
        """Print formatted table of symbols with volume"""
        print(colored("-" * 50, "cyan"))
        print(colored(f"{'#':<4} {'Symbol':<20} {'Volume 24h':>20}", "white", attrs=['bold']))
        print(colored("-" * 50, "cyan"))
        
        for i, (symbol, vol) in enumerate(volumes, 1):
            symbol_short = symbol.replace('/USDT:USDT', '')
            vol_str = f"${vol/1e9:.2f}B" if vol >= 1e9 else f"${vol/1e6:.1f}M" if vol >= 1e6 else f"${vol/1e3:.1f}K"
            print(f"{i:<4} {symbol_short:<20} {vol_str:>20}")
        
        print(colored("-" * 50, "cyan"))
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> Optional[pd.DataFrame]:
        """Download OHLCV candles for a symbol"""
        try:
            ohlcv = await self._exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=min(limit, 1000))
            
            if not ohlcv:
                return None
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            
            return df
            
        except Exception as e:
            logging.error(f"Download error {symbol}[{timeframe}]: {e}")
            return None
    
    async def download_symbols(
        self, 
        symbols: List[str], 
        timeframe: str, 
        limit: int = 200,
        max_concurrent: int = 15
    ) -> Dict[str, pd.DataFrame]:
        """Download candles for a list of symbols"""
        semaphore = Semaphore(max_concurrent)
        results = {}
        
        async def fetch_single(symbol):
            async with semaphore:
                await asyncio.sleep(0.05)
                df = await self.fetch_ohlcv(symbol, timeframe, limit)
                return symbol, df
        
        print(colored(f"\n⬇️  Downloading {len(symbols)} symbols [{timeframe}]...", "yellow"))
        
        tasks = [fetch_single(s) for s in symbols]
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        for result in completed:
            if isinstance(result, tuple) and result[1] is not None:
                results[result[0]] = result[1]
                self.downloaded_symbols.append(result[0])
                success_count += 1
        
        print(colored(f"✅ Downloaded {success_count}/{len(symbols)} symbols successfully", "green"))
        
        return results
    
    def get_downloaded_symbols(self) -> List[str]:
        return list(set(self.downloaded_symbols))
    
    def print_downloaded_summary(self):
        """Print summary of downloaded symbols"""
        symbols = self.get_downloaded_symbols()
        if not symbols:
            print(colored("⚠️ No symbols downloaded", "yellow"))
            return
        
        print(colored(f"\n📋 DOWNLOADED SYMBOLS ({len(symbols)}):", "cyan", attrs=['bold']))
        print(colored("-" * 60, "cyan"))
        
        cols = 4
        for i in range(0, len(symbols), cols):
            row = symbols[i:i+cols]
            row_str = "  ".join(s.replace('/USDT:USDT', '').ljust(15) for s in row)
            print(row_str)
        
        print(colored("-" * 60, "cyan"))


async def fetch_top_symbols_and_save(exchange, db_cache) -> List[str]:
    """
    Fetch top 100 symbols with volumes and save to database.
    Called at startup and when manually requested.
    
    Returns:
        List of downloaded symbols
    """
    async with CryptoDataFetcher(exchange) as fetcher:
        print(colored("\n🔄 Loading Bybit markets...", "cyan"))
        await fetcher.load_markets()
        
        usdt_symbols = await fetcher.get_usdt_perpetual_symbols()
        print(colored(f"📈 Found {len(usdt_symbols)} USDT perpetual pairs", "cyan"))
        
        # Fetch and save top symbols
        symbols = await fetcher.fetch_and_save_top_symbols(db_cache, config.TOP_SYMBOLS_COUNT)
        
        return symbols


async def fetch_candles_for_symbols(exchange, db_cache, symbols: List[str] = None, timeframes: List[str] = None):
    """
    Download candles for specified symbols (or those saved in database).
    Called periodically every 15 minutes.
    
    Args:
        exchange: ccxt exchange instance
        db_cache: DatabaseCache instance
        symbols: Symbol list (if None, uses database symbols)
        timeframes: Timeframe list (if None, uses config.ENABLED_TIMEFRAMES)
    """
    import time
    start_time = time.time()
    
    stats = {
        'symbols_processed': 0,
        'candles_saved': 0,
        'errors': 0,
        'downloaded_symbols': []
    }
    
    # Set status to UPDATING
    db_cache.set_status_updating()
    
    async with CryptoDataFetcher(exchange) as fetcher:
        await fetcher.load_markets()
        
        # If not specified, use symbols from database
        if symbols is None:
            symbols = db_cache.get_top_symbols_list()
            if not symbols:
                print(colored("⚠️ No symbols found in database. Run top symbols fetch first.", "yellow"))
                return stats
        
        if timeframes is None:
            timeframes = config.ENABLED_TIMEFRAMES
        
        print(colored(f"\n📊 Updating candles for {len(symbols)} symbols", "cyan"))
        print(colored(f"⏰ Timeframes: {', '.join(timeframes)}", "cyan"))
        
        for tf in timeframes:
            print(colored(f"\n{'='*60}", "magenta"))
            print(colored(f"⏰ TIMEFRAME: {tf}", "magenta", attrs=['bold']))
            print(colored(f"{'='*60}", "magenta"))
            
            # Scarica CANDLES_LIMIT + WARMUP per avere indicatori validi fin dall'inizio
            data = await fetcher.download_symbols(symbols, tf, config.TOTAL_CANDLES_TO_FETCH)
            
            for symbol, df in data.items():
                if df is not None and len(df) > 0:
                    try:
                        db_cache.save_data_to_db(symbol, tf, df)
                        stats['symbols_processed'] += 1
                        stats['candles_saved'] += len(df)
                        if symbol not in stats['downloaded_symbols']:
                            stats['downloaded_symbols'].append(symbol)
                    except Exception as e:
                        logging.error(f"Save error {symbol}[{tf}]: {e}")
                        stats['errors'] += 1
            
            print(colored(f"💾 Saved {len(data)} symbols to database", "green"))
        
        fetcher.print_downloaded_summary()
    
    # Calculate duration and set status to IDLE
    duration = time.time() - start_time
    db_cache.set_status_idle(
        symbols_updated=len(stats.get('downloaded_symbols', [])),
        candles_updated=stats['candles_saved'],
        duration_sec=duration
    )
    
    return stats


async def full_refresh(exchange, db_cache):
    """
    Execute full refresh: update top symbols list and download all candles.
    Called at startup and when manually requested from frontend.
    """
    import time
    start_time = time.time()
    
    print(colored("\n" + "="*60, "cyan", attrs=['bold']))
    print(colored("🔄 FULL REFRESH - Top Symbols + Candles", "cyan", attrs=['bold']))
    print(colored("="*60, "cyan", attrs=['bold']))
    
    # Set status to UPDATING at start of full refresh
    db_cache.set_status_updating()
    
    # 1. Fetch and save top symbols
    symbols = await fetch_top_symbols_and_save(exchange, db_cache)
    
    # 2. Download candles for all timeframes (this will set IDLE at the end)
    stats = await fetch_candles_for_symbols(exchange, db_cache, symbols)
    
    return stats


def display_download_summary(stats):
    """Display download summary"""
    print(colored("\n" + "="*60, "cyan"))
    print(colored("📊 DOWNLOAD SUMMARY", "cyan", attrs=['bold']))
    print(colored("="*60, "cyan"))
    print(colored(f"  ✅ Symbols processed: {stats['symbols_processed']}", "green"))
    print(colored(f"  📈 Total candles saved: {stats['candles_saved']:,}", "green"))
    print(colored(f"  🪙 Unique symbols: {len(stats.get('downloaded_symbols', []))}", "green"))
    if stats['errors'] > 0:
        print(colored(f"  ❌ Errors: {stats['errors']}", "red"))
    print(colored("="*60, "cyan"))
