# fetcher.py

import asyncio
import logging
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from config import TIMEFRAME_DEFAULT, DATA_LIMIT_DAYS, TOP_ANALYSIS_CRYPTO
from termcolor import colored
import re
import time
from concurrent.futures import ThreadPoolExecutor
from asyncio import Semaphore

# Import database cache system
try:
    from core.database_cache import fetch_with_database, global_db_cache, global_db_manager, display_database_stats
    DATABASE_CACHE_AVAILABLE = True
    logging.info("🗄️ Database cache system loaded successfully")
except ImportError as e:
    logging.warning(f"⚠️ Database cache system not available: {e}")
    DATABASE_CACHE_AVAILABLE = False

def is_candle_closed(candle_timestamp, timeframe):
    """
    Determina se una candela è completamente chiusa basandosi sul timeframe.
    
    CRITICAL FIX: Assicura consistenza tra backtest e live trading
    usando solo candele completamente chiuse.
    
    Args:
        candle_timestamp (pd.Timestamp): Timestamp della candela
        timeframe (str): Timeframe (es. "15m", "1h")
        
    Returns:
        bool: True se la candela è chiusa, False se ancora aperta
    """
    try:
        current_time = pd.Timestamp.now(tz='UTC')
        
        # Converti candle_timestamp in UTC se necessario
        if candle_timestamp.tz is None:
            candle_timestamp = candle_timestamp.tz_localize('UTC')
        else:
            candle_timestamp = candle_timestamp.tz_convert('UTC')
        
        # Calcola la durata del timeframe in minuti
        if timeframe.endswith('m'):
            minutes = int(timeframe[:-1])
        elif timeframe.endswith('h'):
            hours = int(timeframe[:-1])
            minutes = hours * 60
        elif timeframe.endswith('d'):
            days = int(timeframe[:-1])
            minutes = days * 24 * 60
        else:
            logging.warning(f"Unknown timeframe format: {timeframe}, assuming 15m")
            minutes = 15
        
        # Una candela è chiusa se il tempo corrente >= inizio candela + durata timeframe
        candle_end_time = candle_timestamp + pd.Timedelta(minutes=minutes)
        is_closed = current_time >= candle_end_time
        
        # Log per debug (solo per le ultime candele)
        if not is_closed:
            time_remaining = candle_end_time - current_time
            logging.debug(f"Candle {candle_timestamp} [{timeframe}] still open, closes in {time_remaining}")
        
        return is_closed
        
    except Exception as e:
        logging.error(f"Error checking candle closure: {e}")
        # Safe fallback: assume candle is closed if we can't determine
        return True
async def fetch_markets(exchange):
    return await exchange.load_markets()

async def fetch_ticker_volume(exchange, symbol):
    try:
        ticker = await exchange.fetch_ticker(symbol)
        return symbol, ticker.get('quoteVolume')
    except Exception as e:
        logging.error(f"Error fetching ticker volume for {symbol}: {e}")
        return symbol, None

async def get_top_symbols(exchange, symbols, top_n=TOP_ANALYSIS_CRYPTO):
    # Parallel ticker volume fetching with rate limiting
    semaphore = Semaphore(20)  # Max 20 concurrent requests
    
    async def fetch_with_semaphore(symbol):
        async with semaphore:
            return await fetch_ticker_volume(exchange, symbol)
    
    tasks = [fetch_with_semaphore(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out exceptions and None values
    symbol_volumes = []
    for result in results:
        if isinstance(result, tuple) and result[1] is not None:
            symbol_volumes.append(result)
    
    symbol_volumes.sort(key=lambda x: x[1], reverse=True)
    logging.info(f"🚀 Parallel ticker fetch: {len(symbol_volumes)} symbols processed concurrently")
    return [x[0] for x in symbol_volumes[:top_n]]

async def fetch_min_amounts(exchange, top_symbols, markets):
    min_amounts = {}
    for symbol in top_symbols:
        market = markets.get(symbol)
        if market and 'limits' in market and 'amount' in market['limits'] and 'min' in market['limits']['amount']:
            min_amounts[symbol] = market['limits']['amount']['min']
        else:
            min_amounts[symbol] = 1
    return min_amounts

async def get_data_async(exchange, symbol, timeframe=TIMEFRAME_DEFAULT, limit=1000):
    """
    Fetch OHLCV data with proper error handling and rate limiting.
    
    Fixes:
    - Prevents infinite loops with timestamp validation
    - Adds exponential backoff for rate limiting
    - Limits maximum iterations for safety
    """
    ohlcv_all = []
    since_dt = datetime.utcnow() - timedelta(days=DATA_LIMIT_DAYS)
    since = int(since_dt.timestamp() * 1000)
    current_time = int(datetime.utcnow().timestamp() * 1000)
    
    # Safety limits to prevent infinite loops
    max_iterations = 100
    iteration_count = 0
    last_timestamp_seen = None
    consecutive_same_timestamps = 0
    
    # Rate limiting parameters
    base_delay = 0.1  # 100ms base delay
    max_delay = 5.0   # 5s max delay
    current_delay = base_delay
    
    while iteration_count < max_iterations:
        iteration_count += 1
        
        try:
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit, since=since)
            
            # Reset delay on successful request
            current_delay = base_delay
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Handle rate limiting specifically
            if any(keyword in error_msg for keyword in ['rate', 'limit', 'too many', 'throttle']):
                logging.warning(f"Rate limit hit for {symbol}, backing off for {current_delay:.2f}s")
                await asyncio.sleep(current_delay)
                current_delay = min(current_delay * 2, max_delay)  # Exponential backoff
                continue
            else:
                logging.error(f"Error fetching ohlcv for {symbol}: {e}")
                break
        
        if not ohlcv:
            logging.debug(f"No more data available for {symbol}")
            break
        
        # Detect timestamp stagnation to prevent infinite loops
        current_last_timestamp = ohlcv[-1][0]
        if last_timestamp_seen == current_last_timestamp:
            consecutive_same_timestamps += 1
            if consecutive_same_timestamps >= 3:
                logging.warning(f"Timestamp stagnation detected for {symbol}, stopping fetch")
                break
        else:
            consecutive_same_timestamps = 0
            last_timestamp_seen = current_last_timestamp
        
        ohlcv_all.extend(ohlcv)
        
        # Check if we've reached current time
        if current_last_timestamp >= current_time:
            logging.debug(f"Reached current time for {symbol}")
            break
            
        # Calculate next since timestamp
        new_since = current_last_timestamp + 1
        
        # Additional safety check: ensure we're making progress
        if new_since <= since:
            logging.warning(f"No progress in timestamp advancement for {symbol}, stopping")
            break
            
        since = new_since
        
        # Small delay to be respectful to the exchange
        if current_delay > base_delay:
            await asyncio.sleep(base_delay)

    if iteration_count >= max_iterations:
        logging.warning(f"Maximum iterations ({max_iterations}) reached for {symbol}")

    if ohlcv_all:
        # Remove duplicates based on timestamp while preserving order
        df = pd.DataFrame(ohlcv_all, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df = df.drop_duplicates(subset=['timestamp'], keep='last')
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)  # Ensure chronological order
        
        # Log and save last candle information
        last_candle = df.iloc[-1]
        last_date = df.index[-1].strftime('%Y-%m-%d %H:%M:%S')
        
        # Format last candle data: O,H,L,C,V
        last_candle_formatted = f"{last_candle['open']:.4f},{last_candle['high']:.4f},{last_candle['low']:.4f},{last_candle['close']:.4f},{last_candle['volume']:.0f}"
        
        # Only log to console during normal operations, not during training
        import inspect
        frame = inspect.currentframe()
        is_training_phase = False
        
        # Check if we're being called from training context
        try:
            for i in range(5):  # Check up to 5 frames up the stack
                if frame is None:
                    break
                frame_info = frame.f_code
                if 'train' in frame_info.co_filename.lower() or 'train' in frame_info.co_name.lower():
                    is_training_phase = True
                    break
                frame = frame.f_back
        except:
            pass
        
        # Completely suppress console output (only save to log files)
        # No more console printing of candles - too verbose
        pass
        
        # Save to dedicated candle log file
        candle_log_path = Path("logs/latest_candles.log")
        candle_log_path.parent.mkdir(exist_ok=True)
        
        try:
            with open(candle_log_path, "a", encoding="utf-8") as f:
                f.write(f"{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} - {symbol} [{timeframe}]: {last_candle_formatted}\n")
        except Exception as e:
            logging.warning(f"Failed to write to candle log: {e}")
        
        # Only log during analysis phase, not training (silenced for clean output)
        pass
        return df
    else:
        logging.info(f"No data available for {symbol} in the last {DATA_LIMIT_DAYS} days.")
        return None

async def fetch_and_save_data(exchange, symbol, timeframe=TIMEFRAME_DEFAULT, limit=1000):
    """
    🚀 ENHANCED CACHE-OPTIMIZED FETCH (GAME CHANGER!)
    
    NEW: Usa database con indicatori pre-calcolati per 10x speedup!
    
    Strategy:
    1. Check enhanced_data table for existing data with indicators
    2. If fresh (< 5 min), return directly → 10x FASTER!
    3. If stale/missing, calculate & save all indicators
    4. Future calls use cached indicators → MASSIVE SPEEDUP!
    """
    
    if DATABASE_CACHE_AVAILABLE:
        symbol_short = symbol.replace('/USDT:USDT', '')
        
        try:
            # 🚀 FIRST: Try to get enhanced data with ALL indicators pre-calculated
            enhanced_data = global_db_cache.get_enhanced_cached_data(symbol, timeframe)
            
            if enhanced_data is not None and len(enhanced_data) > 0:
                # Check if data is fresh enough
                last_timestamp = enhanced_data.index[-1]
                now = pd.Timestamp.now(tz='UTC')
                if last_timestamp.tz is None:
                    last_timestamp = last_timestamp.tz_localize('UTC')
                
                age_minutes = (now - last_timestamp).total_seconds() / 60
                
                if age_minutes <= 5:  # Fresh enhanced data!
                    # 🎉 JACKPOT: Return pre-calculated indicators (10x speedup!)
                    logging.debug(f"🚀 {symbol_short}[{timeframe}]: ENHANCED cache hit - ALL indicators ready ({age_minutes:.1f}m old)")
                    
                    # Filter closed candles
                    closed_candles_mask = enhanced_data.index.to_series().apply(
                        lambda ts: is_candle_closed(ts, timeframe)
                    )
                    enhanced_data_filtered = enhanced_data[closed_candles_mask]
                    
                    return enhanced_data_filtered
                else:
                    logging.debug(f"🔄 {symbol_short}[{timeframe}]: Enhanced data too old ({age_minutes:.1f}m), recalculating...")
            
        except Exception as enhanced_error:
            logging.debug(f"Enhanced cache miss for {symbol_short}[{timeframe}]: {enhanced_error}")
    
    # FALLBACK: Standard calculation with enhanced caching
    try:
        # Get OHLCV data (from cache or exchange)
        if DATABASE_CACHE_AVAILABLE:
            df = await global_db_manager.get_ohlcv_smart(exchange, symbol, timeframe, limit)
        else:
            df = await get_data_async(exchange, symbol, timeframe, limit)
        
        if df is not None:
            from data_utils import add_technical_indicators, add_swing_probability_features
            
            # Calculate all technical indicators (CPU intensive but cached afterward!)
            df_with_indicators = add_technical_indicators(df.copy(), symbol)
            
            # Add swing probability features (no lookahead bias)
            df_with_indicators = add_swing_probability_features(df_with_indicators)
            
            # Filter closed candles for consistency
            closed_candles_mask = df_with_indicators.index.to_series().apply(
                lambda ts: is_candle_closed(ts, timeframe)
            )
            df_with_indicators = df_with_indicators[closed_candles_mask]
            
            # 🚀 SAVE TO ENHANCED DATABASE with WARMUP SKIP (QUALITY IMPROVEMENT!)
            if DATABASE_CACHE_AVAILABLE:
                try:
                    from config import WARMUP_PERIODS
                    symbol_short = symbol.replace('/USDT:USDT', '')
                    
                    # Skip first WARMUP_PERIODS candeles to ensure reliable indicators
                    if len(df_with_indicators) > WARMUP_PERIODS:
                        df_stable = df_with_indicators[WARMUP_PERIODS:]  # Skip primi 30 dati di warmup
                        global_db_cache.save_enhanced_data_to_db(symbol, timeframe, df_stable)
                        logging.debug(f"💾 {symbol_short}[{timeframe}]: Saved {len(df_stable)} stable indicators (skipped {WARMUP_PERIODS} warmup)")
                    else:
                        # Not enough data for reliable indicators
                        logging.warning(f"⚠️ {symbol_short}[{timeframe}]: Insufficient data {len(df_with_indicators)} <= {WARMUP_PERIODS} warmup")
                except Exception as save_error:
                    logging.warning(f"Failed to save enhanced data for {symbol_short}[{timeframe}]: {save_error}")
            
            return df_with_indicators
            
        return None
        
    except Exception as e:
        logging.error(f"❌ Enhanced fetch failed for {symbol}[{timeframe}]: {e}")
        return None

# ==============================================================================
# PARALLEL FETCHING OPTIMIZATION - Threading Implementation
# ==============================================================================

async def fetch_all_data_parallel(exchange, symbols, timeframes, max_concurrent=15):
    """
    🚀 PARALLEL DATA FETCHING OPTIMIZATION
    
    Fetches data for all symbol/timeframe combinations concurrently with intelligent
    rate limiting. This replaces the sequential approach for massive speedup.
    
    Args:
        exchange: Exchange instance
        symbols: List of symbols to fetch
        timeframes: List of timeframes to fetch
        max_concurrent: Maximum concurrent requests (default: 15)
        
    Returns:
        dict: {symbol: {timeframe: dataframe}} structure
        
    Performance:
        - Sequential: ~300-600 seconds for 50 symbols × 3 timeframes
        - Parallel: ~30-60 seconds for same workload (5-10x speedup)
    """
    start_time = time.time()
    
    # Rate limiting semaphore - critical for exchange stability
    semaphore = Semaphore(max_concurrent)
    
    # Progress tracking
    total_tasks = len(symbols) * len(timeframes)
    completed_tasks = 0
    
    logging.info(f"🚀 Starting parallel data fetch: {len(symbols)} symbols × {len(timeframes)} timeframes = {total_tasks} total tasks")
    logging.info(f"⚡ Max concurrent requests: {max_concurrent}")
    
    async def fetch_single_with_semaphore(symbol, timeframe):
        """Fetch single symbol/timeframe combination with semaphore control"""
        nonlocal completed_tasks
        
        async with semaphore:
            try:
                # Add small delay to distribute requests evenly
                await asyncio.sleep(0.05)  # 50ms between requests
                
                df = await fetch_and_save_data(exchange, symbol, timeframe)
                
                completed_tasks += 1
                progress_pct = (completed_tasks / total_tasks) * 100
                
                if completed_tasks % 10 == 0 or completed_tasks == total_tasks:
                    elapsed = time.time() - start_time
                    rate = completed_tasks / elapsed if elapsed > 0 else 0
                    eta = (total_tasks - completed_tasks) / rate if rate > 0 else 0
                    
                    logging.info(f"📊 Progress: {completed_tasks}/{total_tasks} ({progress_pct:.1f}%) | Rate: {rate:.1f}/s | ETA: {eta:.0f}s")
                
                return symbol, timeframe, df
                
            except Exception as e:
                logging.error(f"❌ Failed to fetch {symbol}[{timeframe}]: {e}")
                completed_tasks += 1
                return symbol, timeframe, None
    
    # Create all tasks
    tasks = []
    for symbol in symbols:
        for timeframe in timeframes:
            task = fetch_single_with_semaphore(symbol, timeframe)
            tasks.append(task)
    
    # Execute all tasks concurrently
    logging.info(f"⏳ Executing {len(tasks)} concurrent fetch tasks...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results into structured format
    all_data = {}
    successful_fetches = 0
    
    for result in results:
        if isinstance(result, tuple) and len(result) == 3:
            symbol, timeframe, df = result
            
            if df is not None:
                if symbol not in all_data:
                    all_data[symbol] = {}
                all_data[symbol][timeframe] = df
                successful_fetches += 1
            else:
                # Log failed fetch without cluttering output
                logging.debug(f"Failed fetch: {symbol}[{timeframe}]")
        elif isinstance(result, Exception):
            logging.error(f"Task exception: {result}")
    
    # Performance summary
    total_time = time.time() - start_time
    speedup_estimate = (total_tasks * 2) / total_time  # Estimated vs sequential (2s per fetch)
    
    logging.info(f"🎉 Parallel fetch complete!")
    logging.info(f"   ✅ Successful: {successful_fetches}/{total_tasks} ({successful_fetches/total_tasks*100:.1f}%)")
    logging.info(f"   ⏱️ Total time: {total_time:.1f}s")
    logging.info(f"   🚀 Estimated speedup: {speedup_estimate:.1f}x vs sequential")
    logging.info(f"   📊 Symbols with complete data: {len(all_data)}")
    
    return all_data

async def fetch_symbol_data_parallel(exchange, symbol, timeframes):
    """
    🚀 SINGLE SYMBOL PARALLEL FETCHING
    
    Fetches all timeframes for a single symbol concurrently.
    Useful when processing symbols one by one but want timeframe parallelism.
    
    Args:
        exchange: Exchange instance  
        symbol: Single symbol to fetch
        timeframes: List of timeframes
        
    Returns:
        dict: {timeframe: dataframe} for the symbol
    """
    semaphore = Semaphore(len(timeframes))  # Allow all timeframes concurrently for single symbol
    
    async def fetch_tf_with_semaphore(tf):
        async with semaphore:
            try:
                await asyncio.sleep(0.02)  # Small delay between timeframes
                return tf, await fetch_and_save_data(exchange, symbol, tf)
            except Exception as e:
                logging.error(f"Error fetching {symbol}[{tf}]: {e}")
                return tf, None
    
    # Fetch all timeframes for this symbol concurrently
    tasks = [fetch_tf_with_semaphore(tf) for tf in timeframes]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Build result dictionary
    symbol_data = {}
    for result in results:
        if isinstance(result, tuple) and len(result) == 2:
            tf, df = result
            if df is not None:
                symbol_data[tf] = df
    
    logging.debug(f"✅ {symbol}: {len(symbol_data)}/{len(timeframes)} timeframes fetched successfully")
    return symbol_data
