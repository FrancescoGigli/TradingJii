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
    tasks = [fetch_ticker_volume(exchange, symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks)
    symbol_volumes = [(symbol, volume) for symbol, volume in results if volume is not None]
    symbol_volumes.sort(key=lambda x: x[1], reverse=True)
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
        
        # Print to console with color
        print(colored(f"🕯️ {symbol} [{timeframe}]: {last_candle_formatted}", "green"))
        
        # Log to main log file
        logging.info(f"📊 Latest candle - {symbol} [{timeframe}]: {last_candle_formatted} at {last_date}")
        
        # Save to dedicated candle log file
        candle_log_path = Path("logs/latest_candles.log")
        candle_log_path.parent.mkdir(exist_ok=True)
        
        try:
            with open(candle_log_path, "a", encoding="utf-8") as f:
                f.write(f"{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} - {symbol} [{timeframe}]: {last_candle_formatted}\n")
        except Exception as e:
            logging.warning(f"Failed to write to candle log: {e}")
        
        logging.info(colored(
            f"Fetched {len(df)} unique candlesticks for {symbol} (Timeframe: {timeframe}) from {since_dt.strftime('%Y-%m-%d')} to {last_date}.",
            "cyan"))
        return df
    else:
        logging.info(f"No data available for {symbol} in the last {DATA_LIMIT_DAYS} days.")
        return None

async def fetch_and_save_data(exchange, symbol, timeframe=TIMEFRAME_DEFAULT, limit=1000):
    """
    Fetch OHLCV data and add all technical indicators.
    
    NEW: Now logs complete last candle with all indicators
    
    Fixes:
    - Removed duplicate volatility calculation (now handled in data_utils)
    - Centralized all indicator logic in data_utils for consistency
    """
    df = await get_data_async(exchange, symbol, timeframe, limit)
    if df is not None:
        from data_utils import add_technical_indicators, add_swing_probability_features
        from pathlib import Path
        
        # Add all technical indicators (including volatility) in one place
        df_with_indicators = add_technical_indicators(df.copy(), symbol)
        
        # Add swing probability features (no lookahead bias)
        df_with_indicators = add_swing_probability_features(df_with_indicators)
        
        # CRITICAL FIX: Filtra solo candele completamente chiuse per consistenza backtest/live
        original_length = len(df_with_indicators)
        closed_candles_mask = df_with_indicators.index.to_series().apply(
            lambda ts: is_candle_closed(ts, timeframe)
        )
        df_with_indicators = df_with_indicators[closed_candles_mask]
        
        filtered_count = original_length - len(df_with_indicators)
        if filtered_count > 0:
            logging.info(colored(f"🔒 {symbol} [{timeframe}]: Filtered {filtered_count} open candles, using {len(df_with_indicators)} closed candles", "yellow"))
        
        # === LOG COMPLETE LAST CANDLE WITH ALL INDICATORS ===
        try:
            last_row = df_with_indicators.iloc[-1]
            last_timestamp = df_with_indicators.index[-1].strftime('%Y-%m-%d %H:%M:%S')
            
            # Format complete candle data with all indicators
            candle_data = []
            candle_data.append(f"O:{last_row['open']:.4f}")
            candle_data.append(f"H:{last_row['high']:.4f}")
            candle_data.append(f"L:{last_row['low']:.4f}")
            candle_data.append(f"C:{last_row['close']:.4f}")
            candle_data.append(f"V:{last_row['volume']:.0f}")
            candle_data.append(f"RSI:{last_row['rsi_fast']:.2f}")
            candle_data.append(f"MACD:{last_row['macd']:.6f}")
            candle_data.append(f"ATR:{last_row['atr']:.4f}")
            candle_data.append(f"ADX:{last_row['adx']:.2f}")
            candle_data.append(f"EMA20:{last_row['ema20']:.4f}")
            candle_data.append(f"VOL%:{last_row['volatility']:.2f}")
            
            complete_candle_str = ", ".join(candle_data)
            
            # Print to console with color
            print(colored(f"📊 {symbol} [{timeframe}] - {last_timestamp}", "cyan"))
            print(colored(f"    {complete_candle_str}", "green"))
            
            # Save to dedicated detailed candle log
            detailed_log_path = Path("logs/detailed_candles.log")
            detailed_log_path.parent.mkdir(exist_ok=True)
            
            with open(detailed_log_path, "a", encoding="utf-8") as f:
                f.write(f"{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} | {symbol} [{timeframe}] @ {last_timestamp}\n")
                f.write(f"    {complete_candle_str}\n")
                f.write("    " + "-" * 80 + "\n")
        
        except Exception as e:
            logging.warning(f"Failed to log detailed candle data for {symbol}: {e}")
        
        # Return dataframe with all indicators
        return df_with_indicators
    return None
