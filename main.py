#!/usr/bin/env python3
"""
Restructured Trading Bot - Clean Main Entry Point
Focuses only on live trading without backtesting overhead
"""

import sys
import os
import numpy as np
import warnings
import asyncio
import logging

# Suppress runtime warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="ta")
np.seterr(divide='ignore', invalid='ignore')

# Set Windows event loop policy
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Core imports
import ccxt.async_support as ccxt_async
from termcolor import colored

# Configuration and logging
from config import (
    exchange_config, EXCLUDED_SYMBOLS, TIME_STEPS, TRAIN_IF_NOT_FOUND,
    LEVERAGE, TOP_TRAIN_CRYPTO, TOP_ANALYSIS_CRYPTO, EXPECTED_COLUMNS
)
from logging_config import *

# New modular imports
from bot_config import ConfigManager
from trading import TradingEngine
from backtest import BacktestEngine

# Model and data imports
from model_loader import load_xgboost_model_func
from trainer import train_xgboost_model_wrapper, ensure_trained_models_dir
from trade_manager import get_real_balance
from utils.display_utils import display_selected_symbols


async def initialize_exchange():
    """
    Initialize and synchronize exchange connection with enhanced timestamp handling
    """
    logging.info(colored("🚀 Initializing Bybit exchange connection...", "cyan"))
    
    async_exchange = ccxt_async.bybit(exchange_config)
    
    # Enhanced timestamp synchronization
    logging.info(colored("🕐 TIMESTAMP SYNC: Advanced synchronization with Bybit servers...", "yellow"))
    
    max_sync_attempts = 3
    sync_success = False
    
    for attempt in range(max_sync_attempts):
        try:
            # Load markets and synchronize time
            await async_exchange.load_markets()
            await async_exchange.load_time_difference()
            
            # Verify synchronization quality
            server_time = await async_exchange.fetch_time()
            local_time = async_exchange.milliseconds()
            time_diff = abs(server_time - local_time)
            
            logging.info(colored(f"⏰ Sync attempt {attempt + 1}: Server={server_time}, Local={local_time}, Diff={time_diff}ms", "cyan"))
            
            if time_diff <= 2000:  # Excellent sync
                logging.info(colored(f"✅ TIMESTAMP SYNC SUCCESS: Difference {time_diff}ms (excellent)", "green"))
                sync_success = True
                break
            elif time_diff <= 5000:  # Acceptable sync
                logging.info(colored(f"✅ TIMESTAMP SYNC OK: Difference {time_diff}ms (acceptable)", "green"))
                sync_success = True
                break
            else:
                logging.warning(colored(f"⚠️ Large time difference: {time_diff}ms, retry {attempt + 1}/{max_sync_attempts}", "yellow"))
                if attempt < max_sync_attempts - 1:
                    await asyncio.sleep(1)
                
        except Exception as sync_error:
            logging.error(colored(f"❌ Sync attempt {attempt + 1} failed: {sync_error}", "red"))
            if attempt < max_sync_attempts - 1:
                await asyncio.sleep(2)
    
    if not sync_success:
        logging.warning(colored("⚠️ TIMESTAMP SYNC: Issues detected, continuing with extended recv_window", "yellow"))
        logging.info(colored("💡 TIP: Consider synchronizing system clock with 'w32tm /resync /force'", "cyan"))
    
    # Final connection test
    try:
        test_balance = await async_exchange.fetch_balance()
        logging.info(colored("🎯 BYBIT CONNECTION: API test successful - stable connection", "green"))
    except Exception as test_error:
        error_str = str(test_error).lower()
        if "timestamp" in error_str or "recv_window" in error_str:
            logging.error(colored("🚨 TIMESTAMP ISSUE PERSISTS: Check system synchronization", "red"))
            logging.info(colored("🔧 SOLUTIONS: 1) w32tm /resync /force, 2) Restart system, 3) Check timezone", "yellow"))
        else:
            logging.warning(colored(f"⚠️ Connection test failed (may be normal): {test_error}", "yellow"))
    
    return async_exchange


async def initialize_models(config_manager, top_symbols_training):
    """
    Initialize XGBoost models for all enabled timeframes
    """
    ensure_trained_models_dir()
    
    logging.info(colored("🧠 Initializing ML models...", "cyan"))
    
    xgb_models = {}
    xgb_scalers = {}
    model_status = {}
    
    for tf in config_manager.get_timeframes():
        # Load existing model
        xgb_models[tf], xgb_scalers[tf] = await asyncio.to_thread(load_xgboost_model_func, tf)
    
        if not xgb_models[tf]:
            if TRAIN_IF_NOT_FOUND:
                logging.info(colored(f"🎯 Training new model for {tf}", "yellow"))
                
                xgb_models[tf], xgb_scalers[tf], training_metrics = await train_xgboost_model_wrapper(
                    top_symbols_training, None, timestep=TIME_STEPS, 
                    timeframe=tf, use_future_returns=True
                )
                
                if xgb_models[tf] and training_metrics:
                    logging.info(colored(f"✅ Model trained for {tf}: Accuracy {training_metrics.get('val_accuracy', 0):.3f}", "green"))
                    model_status[tf] = True
                    
                    # Optional: Validate model with backtest (if needed)
                    # backtest_engine = BacktestEngine()
                    # await backtest_engine.validate_model_performance(top_symbols_training[0], tf, exchange, xgb_models[tf], xgb_scalers[tf])
                else:
                    model_status[tf] = False
                    
            else:
                raise Exception(f"XGBoost model for timeframe {tf} not available. Train models first.")
        else:
            model_status[tf] = True

    # Display model status
    working_models = sum(1 for status in model_status.values() if status)
    total_models = len(config_manager.get_timeframes())
    
    logging.info(colored("=" * 50, "green"))
    logging.info(colored("🤖 ML MODELS STATUS", "green", attrs=['bold']))
    
    for tf in config_manager.get_timeframes():
        status_emoji = "✅" if model_status.get(tf, False) else "❌"
        status_text = colored("READY", "green") if model_status.get(tf, False) else colored("FAILED", "red")
        logging.info(colored(f"  {tf:>4}: {status_emoji} {status_text}", "white"))
    
    logging.info(colored(f"🎯 Status: {working_models}/{total_models} models ready for parallel prediction", "green"))
    logging.info(colored("=" * 50, "green"))
    
    return xgb_models, xgb_scalers


async def main():
    """
    Main entry point for the restructured trading bot
    """
    try:
        logging.info(colored("🚀 Starting Restructured Trading Bot - Live Trading Focus", "cyan"))
        
        # Initialize configuration
        config_manager = ConfigManager()
        selected_timeframes, selected_models, demo_mode = config_manager.select_config()
        
        logging.info(colored(f"⚙️ Configuration: {len(selected_timeframes)} timeframes, {'DEMO' if demo_mode else 'LIVE'} mode", "cyan"))
        
        # Initialize exchange
        async_exchange = await initialize_exchange()
        
        # Initialize trading engine
        trading_engine = TradingEngine(config_manager)
        
        # Initialize market data and get top symbols
        min_amounts = await trading_engine.market_analyzer.initialize_markets(
            async_exchange, TOP_ANALYSIS_CRYPTO, EXCLUDED_SYMBOLS
        )
        
        # Get symbols for training (if needed)
        top_symbols_training = trading_engine.market_analyzer.get_top_symbols()[:TOP_TRAIN_CRYPTO]
        
        # Display selected symbols
        display_selected_symbols(
            trading_engine.market_analyzer.get_top_symbols(), 
            "SYMBOLS FOR LIVE ANALYSIS"
        )
        
        logging.info(f"{colored('Training symbols:', 'cyan')} {len(top_symbols_training)}")
        logging.info(f"{colored('Analysis symbols:', 'cyan')} {len(trading_engine.market_analyzer.get_top_symbols())}")
        
        # Initialize ML models
        xgb_models, xgb_scalers = await initialize_models(config_manager, top_symbols_training)
        
        # Initialize fresh session
        await trading_engine.initialize_session(async_exchange)
        
        logging.info(colored("🎯 All systems initialized - starting continuous trading...", "green"))
        
        # Start continuous trading
        await trading_engine.run_continuous_trading(async_exchange, xgb_models, xgb_scalers)
        
    except KeyboardInterrupt:
        logging.info(colored("Interrupt signal received. Shutting down...", "red"))
    except Exception as e:
        error_msg = str(e)
        logging.error(f"{colored('Error in main loop:', 'red')} {error_msg}")
        
        # Enhanced error recovery
        if "invalid request, please check your server timestamp" in error_msg:
            logging.warning(colored("⚠️ Timestamp error detected. Attempting recovery...", "yellow"))
            try:
                await async_exchange.load_time_difference()
                await async_exchange.load_markets()
                logging.info(colored("✅ Exchange time synchronization recovered", "green"))
                await asyncio.sleep(10)
            except Exception as recovery_error:
                logging.error(f"❌ Recovery failed: {recovery_error}")
                logging.info(colored("🔄 Attempting full restart as last resort...", "red"))
                os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            logging.warning(colored(f"⚠️ Non-critical error in main loop, continuing after delay", "yellow"))
            await asyncio.sleep(30)
    finally:
        if 'async_exchange' in locals():
            await async_exchange.close()
        logging.info(colored("Program terminated.", "red"))


if __name__ == "__main__":
    asyncio.run(main())
