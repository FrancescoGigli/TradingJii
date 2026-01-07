"""
📥 Bybit Historical Data Fetcher

Downloads historical OHLCV data from Bybit with pagination support.
Handles rate limiting and large date ranges (12+ months).
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass
import time

import pandas as pd
import ccxt.async_support as ccxt
from termcolor import colored

import config

logger = logging.getLogger(__name__)


@dataclass
class DownloadProgress:
    """Progress information for a download operation"""
    symbol: str
    timeframe: str
    total_candles: int
    downloaded_candles: int
    current_date: datetime
    start_date: datetime
    end_date: datetime
    requests_made: int
    errors: int
    
    @property
    def progress_pct(self) -> float:
        if self.total_candles == 0:
            return 0.0
        return min(100.0, (self.downloaded_candles / self.total_candles) * 100)
    
    @property
    def is_complete(self) -> bool:
        return self.progress_pct >= 100


class BybitHistoricalFetcher:
    """
    Fetches historical OHLCV data from Bybit with pagination.
    
    Features:
    - Pagination for large date ranges
    - Rate limiting compliance
    - Progress callbacks
    - Retry logic for failed requests
    """
    
    def __init__(self, exchange: ccxt.Exchange = None):
        self._exchange = exchange
        self._own_exchange = False
        self.markets = None
    
    async def __aenter__(self):
        if self._exchange is None:
            self._exchange = ccxt.bybit(config.EXCHANGE_CONFIG)
            self._own_exchange = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._own_exchange and self._exchange:
            await self._exchange.close()
    
    @property
    def exchange(self):
        return self._exchange
    
    async def load_markets(self) -> Dict:
        """Load exchange markets"""
        if self.markets is None:
            self.markets = await self._exchange.load_markets()
        return self.markets
    
    def _get_timeframe_ms(self, timeframe: str) -> int:
        """Get timeframe duration in milliseconds"""
        if timeframe.endswith('m'):
            return int(timeframe[:-1]) * 60 * 1000
        elif timeframe.endswith('h'):
            return int(timeframe[:-1]) * 60 * 60 * 1000
        elif timeframe.endswith('d'):
            return int(timeframe[:-1]) * 24 * 60 * 60 * 1000
        else:
            return 15 * 60 * 1000  # Default 15m
    
    def _calculate_target_start(self, timeframe: str) -> datetime:
        """
        Calculate target start date based on historical period + warmup.
        
        Returns datetime for: now - HISTORICAL_MONTHS - warmup period
        """
        now = datetime.utcnow()
        
        # Target end: now
        # Target start: now - 12 months - warmup candles
        
        # Calculate warmup duration
        tf_minutes = config.get_target_candles(timeframe) // config.CANDLES_15M_PER_DAY  # rough days
        warmup_duration = timedelta(days=tf_minutes)
        
        # More accurate: calculate from candles
        tf_ms = self._get_timeframe_ms(timeframe)
        total_candles = config.get_target_candles(timeframe)
        total_duration_ms = total_candles * tf_ms
        total_duration = timedelta(milliseconds=total_duration_ms)
        
        target_start = now - total_duration
        
        return target_start
    
    async def fetch_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime = None,
        end_date: datetime = None,
        progress_callback: Callable[[DownloadProgress], None] = None,
        max_retries: int = 3
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data with pagination.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT:USDT')
            timeframe: Candle timeframe (e.g., '15m')
            start_date: Start date (default: 12 months + warmup ago)
            end_date: End date (default: now)
            progress_callback: Optional callback for progress updates
            max_retries: Max retries per request
            
        Returns:
            DataFrame with all historical candles
        """
        # Set default dates
        if end_date is None:
            end_date = datetime.utcnow()
        
        if start_date is None:
            start_date = self._calculate_target_start(timeframe)
        
        tf_ms = self._get_timeframe_ms(timeframe)
        
        # Calculate expected total candles
        total_duration_ms = int((end_date - start_date).total_seconds() * 1000)
        expected_candles = total_duration_ms // tf_ms
        
        # Initialize progress
        progress = DownloadProgress(
            symbol=symbol,
            timeframe=timeframe,
            total_candles=expected_candles,
            downloaded_candles=0,
            current_date=start_date,
            start_date=start_date,
            end_date=end_date,
            requests_made=0,
            errors=0
        )
        
        all_candles = []
        current_start_ms = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000)
        
        logger.info(f"📥 Starting download: {symbol} [{timeframe}]")
        logger.info(f"   Date range: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}")
        logger.info(f"   Expected candles: ~{expected_candles:,}")
        
        while current_start_ms < end_ms:
            # Rate limiting delay
            await asyncio.sleep(config.REQUEST_DELAY_MS / 1000)
            
            # Retry loop
            for retry in range(max_retries):
                try:
                    # Fetch batch (max 1000 candles per request)
                    ohlcv = await self._exchange.fetch_ohlcv(
                        symbol,
                        timeframe=timeframe,
                        since=current_start_ms,
                        limit=config.MAX_CANDLES_PER_REQUEST
                    )
                    
                    progress.requests_made += 1
                    
                    if not ohlcv:
                        # No more data available
                        logger.debug(f"No more data for {symbol} at {datetime.fromtimestamp(current_start_ms/1000)}")
                        current_start_ms = end_ms  # Exit loop
                        break
                    
                    all_candles.extend(ohlcv)
                    progress.downloaded_candles = len(all_candles)
                    
                    # Move to next batch
                    last_timestamp = ohlcv[-1][0]
                    current_start_ms = last_timestamp + tf_ms
                    progress.current_date = datetime.fromtimestamp(current_start_ms / 1000)
                    
                    # Progress callback
                    if progress_callback:
                        progress_callback(progress)
                    
                    # Log progress every 10 requests
                    if progress.requests_made % 10 == 0:
                        logger.info(f"   {symbol}: {progress.progress_pct:.1f}% ({progress.downloaded_candles:,} candles)")
                    
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    progress.errors += 1
                    logger.warning(f"Error fetching {symbol} (retry {retry+1}/{max_retries}): {e}")
                    
                    if retry < max_retries - 1:
                        await asyncio.sleep(1)  # Wait before retry
                    else:
                        logger.error(f"Failed to fetch {symbol} after {max_retries} retries")
                        # Continue with partial data
                        current_start_ms = end_ms
        
        # Convert to DataFrame
        if not all_candles:
            logger.warning(f"No candles downloaded for {symbol}")
            return pd.DataFrame()
        
        df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        
        # Remove duplicates
        df = df[~df.index.duplicated(keep='first')]
        
        logger.info(f"✅ {symbol}: Downloaded {len(df):,} candles")
        
        return df
    
    async def fetch_incremental(
        self,
        symbol: str,
        timeframe: str,
        last_timestamp: datetime
    ) -> pd.DataFrame:
        """
        Fetch only new candles since last_timestamp.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe
            last_timestamp: Last known candle timestamp
            
        Returns:
            DataFrame with new candles only
        """
        return await self.fetch_historical_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            start_date=last_timestamp,
            end_date=datetime.utcnow()
        )


async def download_symbol_history(
    symbol: str,
    timeframe: str,
    start_date: datetime = None,
    end_date: datetime = None,
    progress_callback: Callable[[DownloadProgress], None] = None
) -> pd.DataFrame:
    """
    Convenience function to download historical data for a single symbol.
    
    Args:
        symbol: Trading pair symbol
        timeframe: Candle timeframe
        start_date: Start date
        end_date: End date
        progress_callback: Progress callback
        
    Returns:
        DataFrame with historical candles
    """
    async with BybitHistoricalFetcher() as fetcher:
        await fetcher.load_markets()
        return await fetcher.fetch_historical_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            progress_callback=progress_callback
        )


def print_download_progress(progress: DownloadProgress):
    """Default progress printer"""
    bar_width = 30
    filled = int(bar_width * progress.progress_pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    
    print(f"\r  [{bar}] {progress.progress_pct:5.1f}% | {progress.downloaded_candles:,} candles | {progress.requests_made} requests", end="", flush=True)
    
    if progress.is_complete:
        print()  # New line when complete
