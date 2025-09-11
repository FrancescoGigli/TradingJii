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

# High-frequency trailing monitor
from core.trailing_monitor import TrailingMonitor
from core.trailing_stop_manager import TrailingStopManager
from core.order_manager import OrderManager
from config import TRAILING_MONITOR_ENABLED, TRAILING_MONITOR_INTERVAL

# Real-time position display
from core.realtime_display import initialize_global_realtime_display
from config import REALTIME_DISPLAY_ENABLED, REALTIME_DISPLAY_INTERVAL

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
            await async_exchange.load_markets()
            await async_exchange.load_time_difference()
            
            server_time = await async_exchange.fetch_time()
            local_time = async_exchange.milliseconds()
            time_diff = abs(server_time - local_time)
            
            logging.info(colored(f"⏰ Sync attempt {attempt + 1}: Server={server_time}, Local={local_time}, Diff={time_diff}ms", "cyan"))
            
            if time_diff <= 2000:
                logging.info(colored(f"✅ TIMESTAMP SYNC SUCCESS: Difference {time_diff}ms (excellent)", "green"))
                sync_success = True
                break
            elif time_diff <= 5000:
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
    
    try:
        await async_exchange.fetch_balance()
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
                else:
                    model_status[tf] = False
            else:
                raise Exception(f"XGBoost model for timeframe {tf} not available. Train models first.")
        else:
            model_status[tf] = True

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
        
        config_manager = ConfigManager()
        selected_timeframes, selected_models, demo_mode = config_manager.select_config()
        
        logging.info(colored(f"⚙️ Configuration: {len(selected_timeframes)} timeframes, {'DEMO' if demo_mode else 'LIVE'} mode", "cyan"))
        
        async_exchange = await initialize_exchange()
        trading_engine = TradingEngine(config_manager)
        
        min_amounts = await trading_engine.market_analyzer.initialize_markets(
            async_exchange, TOP_ANALYSIS_CRYPTO, EXCLUDED_SYMBOLS
        )
        
        top_symbols_training = trading_engine.market_analyzer.get_top_symbols()[:TOP_TRAIN_CRYPTO]
        display_selected_symbols(
            trading_engine.market_analyzer.get_top_symbols(), 
            "SYMBOLS FOR LIVE ANALYSIS"
        )
        
        logging.info(f"{colored('Training symbols:', 'cyan')} {len(top_symbols_training)}")
        logging.info(f"{colored('Analysis symbols:', 'cyan')} {len(trading_engine.market_analyzer.get_top_symbols())}")
        
        xgb_models, xgb_scalers = await initialize_models(config_manager, top_symbols_training)
        await trading_engine.initialize_session(async_exchange)
        
        trailing_monitor = None
        if TRAILING_MONITOR_ENABLED:
            try:
                if trading_engine.clean_modules_available:
                    position_manager = trading_engine.position_manager
                    order_manager = trading_engine.global_order_manager
                    trailing_manager = TrailingStopManager(order_manager, position_manager)
                    trailing_monitor = TrailingMonitor(position_manager, trailing_manager, order_manager)
                    await trailing_monitor.start_monitoring(async_exchange)
                    logging.info(colored(f"⚡ HIGH-FREQUENCY TRAILING: Started monitoring every {TRAILING_MONITOR_INTERVAL}s", "green"))
                else:
                    logging.warning(colored("⚠️ Clean modules not available - trailing monitor disabled", "yellow"))
            except Exception as e:
                logging.error(colored(f"❌ Failed to start trailing monitor: {e}", "red"))
        else:
            logging.info(colored("⚡ High-frequency trailing monitor disabled in config", "yellow"))
        
        # 🔥 REAL-TIME DISPLAY
        realtime_display = None
        if REALTIME_DISPLAY_ENABLED:
            try:
                if trading_engine.clean_modules_available:
                    position_manager = trading_engine.position_manager
                    realtime_display = initialize_global_realtime_display(position_manager, trailing_monitor)
                    if realtime_display:
                        await realtime_display.start_display(async_exchange)
                        logging.info(colored("✅ REAL-TIME DISPLAY avviato con successo", "green"))
                    else:
                        logging.error("❌ REAL-TIME DISPLAY non inizializzato")
                else:
                    logging.warning(colored("⚠️ Clean modules not available - real-time display disabled", "yellow"))
            except Exception as e:
                logging.error(colored(f"❌ Failed to start real-time display: {e}", "red"))
            logging.info(colored(f"📊 REAL-TIME DISPLAY: Aggiornamento ogni {REALTIME_DISPLAY_INTERVAL}s", "cyan"))
        else:
            logging.info(colored("📊 Real-time position display disabled in config", "yellow"))
        
        logging.info(colored("🎯 All systems initialized - starting continuous trading...", "green"))
        
        try:
            await trading_engine.run_continuous_trading(async_exchange, xgb_models, xgb_scalers)
        finally:
            if trailing_monitor and trailing_monitor.is_running:
                logging.info(colored("⚡ Stopping high-frequency trailing monitor...", "yellow"))
                await trailing_monitor.stop_monitoring()
            
            if realtime_display and realtime_display.is_running:
                logging.info(colored("📊 Stopping real-time position display...", "yellow"))
                await realtime_display.stop_display()
        
    except KeyboardInterrupt:
        logging.info(colored("Interrupt signal received. Shutting down...", "red"))
    except Exception as e:
        error_msg = str(e)
        logging.error(f"{colored('Error in main loop:', 'red')} {error_msg}")
        await asyncio.sleep(30)
    finally:
        if 'async_exchange' in locals():
            await async_exchange.close()
        logging.info(colored("Program terminated.", "red"))


if __name__ == "__main__":
    asyncio.run(main())
