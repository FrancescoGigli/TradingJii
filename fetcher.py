# fetcher.py

import asyncio
import logging
import pandas as pd
from datetime import datetime, timedelta
from config import TIMEFRAME_DEFAULT, DATA_LIMIT_DAYS, TOP_ANALYSIS_CRYPTO
from termcolor import colored
import re
import sqlite3
from db_manager import save_data

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
    ohlcv_all = []
    since_dt = datetime.utcnow() - timedelta(days=DATA_LIMIT_DAYS)
    since = int(since_dt.timestamp() * 1000)
    current_time = int(datetime.utcnow().timestamp() * 1000)
    
    while True:
        try:
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit, since=since)
        except Exception as e:
            logging.error(f"Error fetching ohlcv for {symbol}: {e}")
            break
        if not ohlcv:
            break
        
        ohlcv_all.extend(ohlcv)
        last_timestamp = ohlcv[-1][0]
        if last_timestamp >= current_time:
            break
        new_since = last_timestamp + 1
        if new_since <= since:
            break
        since = new_since

    if ohlcv_all:
        df = pd.DataFrame(ohlcv_all, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        last_date = df.index[-1].strftime('%Y-%m-%d')
        logging.info(colored(
            f"Fetched {len(df)} candlestick for {symbol} (Timeframe: {timeframe}) from {since_dt.strftime('%Y-%m-%d')} to {last_date}.",
            "cyan"))
        return df
    else:
        logging.info(f"Nessun dato disponibile per {symbol} negli ultimi {DATA_LIMIT_DAYS} giorni.")
        return None

async def fetch_and_save_data(exchange, symbol, timeframe=TIMEFRAME_DEFAULT, limit=1000, save_to_db=None):
    # Use the global USE_DATABASE setting if save_to_db is not explicitly provided
    if save_to_db is None:
        from config import USE_DATABASE
        save_to_db = USE_DATABASE
    df = await get_data_async(exchange, symbol, timeframe, limit)
    if df is not None:
        from data_utils import add_technical_indicators
        
        # Aggiungi gli indicatori tecnici
        df_with_indicators = add_technical_indicators(df.copy(), symbol)
        
        # Aggiungi esplicitamente la volatilità
        df_with_indicators['volatility'] = df_with_indicators['close'].pct_change() * 100
        df_with_indicators['volatility'] = df_with_indicators['volatility'].replace([float('inf'), float('-inf')], float('nan')).fillna(0.0)
        df_with_indicators['volatility'] = df_with_indicators['volatility'].clip(-100, 100)
        
        # Salva i dati nel database solo se save_to_db è True e la configurazione USE_DATABASE è attiva
        if save_to_db:
            try:
                save_data(symbol, df_with_indicators, timeframe)
            except sqlite3.OperationalError as e:
                # Log the error but don't fail the entire operation
                logging.warning(f"Database error during save_data for {symbol}: {e}")
            
        # Restituisci il dataframe con tutti gli indicatori (inclusa volatilità)
        return df_with_indicators
    return None
