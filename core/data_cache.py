"""
🚀 INCREMENTAL DATA CACHE SYSTEM

Sistema di cache intelligente per dati OHLCV che elimina la ridondanza
nel download dei dati storici, velocizzando drasticamente il bot.
"""

import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
from termcolor import colored

class IncrementalDataCache:
    """Sistema di cache intelligente per dati OHLCV"""
    
    def __init__(self, cache_dir="data_cache", retention_days=90):
        self.cache_dir = Path(cache_dir)
        self.symbols_dir = self.cache_dir / "symbols"
        self.performance_file = self.cache_dir / "performance_stats.json"
        self.retention_days = retention_days
        
        # Create directories
        self.cache_dir.mkdir(exist_ok=True)
        self.symbols_dir.mkdir(exist_ok=True)
        
        # Performance tracking
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0, 
            'incremental_updates': 0,
            'full_downloads': 0,
            'total_api_calls_saved': 0,
            'session_start': datetime.now().isoformat()
        }
        
        self.load_performance_stats()
        logging.info(f"💾 Data Cache initialized: {self.cache_dir}")
    
    def get_cache_file_path(self, symbol: str, timeframe: str) -> Path:
        """Get file path for symbol/timeframe cache"""
        safe_symbol = symbol.replace('/', '_').replace(':', '_')
        return self.symbols_dir / f"{safe_symbol}_{timeframe}.parquet"
    
    def load_performance_stats(self):
        """Load existing performance statistics"""
        try:
            if self.performance_file.exists():
                with open(self.performance_file, 'r') as f:
                    saved_stats = json.load(f)
                    for key in ['cache_hits', 'cache_misses', 'incremental_updates', 'full_downloads', 'total_api_calls_saved']:
                        if key in saved_stats:
                            self.stats[key] += saved_stats[key]
        except Exception as e:
            logging.warning(f"Could not load cache performance stats: {e}")
    
    def save_performance_stats(self):
        """Save current performance statistics"""
        try:
            with open(self.performance_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            logging.warning(f"Could not save cache performance stats: {e}")
    
    def load_cached_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Carica dati dal cache se disponibili"""
        try:
            cache_file = self.get_cache_file_path(symbol, timeframe)
            
            if not cache_file.exists():
                self.stats['cache_misses'] += 1
                return None
            
            df = pd.read_parquet(cache_file)
            
            if df is not None and len(df) > 0:
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                
                self.stats['cache_hits'] += 1
                logging.debug(f"💾 Cache hit: {symbol}[{timeframe}] - {len(df)} candles")
                return df
            else:
                self.stats['cache_misses'] += 1
                return None
                
        except Exception as e:
            logging.warning(f"❌ Cache load failed for {symbol}[{timeframe}]: {e}")
            self.stats['cache_misses'] += 1
            return None
    
    def save_data_to_cache(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """Salva DataFrame nella cache"""
        try:
            cache_file = self.get_cache_file_path(symbol, timeframe)
            
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            df = df.sort_index()
            df = df[~df.index.duplicated(keep='last')]
            
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            df = df[df.index >= cutoff_date]
            
            df.to_parquet(cache_file, compression='gzip')
            logging.debug(f"💾 Cached {symbol}[{timeframe}]: {len(df)} candles saved")
            
        except Exception as e:
            logging.error(f"❌ Cache save failed for {symbol}[{timeframe}]: {e}")
    
    def get_last_timestamp(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """Ottieni timestamp dell'ultima candela in cache"""
        try:
            cached_df = self.load_cached_data(symbol, timeframe)
            if cached_df is not None and len(cached_df) > 0:
                return cached_df.index[-1].to_pydatetime()
            return None
        except Exception as e:
            return None
    
    def get_cache_stats(self) -> Dict:
        """Get cache performance statistics"""
        total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            'total_requests': total_requests,
            'hit_rate_pct': hit_rate
        }


class SmartDataManager:
    """Gestore intelligente che combina cache e fetching"""
    
    def __init__(self, cache: IncrementalDataCache):
        self.cache = cache
        
    async def get_ohlcv_smart(self, exchange, symbol: str, timeframe: str, limit: int = 1000) -> Optional[pd.DataFrame]:
        """🧠 SMART DATA FETCHING - Cache-aware"""
        try:
            symbol_short = symbol.replace('/USDT:USDT', '')
            last_cached_timestamp = self.cache.get_last_timestamp(symbol, timeframe)
            
            if last_cached_timestamp is None:
                # No cache - full download
                from fetcher import get_data_async
                df = await get_data_async(exchange, symbol, timeframe, limit)
                
                if df is not None:
                    self.cache.save_data_to_cache(symbol, timeframe, df)
                    self.cache.stats['full_downloads'] += 1
                    
                return df
                
            else:
                # Cache exists - check if update needed
                now = datetime.utcnow()
                last_cached_utc = last_cached_timestamp.replace(tzinfo=None) if last_cached_timestamp.tzinfo else last_cached_timestamp
                age_minutes = (now - last_cached_utc).total_seconds() / 60
                
                if age_minutes <= 3:
                    # Cache is fresh, use it
                    cached_data = self.cache.load_cached_data(symbol, timeframe)
                    self.cache.stats['total_api_calls_saved'] += 1
                    return cached_data
                    
                else:
                    # Incremental update needed
                    since_dt = last_cached_utc - timedelta(hours=1)
                    since = int(since_dt.timestamp() * 1000)
                    
                    try:
                        new_ohlcv = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100, since=since)
                        
                        if new_ohlcv:
                            new_df = pd.DataFrame(new_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                            new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms')
                            new_df.set_index('timestamp', inplace=True)
                            new_df.sort_index(inplace=True)
                            
                            # Combine with cache
                            cached_df = self.cache.load_cached_data(symbol, timeframe)
                            if cached_df is not None:
                                combined_df = pd.concat([cached_df, new_df])
                                combined_df = combined_df.sort_index()
                                combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
                                
                                self.cache.save_data_to_cache(symbol, timeframe, combined_df)
                                self.cache.stats['incremental_updates'] += 1
                                self.cache.stats['total_api_calls_saved'] += 5
                                
                                return combined_df
                            else:
                                return new_df
                                
                        else:
                            # No new data, return cached
                            cached_data = self.cache.load_cached_data(symbol, timeframe)
                            self.cache.stats['total_api_calls_saved'] += 1
                            return cached_data
                            
                    except Exception as fetch_error:
                        logging.warning(f"Incremental fetch failed for {symbol}: {fetch_error}")
                        return self.cache.load_cached_data(symbol, timeframe)
            
        except Exception as e:
            logging.error(f"❌ Smart fetch failed for {symbol}[{timeframe}]: {e}")
            try:
                from fetcher import get_data_async
                return await get_data_async(exchange, symbol, timeframe, limit)
            except:
                return None


# Global instances
global_data_cache = IncrementalDataCache()
global_smart_manager = SmartDataManager(global_data_cache)

# Export cache availability flag
CACHE_SYSTEM_AVAILABLE = True


async def fetch_with_cache(exchange, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """🚀 CACHE-AWARE FETCHING WRAPPER"""
    return await global_smart_manager.get_ohlcv_smart(exchange, symbol, timeframe)


def display_cache_stats():
    """Display cache performance statistics"""
    try:
        stats = global_data_cache.get_cache_stats()
        
        print(colored("\n💾 CACHE PERFORMANCE STATISTICS", "cyan", attrs=['bold']))
        print(colored("=" * 80, "cyan"))
        print(colored(f"📊 Cache Hit Rate: {stats['hit_rate_pct']:.1f}% ({stats['cache_hits']}/{stats['total_requests']})", "green"))
        print(colored(f"🚀 API Calls Saved: {stats['total_api_calls_saved']}", "green"))
        print(colored(f"📈 Incremental Updates: {stats['incremental_updates']}", "yellow"))
        print(colored(f"📥 Full Downloads: {stats['full_downloads']}", "yellow"))
        print(colored("=" * 80, "cyan"))
        
        global_data_cache.save_performance_stats()
        
    except Exception as e:
        logging.warning(f"Error displaying cache stats: {e}")
