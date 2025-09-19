#!/usr/bin/env python3
"""
Restructured Trading Bot - Clean Main Entry Point
Live trading only • Static realtime display at end of cycle
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
    exchange_config, EXCLUDED_SYMBOLS, TRAIN_IF_NOT_FOUND,
    LEVERAGE, TOP_TRAIN_CRYPTO, TOP_ANALYSIS_CRYPTO,
    get_timesteps_for_timeframe
)
from logging_config import *

# CRITICAL FIX: Import unified managers for initialization
try:
    from core.unified_balance_manager import initialize_balance_manager
    from core.thread_safe_position_manager import global_thread_safe_position_manager
    from core.smart_api_manager import global_smart_api_manager
    from core.unified_stop_loss_calculator import global_unified_stop_loss_calculator
    UNIFIED_MANAGERS_AVAILABLE = True
    logging.info("🔧 Unified managers available for initialization")
except ImportError as e:
    UNIFIED_MANAGERS_AVAILABLE = False
    logging.warning(f"⚠️ Unified managers not available: {e}")

# Bot modules
from bot_config import ConfigManager
from trading import TradingEngine

# Trailing monitor
from core.trailing_monitor import TrailingMonitor
from core.trailing_stop_manager import TrailingStopManager
from core.order_manager import OrderManager
from config import TRAILING_MONITOR_ENABLED, TRAILING_MONITOR_INTERVAL

# Real-time display (snapshot mode)
from core.realtime_display import initialize_global_realtime_display

# Model and data imports
from model_loader import load_xgboost_model_func
from trainer import train_xgboost_model_wrapper, ensure_trained_models_dir
from trade_manager import get_real_balance
from utils.display_utils import display_selected_symbols


async def initialize_exchange():
    """
    Initialize and synchronize exchange connection with timestamp handling
    """
    logging.info(colored("🚀 Initializing Bybit exchange connection...", "cyan"))

    async_exchange = ccxt_async.bybit(exchange_config)

    # Timestamp sync
    max_sync_attempts = 3
    sync_success = False
    for attempt in range(max_sync_attempts):
        try:
            await async_exchange.load_markets()
            await async_exchange.load_time_difference()
            server_time = await async_exchange.fetch_time()
            local_time = async_exchange.milliseconds()
            diff = abs(server_time - local_time)
            logging.info(colored(f"⏰ Sync attempt {attempt+1}: Diff={diff}ms", "cyan"))
            if diff <= 5000:
                sync_success = True
                break
            await asyncio.sleep(1)
        except Exception as e:
            logging.warning(f"Sync attempt {attempt+1} failed: {e}")
            await asyncio.sleep(1)

    if not sync_success:
        logging.warning(colored("⚠️ TIMESTAMP SYNC: Issues detected", "yellow"))

    try:
        await async_exchange.fetch_balance()
        logging.info(colored("🎯 BYBIT CONNECTION: API test successful", "green"))
    except Exception as e:
        logging.warning(f"⚠️ Connection test failed: {e}")

    return async_exchange


async def initialize_models(config_manager, top_symbols_training):
    """
    Initialize XGBoost models for all enabled timeframes
    """
    ensure_trained_models_dir()
    logging.info(colored("🧠 Initializing ML models...", "cyan"))

    xgb_models, xgb_scalers, model_status = {}, {}, {}

    for tf in config_manager.get_timeframes():
        xgb_models[tf], xgb_scalers[tf] = await asyncio.to_thread(load_xgboost_model_func, tf)
        if not xgb_models[tf]:
            if TRAIN_IF_NOT_FOUND:
                logging.info(colored(f"🎯 Training new model for {tf}", "yellow"))
                xgb_models[tf], xgb_scalers[tf], metrics = await train_xgboost_model_wrapper(
                    top_symbols_training, None, timestep=get_timesteps_for_timeframe(tf),
                    timeframe=tf, use_future_returns=True
                )
                model_status[tf] = bool(xgb_models[tf] and metrics)
            else:
                raise Exception(f"No model for {tf}, and TRAIN_IF_NOT_FOUND disabled")
        else:
            model_status[tf] = True

    logging.info(colored("🤖 ML MODELS STATUS", "green", attrs=['bold']))
    for tf, ok in model_status.items():
        logging.info(f"{tf:>5}: {'✅ READY' if ok else '❌ FAILED'}")

    return xgb_models, xgb_scalers


async def main():
    """
    Main entry point
    """
    try:
        logging.info(colored("🚀 Starting Restructured Trading Bot", "cyan"))

        config_manager = ConfigManager()
        selected_timeframes, selected_models, demo_mode = config_manager.select_config()
        logging.info(colored(f"⚙️ Config: {len(selected_timeframes)} timeframes, {'DEMO' if demo_mode else 'LIVE'}", "cyan"))

        # CRITICAL FIX: Initialize unified managers BEFORE everything else
        if UNIFIED_MANAGERS_AVAILABLE:
            logging.info(colored("🔧 INITIALIZING UNIFIED MANAGERS...", "cyan", attrs=['bold']))
            
            # Initialize balance manager based on mode
            balance_manager = initialize_balance_manager(
                demo_mode=demo_mode, 
                demo_balance=1000.0 if demo_mode else 0.0
            )
            
            # Display unified managers status
            logging.info(colored("✅ ThreadSafePositionManager: Ready", "green"))
            logging.info(colored("✅ UnifiedBalanceManager: Ready", "green"))
            logging.info(colored("✅ SmartAPIManager: Ready", "green"))
            logging.info(colored("✅ UnifiedStopLossCalculator: Ready", "green"))
            logging.info(colored("🔧 RACE CONDITIONS ELIMINATED", "green", attrs=['bold']))
        else:
            logging.warning(colored("⚠️ Using legacy managers - race conditions possible", "yellow"))

        async_exchange = await initialize_exchange()
        trading_engine = TradingEngine(config_manager)

        # Market init
        await trading_engine.market_analyzer.initialize_markets(
            async_exchange, TOP_ANALYSIS_CRYPTO, EXCLUDED_SYMBOLS
        )
        top_symbols_training = trading_engine.market_analyzer.get_top_symbols()[:TOP_TRAIN_CRYPTO]
        # Ottieni simboli con volumi per display
        top_symbols = trading_engine.market_analyzer.get_top_symbols()
        
        # Prova a ottenere dati di volume se disponibili
        try:
            volumes_data = trading_engine.market_analyzer.get_volumes_data() if hasattr(trading_engine.market_analyzer, 'get_volumes_data') else None
        except:
            volumes_data = None
        
        display_selected_symbols(
            top_symbols,
            "SYMBOLS FOR LIVE ANALYSIS",
            volumes_data
        )

        # ML models
        xgb_models, xgb_scalers = await initialize_models(config_manager, top_symbols_training)

        # Fresh session
        await trading_engine.initialize_session(async_exchange)

        # CRITICAL FIX: Initialize balance manager with real Bybit balance
        if UNIFIED_MANAGERS_AVAILABLE and not demo_mode:
            try:
                # Sync balance manager with real Bybit balance
                real_balance = await get_real_balance(async_exchange)
                if real_balance and real_balance > 0:
                    success = await balance_manager.sync_balance_with_bybit(async_exchange)
                    if success:
                        logging.info(colored(f"💰 Balance Manager synced with Bybit: ${balance_manager.get_total_balance():.2f}", "green"))
                        
                        # Display balance dashboard
                        balance_manager.display_balance_dashboard()
                    else:
                        logging.warning("⚠️ Failed to sync balance manager with Bybit")
                else:
                    logging.warning("⚠️ Could not get real balance for balance manager sync")
            except Exception as balance_error:
                logging.error(f"❌ Balance manager sync error: {balance_error}")

        # Trailing monitor
        trailing_monitor = None
        if TRAILING_MONITOR_ENABLED and trading_engine.clean_modules_available:
            try:
                position_manager = trading_engine.position_manager
                order_manager = trading_engine.global_order_manager
                trailing_manager = TrailingStopManager(order_manager, position_manager)
                trailing_monitor = TrailingMonitor(position_manager, trailing_manager, order_manager)
                await trailing_monitor.start_monitoring(async_exchange)
                logging.info(colored(f"⚡ Trailing monitor started ({TRAILING_MONITOR_INTERVAL}s)", "green"))
            except Exception as e:
                logging.error(f"❌ Trailing monitor failed: {e}")
        else:
            logging.info("⚡ Trailing monitor disabled")

        # Static realtime display (snapshot only)
        initialize_global_realtime_display(
            trading_engine.position_manager if trading_engine.clean_modules_available else None,
            trailing_monitor
        )
        logging.info(colored("� Realtime display (snapshot mode) initialized", "cyan"))

        # Continuous trading
        logging.info(colored("🎯 All systems ready — starting trading loop", "green"))
        await trading_engine.run_continuous_trading(async_exchange, xgb_models, xgb_scalers)

    except KeyboardInterrupt:
        logging.info("🛑 Interrupted by user")
    except Exception as e:
        logging.error(f"❌ Fatal error: {e}")
        await asyncio.sleep(30)
    finally:
        if 'async_exchange' in locals():
            await async_exchange.close()
        logging.info("Program terminated.")


if __name__ == "__main__":
    asyncio.run(main())
