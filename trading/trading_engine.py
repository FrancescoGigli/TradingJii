"""
Trading Engine for the restructured trading bot
Main orchestrator for the trading process without backtesting overhead
"""

import time
import logging
import asyncio
from termcolor import colored

from trading.market_analyzer import global_market_analyzer
from trading.signal_processor import global_signal_processor
from utils.display_utils import display_top_signals, show_performance_summary
from trade_manager import get_real_balance
import config

# Import realtime_display snapshot
from core.realtime_display import initialize_global_realtime_display

# Import enhanced decision systems
try:
    from core.decision_explainer import global_decision_explainer
    DECISION_EXPLAINER_AVAILABLE = True
except ImportError:
    DECISION_EXPLAINER_AVAILABLE = False
    global_decision_explainer = None

try:
    from core.rl_agent import global_online_learning_manager
    ONLINE_LEARNING_AVAILABLE = bool(global_online_learning_manager)
except ImportError:
    ONLINE_LEARNING_AVAILABLE = False
    global_online_learning_manager = None

# Import Position Safety Manager
try:
    from core.position_safety_manager import global_position_safety_manager
    POSITION_SAFETY_AVAILABLE = True
except ImportError:
    POSITION_SAFETY_AVAILABLE = False
    global_position_safety_manager = None

# Thread-safe position manager (mandatory)
try:
    from core.thread_safe_position_manager import global_thread_safe_position_manager
    THREAD_SAFE_POSITIONS_AVAILABLE = True
    logging.info("🔒 ThreadSafePositionManager integration enabled")
except ImportError:
    THREAD_SAFE_POSITIONS_AVAILABLE = False
    global_thread_safe_position_manager = None
    logging.error("❌ CRITICAL: ThreadSafePositionManager not available — cannot proceed safely")
    raise ImportError("CRITICAL: ThreadSafePositionManager required for unified position management")


class TradingEngine:
    """
    Main trading engine che orchestra l'intero processo di trading
    """

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.first_cycle = True

        # Core components
        self.market_analyzer = global_market_analyzer
        self.signal_processor = global_signal_processor

        # Optional components
        self.database_system_loaded = self._init_database_system()
        self.clean_modules_available = self._init_clean_modules()

    def _init_database_system(self):
        """Initialize database system if available"""
        try:
            from core.database_cache import global_db_cache, display_database_stats
            self.global_db_cache = global_db_cache
            self.display_database_stats = display_database_stats
            return True
        except ImportError:
            logging.warning("⚠️ Database system integration not available")
            return False

    def _init_clean_modules(self):
        """Initialize clean trading modules"""
        try:
            from core.order_manager import global_order_manager
            from core.risk_calculator import global_risk_calculator, MarketData
            from core.trading_orchestrator import global_trading_orchestrator

            position_manager = global_thread_safe_position_manager
            if position_manager is None:
                raise ImportError("ThreadSafePositionManager not available")

            self.global_order_manager = global_order_manager
            self.global_risk_calculator = global_risk_calculator
            self.global_trading_orchestrator = global_trading_orchestrator
            self.position_manager = position_manager
            self.MarketData = MarketData

            logging.info("🔒 Clean trading modules loaded with ThreadSafePositionManager")
            return True
        except ImportError as e:
            logging.error(f"❌ Clean modules not available: {e}")
            return False

    async def initialize_session(self, exchange):
        """
        Initialize fresh session with position sync
        """
        logging.info(colored("🧹 FRESH SESSION STARTUP", "cyan", attrs=['bold']))

        if self.clean_modules_available:
            self.position_manager.reset_session()

        real_balance = None
        if not config.DEMO_MODE:
            real_balance = await get_real_balance(exchange)

        if real_balance and real_balance > 0:
            if self.clean_modules_available:
                self.position_manager.update_real_balance(real_balance)
            logging.info(colored(f"💰 Balance synced: ${real_balance:.2f}", "green"))
        else:
            logging.warning("⚠️ Using fallback balance (demo or zero balance detected)")

        logging.info(colored("✅ Ready for fresh sync", "green"))

        if not config.DEMO_MODE and self.clean_modules_available:
            logging.info(colored("🔄 SYNCING WITH REAL BYBIT POSITIONS", "cyan"))
            try:
                protection_results = await self.global_trading_orchestrator.protect_existing_positions(exchange)
                if protection_results:
                    successful = sum(1 for r in protection_results.values() if r.success)
                    total = len(protection_results)
                    logging.info(colored(f"🛡️ Protected {successful}/{total} existing positions", "cyan"))
                else:
                    logging.info(colored("🆕 No existing positions - starting fresh", "green"))
            except Exception as e:
                logging.warning(f"⚠️ Error during position protection: {e}")

        logging.info(colored("-" * 80, "cyan"))

    # ------------------------------------------------------------------
    # Main trading cycle
    # ------------------------------------------------------------------
    async def run_trading_cycle(self, exchange, xgb_models, xgb_scalers):
        """
        Execute one complete trading cycle with enhanced phase visualization
        """
        from core.enhanced_logging_system import enhanced_logger, cycle_logger, log_separator

        cycle_start_time = time.time()

        try:
            log_separator("═", 100, "cyan")
            enhanced_logger.display_table("🚀 TRADING CYCLE STARTED", "cyan", attrs=['bold'])
            log_separator("═", 100, "cyan")

            # Phase 1: Data Collection
            enhanced_logger.display_table("📈 PHASE 1: DATA COLLECTION & MARKET ANALYSIS", "blue", attrs=['bold'])
            all_symbol_data, complete_symbols, data_fetch_time = await self.market_analyzer.collect_market_data(
                exchange,
                self.config_manager.get_timeframes(),
                config.TOP_ANALYSIS_CRYPTO,
                config.EXCLUDED_SYMBOLS,
            )
            if not complete_symbols:
                enhanced_logger.display_table("⚠️ No symbols with complete data this cycle", "yellow")
                return

            # Phase 2: ML Predictions
            cycle_logger.log_phase(2, "ML PREDICTIONS & AI ANALYSIS", "magenta")
            prediction_results, ml_time = await self.market_analyzer.generate_ml_predictions(
                xgb_models,
                xgb_scalers,
                config.get_timesteps_for_timeframe(self.config_manager.get_default_timeframe()),
            )

            # Phase 3: Signal Processing
            cycle_logger.log_phase(3, "SIGNAL PROCESSING & FILTERING", "yellow")
            self.signal_processor.display_complete_analysis(prediction_results, all_symbol_data)
            all_signals = await self.signal_processor.process_prediction_results(prediction_results, all_symbol_data)

            # Phase 4: Ranking
            cycle_logger.log_phase(4, "RANKING & TOP SIGNAL SELECTION", "green")
            display_top_signals(all_signals, limit=10)

            # Phase 5: Execution
            cycle_logger.log_phase(5, "TRADE EXECUTION", "red")
            await self._execute_signals(exchange, all_signals)

            # Phase 6: Position Management
            cycle_logger.log_phase(6, "POSITION MANAGEMENT & RISK CONTROL", "cyan")
            await self._manage_positions(exchange)

            # Phase 7: Performance Analysis
            cycle_logger.log_phase(7, "PERFORMANCE ANALYSIS & REPORTING", "white")
            cycle_total_time = time.time() - cycle_start_time
            show_performance_summary(
                cycle_total_time,
                data_fetch_time,
                ml_time,
                len(self.market_analyzer.get_top_symbols()),
                len(self.config_manager.get_timeframes()),
                len(complete_symbols),
                self.database_system_loaded,
            )

            # Phase 8: Online Learning (optional)
            if ONLINE_LEARNING_AVAILABLE and global_online_learning_manager:
                await self._handle_online_learning()

            # Phase 9: Realtime Display
            cycle_logger.log_phase(9, "POSITION DISPLAY & PORTFOLIO OVERVIEW", "green")
            await self._update_realtime_display(exchange)

            # Cycle complete
            log_separator("═", 100, "green")
            enhanced_logger.display_table("✅ TRADING CYCLE COMPLETED SUCCESSFULLY", "green", attrs=['bold'])
            enhanced_logger.display_table(f"⏱️ Total cycle time: {cycle_total_time:.1f}s", "green")
            log_separator("═", 100, "green")

        except Exception as e:
            logging.error(f"❌ Error in trading cycle: {e}", exc_info=True)
            raise

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _execute_signals(self, exchange, all_signals):
        """Execute trading signals with enhanced logging"""
        from core.enhanced_logging_system import enhanced_logger

        if not all_signals:
            enhanced_logger.display_table("😐 No signals to execute this cycle", "yellow")
            return

        usdt_balance = await get_real_balance(exchange) if not config.DEMO_MODE else config.DEMO_BALANCE
        if usdt_balance is None:
            enhanced_logger.display_table("⚠️ Failed to get balance", "yellow")
            return

        # Position limits
        open_positions_count = (
            self.position_manager.get_position_count() if self.clean_modules_available else 0
        )
        max_positions = max(0, config.MAX_CONCURRENT_POSITIONS - open_positions_count)
        signals_to_execute = all_signals[: min(max_positions, len(all_signals))]
        if not signals_to_execute:
            enhanced_logger.display_table("⚠️ No slots for new positions", "yellow")
            return

        enhanced_logger.display_table(f"🎯 Executing {len(signals_to_execute)} signals", "red")
        await self._setup_trading_parameters(exchange, signals_to_execute)

        # Execute each signal
        executed_trades = 0
        for i, signal in enumerate(signals_to_execute, 1):
            try:
                if not self.clean_modules_available:
                    logging.warning("⚠️ Clean modules not available, skipping execution")
                    break

                symbol = signal["symbol"]

                # Skip if already open
                if self.position_manager.has_position_for_symbol(symbol):
                    logging.info(colored(f"📝 {i}/{len(signals_to_execute)} {symbol}: Position exists, skipping", "cyan"))
                    continue

                # Risk and execution
                df = signal["dataframes"][self.config_manager.get_default_timeframe()]
                if df is None or len(df) == 0:
                    logging.warning(f"⚠️ {symbol}: No market data available")
                    continue

                latest_candle = df.iloc[-1]
                current_price = latest_candle.get("close", 0)
                atr = latest_candle.get("atr", current_price * 0.003)
                volatility = latest_candle.get("volatility", 0.0)

                market_data = self.MarketData(price=current_price, atr=atr, volatility=volatility)
                levels = self.global_risk_calculator.calculate_position_levels(
                    market_data, signal["signal_name"].lower(), signal["confidence"], usdt_balance
                )
                if levels.margin > usdt_balance:
                    logging.warning(f"⚠️ {symbol}: Insufficient balance")
                    break

                result = await self.global_trading_orchestrator.execute_new_trade(exchange, signal, market_data, usdt_balance)
                if result.success:
                    executed_trades += 1
                    usdt_balance -= levels.margin
                    logging.info(colored(f"✅ {i}/{len(signals_to_execute)} {symbol}: Trade executed", "green"))
                else:
                    logging.warning(f"❌ {i}/{len(signals_to_execute)} {symbol}: {result.error}")
            except Exception as e:
                logging.error(f"❌ Error executing {signal['symbol']}: {e}", exc_info=True)
                continue

        if executed_trades > 0:
            enhanced_logger.display_table(f"✅ Execution complete: {executed_trades} trades", "green")
        else:
            enhanced_logger.display_table("⚠️ No signals executed", "yellow")

    async def _setup_trading_parameters(self, exchange, signals_to_execute):
        from core.enhanced_logging_system import enhanced_logger

        enhanced_logger.display_table("⚖️ Setting leverage + isolated margin for selected symbols", "yellow")
        for signal in signals_to_execute:
            symbol = signal["symbol"]
            try:
                await exchange.set_leverage(config.LEVERAGE, symbol)
                await exchange.set_margin_mode("isolated", symbol)
            except Exception as e:
                logging.warning(f"⚠️ {symbol}: Param setup failed: {e}")

    async def _manage_positions(self, exchange):
        from core.enhanced_logging_system import enhanced_logger

        if not self.clean_modules_available:
            return

        enhanced_logger.display_table("🔄 Synchronizing positions with Bybit", "cyan")
        if not config.DEMO_MODE:
            try:
                await self.position_manager.sync_with_bybit(exchange)
            except Exception as e:
                logging.warning(f"Position sync error: {e}")

        # Safety manager
        if POSITION_SAFETY_AVAILABLE and not config.DEMO_MODE:
            try:
                closed_unsafe = await global_position_safety_manager.check_and_close_unsafe_positions(
                    exchange, self.position_manager
                )
                if closed_unsafe > 0:
                    enhanced_logger.display_table(f"🛡️ {closed_unsafe} unsafe positions closed", "yellow")
            except Exception as safety_error:
                logging.error(f"Position safety check error: {safety_error}")

    async def _handle_online_learning(self):
        from core.enhanced_logging_system import enhanced_logger, log_separator

        try:
            summary = global_online_learning_manager.get_learning_performance_summary()
            if summary.get("total_trades", 0) > 0:
                global_online_learning_manager.display_learning_dashboard()
            else:
                enhanced_logger.display_table("🧠 No completed trades yet for learning analysis", "yellow")
        except Exception as e:
            logging.warning(f"Learning dashboard error: {e}")

    async def _update_realtime_display(self, exchange):
        from core.enhanced_logging_system import enhanced_logger

        if not hasattr(self, "realtime_display") or self.realtime_display is None:
            try:
                trailing_monitor = getattr(self, "trailing_monitor", None)
                self.realtime_display = initialize_global_realtime_display(
                    self.position_manager if self.clean_modules_available else None,
                    trailing_monitor,
                )
                enhanced_logger.display_table("📊 Realtime display initialized", "cyan")
            except Exception as init_error:
                logging.error(f"❌ Failed to initialize realtime display: {init_error}")
                self.realtime_display = None

        if self.realtime_display:
            try:
                await self.realtime_display.update_snapshot(exchange)
                self.realtime_display.show_snapshot()
            except Exception as e:
                logging.error(f"❌ Snapshot display failed: {e}")

    async def run_continuous_trading(self, exchange, xgb_models, xgb_scalers):
        while True:
            try:
                await self.run_trading_cycle(exchange, xgb_models, xgb_scalers)
                await self._wait_with_countdown(config.TRADE_CYCLE_INTERVAL)
            except KeyboardInterrupt:
                logging.info("🛑 Trading stopped by user")
                break
            except Exception as e:
                logging.error(f"❌ Error in trading loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _wait_with_countdown(self, total_seconds: int):
        """Countdown con logging multiplo"""
        from core.enhanced_logging_system import enhanced_logger, countdown_logger

        countdown_logger.log_countdown_start(total_seconds // 60)
        remaining = total_seconds

        while remaining > 0:
            minutes, seconds = divmod(remaining, 60)
            countdown_text = f"⏰ Next cycle in: {minutes}m{seconds:02d}s"
            print(f"\r{colored(countdown_text, 'magenta')}", end="", flush=True)

            if remaining % 30 == 0 or remaining <= 10:
                countdown_logger.log_countdown_tick(minutes, seconds)

            await asyncio.sleep(1)
            remaining -= 1

        print()
        enhanced_logger.display_table("🚀 Starting next cycle...", "cyan", attrs=["bold"])
