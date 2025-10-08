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
import numpy as np
import warnings
import asyncio
import logging
from termcolor import colored

# Suppress runtime warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="ta")
np.seterr(divide="ignore", invalid="ignore")

# Fix Windows loop policy
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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

# Unified managers
try:
    from core.thread_safe_position_manager import global_thread_safe_position_manager
    from core.smart_api_manager import global_smart_api_manager

    UNIFIED_MANAGERS_AVAILABLE = True
    logging.debug("🔧 Unified managers available for initialization")
except ImportError as e:
    UNIFIED_MANAGERS_AVAILABLE = False
    logging.warning(f"⚠️ Unified managers not available: {e}")

# Bot modules
from bot_config import ConfigManager
from trading import TradingEngine

# Realtime display
from core.realtime_display import initialize_global_realtime_display

# Models
from model_loader import load_xgboost_model_func
from trainer import train_xgboost_model_wrapper, ensure_trained_models_dir
from trade_manager import get_real_balance
from utils.display_utils import display_selected_symbols


async def initialize_exchange():
    """Initialize and test exchange connection with robust timestamp sync"""
    if DEMO_MODE:
        logging.info(colored("🧪 DEMO MODE: Exchange not required", "yellow"))
        return None

    logging.info(colored("🚀 Initializing Bybit exchange connection...", "cyan"))
    async_exchange = ccxt_async.bybit(exchange_config)

    # Import time sync configuration
    from config import (
        TIME_SYNC_MAX_RETRIES,
        TIME_SYNC_RETRY_DELAY,
        TIME_SYNC_NORMAL_RECV_WINDOW,
        MANUAL_TIME_OFFSET
    )

    # Phase 1: Pre-authentication time synchronization
    # This MUST happen before any authenticated API calls (like load_markets)
    sync_success = False
    final_time_diff = 0
    
    logging.info(colored("⏰ Phase 1: Pre-authentication time sync", "cyan"))
    
    for attempt in range(1, TIME_SYNC_MAX_RETRIES + 1):
        try:
            logging.info(f"⏰ Sync attempt {attempt}/{TIME_SYNC_MAX_RETRIES}...")
            
            # Step 1: Fetch server time using public API (no authentication required)
            server_time = await async_exchange.fetch_time()
            local_time = async_exchange.milliseconds()
            
            # Step 2: Calculate time difference
            time_diff = server_time - local_time
            
            logging.info(f"📊 Time analysis:")
            logging.info(f"   Local time:  {local_time} ms")
            logging.info(f"   Server time: {server_time} ms")
            logging.info(f"   Difference:  {time_diff} ms ({time_diff/1000:.3f} seconds)")
            
            # Step 3: Apply manual offset if configured
            if MANUAL_TIME_OFFSET is not None:
                logging.info(f"🔧 Applying manual time offset: {MANUAL_TIME_OFFSET} ms")
                time_diff += MANUAL_TIME_OFFSET
            
            # Step 4: Store the time difference in exchange options
            async_exchange.options['timeDifference'] = time_diff
            final_time_diff = time_diff
            
            # Step 5: Verify the sync by fetching time again
            await asyncio.sleep(0.5)  # Small delay to account for network latency
            verify_server_time = await async_exchange.fetch_time()
            verify_local_time = async_exchange.milliseconds()
            verify_adjusted_time = verify_local_time + time_diff
            verify_diff = abs(verify_server_time - verify_adjusted_time)
            
            logging.info(f"✅ Verification: adjusted time diff = {verify_diff} ms")
            
            # Accept if difference is less than 2 seconds after adjustment
            if verify_diff < 2000:
                logging.info(colored(f"✅ Time sync successful! Offset applied: {time_diff} ms", "green"))
                sync_success = True
                break
            else:
                logging.warning(f"⚠️ Verification failed: adjusted diff too large ({verify_diff} ms)")
                if attempt < TIME_SYNC_MAX_RETRIES:
                    delay = TIME_SYNC_RETRY_DELAY * attempt  # Exponential backoff
                    logging.info(f"⏳ Waiting {delay}s before retry...")
                    await asyncio.sleep(delay)
                    
        except Exception as e:
            logging.error(f"❌ Sync attempt {attempt} failed: {e}")
            if attempt < TIME_SYNC_MAX_RETRIES:
                delay = TIME_SYNC_RETRY_DELAY * attempt  # Exponential backoff
                logging.info(f"⏳ Waiting {delay}s before retry...")
                await asyncio.sleep(delay)
    
    if not sync_success:
        error_msg = f"Time synchronization failed after {TIME_SYNC_MAX_RETRIES} attempts"
        logging.error(colored(f"❌ {error_msg}", "red"))
        logging.error(colored("💡 Troubleshooting tips:", "yellow"))
        logging.error("   1. Check your Windows time sync: Settings > Time & Language > Date & Time")
        logging.error("   2. Enable 'Set time automatically' and sync now")
        logging.error("   3. Restart the bot after fixing time sync")
        logging.error("   4. If issue persists, set MANUAL_TIME_OFFSET in config.py")
        raise RuntimeError(error_msg)

    # Phase 2: Reduce recv_window for tighter security in normal operations
    logging.info(colored("⏰ Phase 2: Optimizing recv_window for normal operations", "cyan"))
    async_exchange.options['recvWindow'] = TIME_SYNC_NORMAL_RECV_WINDOW
    logging.info(f"✅ recv_window reduced to {TIME_SYNC_NORMAL_RECV_WINDOW} ms for enhanced security")

    # Phase 3: Load markets (now safe with synchronized time)
    logging.info(colored("⏰ Phase 3: Loading markets with synchronized time", "cyan"))
    try:
        await async_exchange.load_markets()
        logging.info(colored("✅ Markets loaded successfully", "green"))
    except Exception as e:
        logging.error(colored(f"❌ Failed to load markets: {e}", "red"))
        raise RuntimeError(f"Failed to load markets after time sync: {e}")

    # Phase 4: Test authenticated API connection
    logging.info(colored("⏰ Phase 4: Testing authenticated API access", "cyan"))
    try:
        balance = await async_exchange.fetch_balance()
        logging.info(colored("✅ Authenticated API test successful", "green"))
        logging.info(f"📊 Account balance fetched: {len(balance.get('info', {}))} currencies")
    except Exception as e:
        logging.error(colored(f"❌ Authenticated API test failed: {e}", "red"))
        raise RuntimeError(f"Failed to authenticate with Bybit: {e}")

    logging.info(colored("🎯 BYBIT CONNECTION: All phases completed successfully", "green", attrs=["bold"]))
    logging.info(f"⚙️  Final time offset: {final_time_diff} ms ({final_time_diff/1000:.3f}s)")
    
    return async_exchange


async def initialize_models(config_manager, top_symbols_training):
    """Load or train ML models"""
    ensure_trained_models_dir()
    logging.info(colored("🧠 Initializing ML models...", "cyan"))

    xgb_models, xgb_scalers, model_status = {}, {}, {}
    for tf in config_manager.get_timeframes():
        xgb_models[tf], xgb_scalers[tf] = await asyncio.to_thread(load_xgboost_model_func, tf)
        if not xgb_models[tf]:
            if TRAIN_IF_NOT_FOUND:
                logging.info(colored(f"🎯 Training new model for {tf}", "yellow"))
                xgb_models[tf], xgb_scalers[tf], metrics = await train_xgboost_model_wrapper(
                    top_symbols_training,
                    None,
                    timestep=get_timesteps_for_timeframe(tf),
                    timeframe=tf,
                    use_future_returns=True,
                )
                model_status[tf] = bool(xgb_models[tf] and metrics)
            else:
                raise RuntimeError(f"No model for {tf}, and TRAIN_IF_NOT_FOUND disabled")
        else:
            model_status[tf] = True

    logging.info(colored("🤖 ML MODELS STATUS", "green", attrs=["bold"]))
    for tf, ok in model_status.items():
        logging.info(f"{tf:>5}: {'✅ READY' if ok else '❌ FAILED'}")

    return xgb_models, xgb_scalers


async def main():
    """Main entry point"""
    try:
        logging.info(colored("🚀 Starting Trading Bot", "cyan"))

        config_manager = ConfigManager()
        selected_timeframes, selected_models, demo_mode = config_manager.select_config()
        logging.info(
            colored(
                f"⚙️ Config: {len(selected_timeframes)} timeframes, {'DEMO' if demo_mode else 'LIVE'}",
                "cyan",
            )
        )

        async_exchange = await initialize_exchange()
        
        # 🧹 FRESH START MODE: Close all positions and cleanup files before starting
        if config.FRESH_START_MODE:
            from core.fresh_start_manager import execute_fresh_start
            logging.info(colored("🧹 Fresh Start Mode is ENABLED", "yellow", attrs=['bold']))
            
            fresh_start_success = await execute_fresh_start(
                exchange=async_exchange,
                options=config.FRESH_START_OPTIONS
            )
            
            if not fresh_start_success:
                logging.error(colored("❌ Fresh start failed - check logs above", "red"))
                logging.warning(colored("⚠️ Proceeding anyway, but state may be inconsistent", "yellow"))
            
            # Small delay to ensure all operations completed
            await asyncio.sleep(2)
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
        xgb_models, xgb_scalers = await initialize_models(config_manager, top_symbols_training)

        # Fresh session
        await trading_engine.initialize_session(async_exchange)

        # Balance sync removed for cleaner startup
        logging.debug("🔧 Balance sync disabled - using direct balance queries when needed")

        # Static realtime display
        initialize_global_realtime_display(
            trading_engine.position_manager if trading_engine.clean_modules_available else None
        )
        logging.debug(colored("📊 Realtime display initialized", "cyan"))

        # Trading loop
        logging.info(colored("🎯 All systems ready — starting trading loop", "green"))
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
    asyncio.run(main())
