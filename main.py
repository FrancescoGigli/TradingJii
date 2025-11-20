#!/usr/bin/env python3
"""
Restructured Trading Bot - Clean Main Entry Point
Live trading only • Static realtime display at end of cycle
"""


import sys, io

# Forza UTF-8 su Windows (per emoji e simboli)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import os
import signal
import numpy as np
import warnings
import asyncio
import logging
from termcolor import colored

# Suppress runtime warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="ta")
np.seterr(divide="ignore", invalid="ignore")

# NOTE: Windows loop policy NOT set when using qasync
# qasync QEventLoop handles Windows compatibility automatically

# Core imports
import ccxt.async_support as ccxt_async

# Configuration and logging
import config
from config import (
    exchange_config,
    EXCLUDED_SYMBOLS,
    TRAIN_IF_NOT_FOUND,
    LEVERAGE,
    TOP_TRAIN_CRYPTO,
    TOP_ANALYSIS_CRYPTO,
    get_timesteps_for_timeframe,
    DEMO_MODE,
    DEMO_BALANCE,
)
from logging_config import *

# Startup display system
from core.startup_display import global_startup_collector


# Unified managers
try:
    from core.thread_safe_position_manager import global_thread_safe_position_manager
    from core.smart_api_manager import global_smart_api_manager

    UNIFIED_MANAGERS_AVAILABLE = True
    logging.debug("🔧 Unified managers available for initialization")
    global_startup_collector.set_core_system("position_manager", "FILE PERSISTENCE")
except ImportError as e:
    UNIFIED_MANAGERS_AVAILABLE = False
    logging.warning(f"⚠️ Unified managers not available: {e}")

# Bot modules
from bot_config import ConfigManager
from trading import TradingEngine

# Realtime display
from core.realtime_display import initialize_global_realtime_display

# Trade history logger with Bybit sync
from core.trade_history_logger import global_trade_history_logger

# Models
from model_loader import load_xgboost_model_func
from trainer import train_xgboost_model_wrapper, ensure_trained_models_dir
from trade_manager import get_real_balance
from utils.display_utils import display_selected_symbols


async def initialize_exchange():
    """Initialize and test exchange connection with robust timestamp sync"""
    # Use centralized time sync manager instead of duplicating logic
    from core.time_sync_manager import global_time_sync_manager
    
    if config.DEMO_MODE:
        logging.info(colored("🧪 DEMO MODE: Exchange not required", "yellow"))
        return None

    logging.debug(colored("🚀 Initializing Bybit exchange connection...", "cyan"))
    
    # Configure aiohttp to use ThreadedResolver (no aiodns dependency)
    import aiohttp
    from aiohttp.resolver import ThreadedResolver
    
    resolver = ThreadedResolver()
    connector = aiohttp.TCPConnector(resolver=resolver, use_dns_cache=False)
    session = aiohttp.ClientSession(connector=connector)
    
    # Create exchange with custom session
    exchange_config_with_session = {**exchange_config, 'session': session}
    async_exchange = ccxt_async.bybit(exchange_config_with_session)

    # Phase 1: Time synchronization using centralized manager
    logging.debug("⏰ Starting time sync...")
    sync_success = await global_time_sync_manager.initialize_exchange_time_sync(async_exchange)
    
    if not sync_success:
        error_msg = "Time synchronization failed"
        logging.error(colored(f"❌ {error_msg}", "red"))
        logging.error(colored("💡 Troubleshooting tips:", "yellow"))
        logging.error("   1. Check your Windows time sync: Settings > Time & Language > Date & Time")
        logging.error("   2. Enable 'Set time automatically' and sync now")
        logging.error("   3. Restart the bot after fixing time sync")
        logging.error("   4. If issue persists, set MANUAL_TIME_OFFSET in config.py")
        raise RuntimeError(error_msg)

    # Phase 2: Load markets (now safe with synchronized time)
    try:
        await async_exchange.load_markets()
        logging.debug(colored("✅ Markets loaded", "green"))
    except Exception as e:
        logging.error(colored(f"❌ Failed to load markets: {e}", "red"))
        raise RuntimeError(f"Failed to load markets after time sync: {e}")

    # Phase 3: Test authenticated API connection
    try:
        balance = await async_exchange.fetch_balance()
        logging.debug(colored("✅ Bybit authenticated", "green"))
    except Exception as e:
        logging.error(colored(f"❌ Authentication failed: {e}", "red"))
        raise RuntimeError(f"Failed to authenticate with Bybit: {e}")

    # Get time sync stats for logging
    stats = global_time_sync_manager.get_stats()
    final_time_diff = async_exchange.options.get('timeDifference', 0)
    logging.debug(f"Time offset: {final_time_diff}ms")
    
    # Register exchange connection data
    global_startup_collector.set_exchange_connection( 
        time_offset=final_time_diff,
        markets=True,
        auth=True
    )
    
    return async_exchange


async def initialize_models(config_manager, top_symbols_training, exchange):
    """Load or train ML models"""
    ensure_trained_models_dir()
    logging.debug(colored("🧠 Initializing ML models...", "cyan"))

    xgb_models, xgb_scalers, model_status = {}, {}, {}
    for tf in config_manager.get_timeframes():
        xgb_models[tf], xgb_scalers[tf] = await asyncio.to_thread(load_xgboost_model_func, tf)
        if not xgb_models[tf]:
            if TRAIN_IF_NOT_FOUND:
                logging.info(colored(f"🎯 Training new model for {tf}", "yellow"))
                xgb_models[tf], xgb_scalers[tf], metrics = await train_xgboost_model_wrapper(
                    top_symbols_training,
                    exchange,  # CRITICAL FIX: Pass exchange for data fetching during training
                    timestep=get_timesteps_for_timeframe(tf),
                    timeframe=tf,
                    use_future_returns=True,
                )
                model_status[tf] = bool(xgb_models[tf] and metrics)
            else:
                raise RuntimeError(f"No model for {tf}, and TRAIN_IF_NOT_FOUND disabled")
        else:
            model_status[tf] = True

    logging.debug(colored("🤖 ML MODELS STATUS", "green", attrs=["bold"]))
    for tf, ok in model_status.items():
        logging.debug(f"{tf:>5}: {'✅ READY' if ok else '❌ FAILED'}")

    return xgb_models, xgb_scalers


async def main():
    """Main entry point"""
    try:
        logging.debug("🚀 Starting Trading Bot")

        config_manager = ConfigManager()
        selected_timeframes, selected_models, demo_mode = config_manager.select_config()
        
        # Register core systems
        global_startup_collector.set_core_system("signal_processor", "")
        global_startup_collector.set_core_system("trade_manager", "")
        global_startup_collector.set_core_system("trade_logger", "data_cache/trade_decisions.db")
        global_startup_collector.set_core_system("session_stats", "")
        
        # Register configuration
        mode_str = "LIVE (Trading reale)" if not demo_mode else "DEMO MODE"
        global_startup_collector.set_configuration(
            excluded_count=len(EXCLUDED_SYMBOLS),
            excluded_list=EXCLUDED_SYMBOLS,
            mode=mode_str,
            timeframes=selected_timeframes,
            model_type="XGBoost"
        )

        async_exchange = await initialize_exchange()
        
        trading_engine = TradingEngine(config_manager)

        # Market init
        await trading_engine.market_analyzer.initialize_markets(
            async_exchange, TOP_ANALYSIS_CRYPTO, EXCLUDED_SYMBOLS
        )
        top_symbols_training = trading_engine.market_analyzer.get_top_symbols()[:TOP_TRAIN_CRYPTO]
        top_symbols = trading_engine.market_analyzer.get_top_symbols()

        try:
            volumes_data = (
                trading_engine.market_analyzer.get_volumes_data()
                if hasattr(trading_engine.market_analyzer, "get_volumes_data")
                else None
            )
        except Exception:
            volumes_data = None

        display_selected_symbols(top_symbols, "SYMBOLS FOR LIVE ANALYSIS", volumes_data)

        # ML models
        xgb_models, xgb_scalers = await initialize_models(config_manager, top_symbols_training, async_exchange)

        # Fresh session
        await trading_engine.initialize_session(async_exchange)

        # Balance sync removed for cleaner startup
        logging.debug("🔧 Balance sync disabled - using direct balance queries when needed")

        # 🆕 FRESH SESSION START - No historical data sync
        # Reset closed positions tracker for this session only
        logging.info(colored("🆕 FRESH SESSION START - Tracking only trades closed in THIS session", "green", attrs=["bold"]))
        logging.info(colored("📊 Historical data sync DISABLED - Clean session tracking", "cyan"))
        
        # Reset trade history for fresh session (optional - keeps file but marks session start)
        try:
            from datetime import datetime
            session_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.info(colored(f"⏰ Session started: {session_start}", "white"))
        except Exception:
            pass
        
        # Register modules initialization
        global_startup_collector.set_modules(
            orchestrator=trading_engine.clean_modules_available,
            dashboard="PyQt6 + qasync",
            subsystems=["stats", "dashboard", "trailing"]
        )
        
        # Register market analysis
        global_startup_collector.set_market_analysis(
            total_symbols=TOP_ANALYSIS_CRYPTO,
            active_symbols=len(top_symbols)
        )
        
        # Static realtime display
        initialize_global_realtime_display(
            trading_engine.position_manager if trading_engine.clean_modules_available else None
        )
        logging.debug(colored("📊 Realtime display initialized", "cyan"))

        # Display startup summary (replaces old logging)
        global_startup_collector.display_startup_summary()

        # Trading loop
        await trading_engine.run_continuous_trading(async_exchange, xgb_models, xgb_scalers)

    except KeyboardInterrupt:
        logging.info("� Interrupted by user")
    except Exception as e:
        logging.error(f"❌ Fatal error: {e}", exc_info=True)
        await asyncio.sleep(30)
    finally:
        if "async_exchange" in locals() and async_exchange:
            await async_exchange.close()
        logging.info("Program terminated.")


if __name__ == "__main__":
    # Run bot with standard asyncio (no PyQt6/qasync needed)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("👋 Interrupted by user")
