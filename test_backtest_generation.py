#!/usr/bin/env python3
"""
Test script per verificare la generazione automatica di backtest
"""

import asyncio
import logging
import ccxt.async_support as ccxt_async
from datetime import datetime, timedelta

from config import exchange_config, ENABLED_TIMEFRAMES
from fetcher import fetch_and_save_data
from trainer import label_with_future_returns
from core.visualization import run_symbol_backtest
from logging_config import *
import config

async def test_backtest_generation():
    """Test della generazione automatica di backtest"""
    
    logging.info("🧪 Testing automatic backtest generation...")
    
    # Setup exchange
    exchange = ccxt_async.bybit(exchange_config)
    await exchange.load_markets()
    
    # Test symbols (use real signals from previous output)
    test_symbols = [
        'MERL/USDT:USDT',  # Previous SELL signal with 100% confidence
        'PYTH/USDT:USDT',  # Previous BUY signal with 100% confidence
        'IP/USDT:USDT'     # Previous BUY signal with 69% confidence
    ]
    
    # Test timeframes
    timeframes = ['15m', '30m', '1h']
    
    for symbol in test_symbols:
        try:
            logging.info(f"📊 Testing backtest for {symbol}")
            
            for tf in timeframes:
                try:
                    # Get data
                    df = await fetch_and_save_data(exchange, symbol, tf)
                    
                    if df is None or len(df) < 100:
                        logging.warning(f"⚠️ Insufficient data for {symbol} [{tf}]")
                        continue
                    
                    # Generate predictions
                    historical_predictions = label_with_future_returns(
                        df,
                        lookforward_steps=config.FUTURE_RETURN_STEPS,
                        buy_threshold=config.RETURN_BUY_THRESHOLD,
                        sell_threshold=config.RETURN_SELL_THRESHOLD
                    )
                    
                    # Test different periods
                    test_periods = [
                        {"name": "Last_7_days", "days": 7},
                        {"name": "Last_30_days", "days": 30}
                    ]
                    
                    for period in test_periods:
                        try:
                            end_date = datetime.now()
                            start_date = end_date - timedelta(days=period["days"])
                            
                            # Run backtest
                            results = run_symbol_backtest(
                                symbol, df, historical_predictions, tf,
                                start_date=start_date.strftime('%Y-%m-%d'),
                                end_date=end_date.strftime('%Y-%m-%d')
                            )
                            
                            if results.get('stats'):
                                stats = results['stats']
                                logging.info(f"✅ {symbol} [{tf}] - {period['name']}: {stats['total_return_pct']:.2f}% return, {stats['win_rate']:.1f}% win rate, {stats['signal_accuracy']:.1f}% accuracy")
                            else:
                                logging.warning(f"⚠️ No results for {symbol} [{tf}] - {period['name']}")
                            
                        except Exception as e:
                            logging.error(f"❌ Error testing {symbol} [{tf}] {period['name']}: {e}")
                
                except Exception as tf_error:
                    logging.error(f"❌ Error with timeframe {tf} for {symbol}: {tf_error}")
                    continue
            
        except Exception as symbol_error:
            logging.error(f"❌ Error testing {symbol}: {symbol_error}")
            continue
    
    await exchange.close()
    logging.info("🎉 Backtest generation test completed!")

if __name__ == "__main__":
    asyncio.run(test_backtest_generation())
