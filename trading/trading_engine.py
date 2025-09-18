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
from core.realtime_display import global_realtime_display, initialize_global_realtime_display

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


class TradingEngine:
    """
    Main trading engine che orchestra l'intero processo di trading
    """

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.first_cycle = True

        # Componenti principali
        self.market_analyzer = global_market_analyzer
        self.signal_processor = global_signal_processor

        # Componenti opzionali
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
            from core.smart_position_manager import global_smart_position_manager as position_manager

            self.global_order_manager = global_order_manager
            self.global_risk_calculator = global_risk_calculator
            self.global_trading_orchestrator = global_trading_orchestrator
            self.position_manager = position_manager
            self.MarketData = MarketData

            logging.debug("🎯 Clean trading modules loaded")
            return True
        except ImportError as e:
            logging.warning(f"⚠️ Clean modules not available: {e}")
            return False

    async def initialize_session(self, exchange):
        """
        Initialize fresh session with position sync
        """
        logging.info(colored("🧹 FRESH SESSION STARTUP", "cyan", attrs=['bold']))

        if self.clean_modules_available:
            self.position_manager.reset_session()

        real_balance = await get_real_balance(exchange)
        if real_balance and real_balance > 0:
            if self.clean_modules_available:
                self.position_manager.update_real_balance(real_balance)
            logging.info(colored(f"💰 Balance synced: ${real_balance:.2f}", "green"))
        else:
            logging.warning("⚠️ Could not sync real balance - using fallback")

        logging.info(colored("✅ Ready for fresh sync", "green"))

        if not config.DEMO_MODE and self.clean_modules_available:
            logging.info(colored("🔄 SYNCING WITH REAL BYBIT POSITIONS", "cyan"))
            try:
                protection_results = await self.global_trading_orchestrator.protect_existing_positions(exchange)
                if protection_results:
                    successful = sum(1 for r in protection_results.values() if r.success)
                    total = len(protection_results)
                    logging.info(colored(f"🛡️ Protected {successful}/{total} existing positions", "cyan"))
                    await self.position_manager.emergency_update_bybit_stop_losses(exchange, self.global_order_manager)
                else:
                    logging.info(colored("🆕 No existing positions - starting fresh", "green"))
            except Exception as e:
                logging.warning(f"⚠️ Error during position protection: {e}")

        logging.info(colored("-" * 80, "cyan"))

    async def run_trading_cycle(self, exchange, xgb_models, xgb_scalers):
        """
        Execute one complete trading cycle with enhanced phase visualization
        """
        from core.enhanced_logging_system import enhanced_logger, cycle_logger, log_separator
        
        cycle_start_time = time.time()

        try:
            # ══════════════════════════════════════════════════════════════════════════════════════
            # 🚀 TRADING CYCLE START
            # ══════════════════════════════════════════════════════════════════════════════════════
            enhanced_logger.display_table("")
            log_separator("═", 100, "cyan")
            enhanced_logger.display_table("🚀 TRADING CYCLE STARTED", "cyan", attrs=['bold'])
            log_separator("═", 100, "cyan")

            # ──────────────────────────────────────────────────────────────────────────────────────
            # 📊 PHASE 1: DATA COLLECTION
            # ──────────────────────────────────────────────────────────────────────────────────────
            enhanced_logger.display_table("📈 PHASE 1: DATA COLLECTION & MARKET ANALYSIS", "blue", attrs=['bold'])
            log_separator("─", 80, "blue")
            enhanced_logger.display_table(f"🔍 Analyzing {config.TOP_ANALYSIS_CRYPTO} symbols across {len(self.config_manager.get_timeframes())} timeframes", "blue")
            
            all_symbol_data, complete_symbols, data_fetch_time = await self.market_analyzer.collect_market_data(
                exchange,
                self.config_manager.get_timeframes(),
                config.TOP_ANALYSIS_CRYPTO,
                config.EXCLUDED_SYMBOLS
            )
            
            if not complete_symbols:
                enhanced_logger.display_table("⚠️ No symbols with complete data this cycle", "yellow")
                return

            enhanced_logger.display_table(f"✅ Data collection complete: {len(complete_symbols)}/{config.TOP_ANALYSIS_CRYPTO} symbols ready", "green")

            # ──────────────────────────────────────────────────────────────────────────────────────
            # 🧠 PHASE 2: ML PREDICTIONS
            # ──────────────────────────────────────────────────────────────────────────────────────
            cycle_logger.log_phase(2, "ML PREDICTIONS & AI ANALYSIS", "magenta")
            log_separator("─", 80, "magenta")
            enhanced_logger.display_table(f"🧠 Running XGBoost models on {len(complete_symbols)} symbols", "magenta")
            
            prediction_results, ml_time = await self.market_analyzer.generate_ml_predictions(
                xgb_models, xgb_scalers, config.get_timesteps_for_timeframe(self.config_manager.get_default_timeframe())
            )

            enhanced_logger.display_table(f"✅ ML predictions complete: {len(prediction_results)} results generated", "green")

            # ──────────────────────────────────────────────────────────────────────────────────────
            # 🔄 PHASE 3: SIGNAL PROCESSING
            # ──────────────────────────────────────────────────────────────────────────────────────
            cycle_logger.log_phase(3, "SIGNAL PROCESSING & FILTERING", "yellow")
            log_separator("─", 80, "yellow")
            enhanced_logger.display_table("🔄 Processing ML predictions into trading signals", "yellow")
            
            self.signal_processor.display_complete_analysis(prediction_results, all_symbol_data)
            all_signals = await self.signal_processor.process_prediction_results(
                prediction_results, all_symbol_data
            )

            enhanced_logger.display_table(f"✅ Signal processing complete: {len(all_signals)} signals generated", "green")

            # ──────────────────────────────────────────────────────────────────────────────────────
            # 📈 PHASE 4: RANKING & SELECTION
            # ──────────────────────────────────────────────────────────────────────────────────────
            cycle_logger.log_phase(4, "RANKING & TOP SIGNAL SELECTION", "green")
            log_separator("─", 80, "green")
            enhanced_logger.display_table("📈 Ranking signals by confidence and selecting top candidates", "green")
            
            display_top_signals(all_signals, limit=10)

            # ──────────────────────────────────────────────────────────────────────────────────────
            # 🚀 PHASE 5: TRADE EXECUTION
            # ──────────────────────────────────────────────────────────────────────────────────────
            cycle_logger.log_phase(5, "TRADE EXECUTION", "red")
            log_separator("─", 80, "red")
            enhanced_logger.display_table("🚀 Executing selected trading signals", "red")
            
            await self._execute_signals(exchange, all_signals)

            # ──────────────────────────────────────────────────────────────────────────────────────
            # 🛡️ PHASE 6: POSITION MANAGEMENT
            # ──────────────────────────────────────────────────────────────────────────────────────
            cycle_logger.log_phase(6, "POSITION MANAGEMENT & RISK CONTROL", "cyan")
            log_separator("─", 80, "cyan")
            enhanced_logger.display_table("🛡️ Managing existing positions and risk controls", "cyan")
            
            await self._manage_positions(exchange)

            # ──────────────────────────────────────────────────────────────────────────────────────
            # 📊 PHASE 7: PERFORMANCE ANALYSIS
            # ──────────────────────────────────────────────────────────────────────────────────────
            cycle_logger.log_phase(7, "PERFORMANCE ANALYSIS & REPORTING", "white")
            log_separator("─", 80, "white")
            enhanced_logger.display_table("📊 Analyzing cycle performance and generating reports", "white")
            
            cycle_total_time = time.time() - cycle_start_time
            show_performance_summary(
                cycle_total_time,
                data_fetch_time,
                ml_time,
                len(self.market_analyzer.get_top_symbols()),
                len(self.config_manager.get_timeframes()),
                len(complete_symbols),
                self.database_system_loaded
            )

            # ──────────────────────────────────────────────────────────────────────────────────────
            # 🧠 PHASE 8: ONLINE LEARNING & ADAPTATION
            # ──────────────────────────────────────────────────────────────────────────────────────
            if ONLINE_LEARNING_AVAILABLE and global_online_learning_manager:
                cycle_logger.log_phase(8, "ONLINE LEARNING & AI ADAPTATION", "magenta")
                log_separator("─", 80, "magenta")
                enhanced_logger.display_table("🧠 Analyzing trade performance for AI learning", "magenta")
                
                try:
                    # Show learning dashboard every 5 cycles or if we have new completed trades
                    cycle_count = getattr(self, 'cycle_count', 0) + 1
                    self.cycle_count = cycle_count
                    
                    summary = global_online_learning_manager.get_learning_performance_summary()
                    if summary.get('total_trades', 0) > 0 and (cycle_count % 5 == 0 or summary.get('total_trades', 0) != getattr(self, 'last_trade_count', 0)):
                        global_online_learning_manager.display_learning_dashboard()
                        self.last_trade_count = summary.get('total_trades', 0)
                    elif summary.get('total_trades', 0) == 0:
                        enhanced_logger.display_table("🧠 No completed trades yet for learning analysis", "yellow")
                        
                    # Show active trades info
                    active_count = global_online_learning_manager.get_active_trades_count()
                    if active_count > 0:
                        enhanced_logger.display_table(f"📊 Currently tracking {active_count} active trades for learning", "cyan")
                        
                except Exception as dashboard_error:
                    logging.warning(f"Learning dashboard error: {dashboard_error}")

            # ──────────────────────────────────────────────────────────────────────────────────────
            # 📊 PHASE 9: REALTIME POSITION DISPLAY
            # ──────────────────────────────────────────────────────────────────────────────────────
            cycle_logger.log_phase(9, "POSITION DISPLAY & PORTFOLIO OVERVIEW", "green")
            log_separator("─", 80, "green")
            enhanced_logger.display_table("📊 Updating live position display and portfolio status", "green")

            if self.first_cycle:
                self.first_cycle = False
                if self.database_system_loaded:
                    self.display_database_stats()

            # Initialize realtime display if needed
            if not hasattr(self, 'realtime_display') or self.realtime_display is None:
                try:
                    trailing_monitor = getattr(self, 'trailing_monitor', None)
                    self.realtime_display = initialize_global_realtime_display(
                        self.position_manager if self.clean_modules_available else None,
                        trailing_monitor
                    )
                    enhanced_logger.display_table("📊 Realtime display initialized for cycle", "cyan")
                except Exception as init_error:
                    logging.error(f"❌ Failed to initialize realtime display: {init_error}")
                    self.realtime_display = None
            
            if self.realtime_display:
                try:
                    await self.realtime_display.update_snapshot(exchange)
                    self.realtime_display.show_snapshot()
                    enhanced_logger.display_table("✅ Position display updated successfully", "green")
                except Exception as e:
                    logging.error(f"❌ Snapshot display failed: {e}")
            else:
                enhanced_logger.display_table("⚠️ Realtime display not available", "yellow")

            # ══════════════════════════════════════════════════════════════════════════════════════
            # ✅ CYCLE COMPLETE
            # ══════════════════════════════════════════════════════════════════════════════════════
            log_separator("═", 100, "green")
            enhanced_logger.display_table("✅ TRADING CYCLE COMPLETED SUCCESSFULLY", "green", attrs=['bold'])
            enhanced_logger.display_table(f"⏱️ Total cycle time: {cycle_total_time:.1f}s", "green")
            log_separator("═", 100, "green")
            enhanced_logger.display_table("")

        except Exception as e:
            logging.error(f"Error in trading cycle: {e}")
            raise

    async def _execute_signals(self, exchange, all_signals):
        """
        Execute trading signals with enhanced logging
        """
        from core.enhanced_logging_system import enhanced_logger
        
        if not all_signals:
            enhanced_logger.display_table("😐 No signals to execute this cycle", "yellow")
            return

        usdt_balance = await get_real_balance(exchange)
        if usdt_balance is None:
            enhanced_logger.display_table("⚠️ Failed to get USDT balance", "yellow")
            return

        # Open positions count
        if self.clean_modules_available:
            open_positions_count = self.position_manager.get_position_count()
        else:
            try:
                positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
                open_positions_count = len([p for p in positions if float(p.get('contracts', 0)) > 0])
            except Exception:
                open_positions_count = 0

        max_positions = config.MAX_CONCURRENT_POSITIONS - open_positions_count
        signals_to_execute = all_signals[:min(max_positions, len(all_signals))]
        if not signals_to_execute:
            enhanced_logger.display_table("⚠️ Maximum positions reached, no new signals", "yellow")
            return

        enhanced_logger.display_table(f"🎯 Executing {len(signals_to_execute)} signals (max {max_positions} available)", "red")
        await self._setup_trading_parameters(exchange, signals_to_execute)

        executed_trades = 0
        for i, signal in enumerate(signals_to_execute, 1):
            try:
                if not self.clean_modules_available:
                    logging.warning("⚠️ Clean modules not available, skipping")
                    break

                symbol = signal['symbol']
                
                # 🔧 SKIP ELEGANTE: Controlla posizioni esistenti prima di tutto
                if self.position_manager.has_position_for_symbol(symbol):
                    logging.info(colored(f"📝 {i}/{len(signals_to_execute)} {symbol}: Position exists, skipping", "cyan"))
                    available_balance = self.position_manager.get_available_balance()
                    logging.info(colored(f"💰 Available balance: ${available_balance:.2f}", "white"))
                    continue
                
                can_open, reason = self.global_trading_orchestrator.can_open_new_position(symbol, usdt_balance)
                if not can_open:
                    logging.warning(f"⚠️ {symbol}: {reason}")
                    available_balance = self.position_manager.get_available_balance()
                    logging.info(colored(f"💰 Available balance: ${available_balance:.2f}", "white"))
                    continue

                df = signal['dataframes'][self.config_manager.get_default_timeframe()]
                if df is None or len(df) == 0:
                    logging.warning(f"⚠️ {symbol}: No market data available")
                    continue

                latest_candle = df.iloc[-1]
                current_price = latest_candle.get('close', 0)
                atr = latest_candle.get('atr', current_price * 0.003)
                volatility = latest_candle.get('volatility', 0.0)

                market_data = self.MarketData(price=current_price, atr=atr, volatility=volatility)
                levels = self.global_risk_calculator.calculate_position_levels(
                    market_data, signal['signal_name'].lower(), signal['confidence'], usdt_balance
                )
                if levels.margin > usdt_balance:
                    logging.warning(f"⚠️ {symbol}: Insufficient balance")
                    break

                result = await self.global_trading_orchestrator.execute_new_trade(
                    exchange, signal, market_data, usdt_balance
                )
                if result.success:
                    executed_trades += 1
                    usdt_balance -= levels.margin
                    
                    # 🧠 ONLINE LEARNING: Track trade opening
                    if ONLINE_LEARNING_AVAILABLE:
                        try:
                            # Build context data for learning
                            from core.rl_agent import build_market_context
                            market_context = build_market_context(symbol, signal['dataframes'])
                            portfolio_state = self.position_manager.get_session_summary()
                            
                            # Track the trade opening
                            global_online_learning_manager.track_trade_opening(
                                symbol, signal, market_context, portfolio_state
                            )
                            
                            # Update entry details
                            global_online_learning_manager.update_trade_entry(
                                symbol, current_price, levels.margin
                            )
                            
                            logging.debug(f"🧠 Trade tracking started for {symbol.replace('/USDT:USDT', '')}")
                            
                        except Exception as tracking_error:
                            logging.warning(f"Trade tracking error: {tracking_error}")
                    
                    logging.info(colored(f"✅ {i}/{len(signals_to_execute)} {symbol}: Trade executed", "green"))
                    # Mostra wallet aggiornato dopo successo
                    available_balance = self.position_manager.get_available_balance()
                    logging.info(colored(f"💰 Available balance: ${available_balance:.2f} (Used: ${levels.margin:.2f})", "white"))
                else:
                    logging.warning(f"❌ {i}/{len(signals_to_execute)} {symbol}: {result.error}")
                    # Mostra wallet anche dopo fallimento
                    available_balance = self.position_manager.get_available_balance()
                    logging.info(colored(f"💰 Available balance: ${available_balance:.2f}", "white"))
                    if "insufficient balance" in result.error.lower():
                        break
            except Exception as e:
                logging.error(f"❌ Error executing {signal['symbol']}: {e}")
                available_balance = self.position_manager.get_available_balance()
                logging.info(colored(f"💰 Available balance: ${available_balance:.2f}", "white"))
                continue

        if executed_trades > 0:
            enhanced_logger.display_table(f"✅ Execution complete: {executed_trades}/{len(signals_to_execute)} signals executed", "green")
        else:
            enhanced_logger.display_table("⚠️ No signals were executed this cycle", "yellow")

    async def _setup_trading_parameters(self, exchange, signals_to_execute):
        from core.enhanced_logging_system import enhanced_logger
        enhanced_logger.display_table("⚖️ Setting leverage + isolated margin for selected symbols", "yellow")
        for signal in signals_to_execute:
            symbol = signal['symbol']
            try:
                await exchange.set_leverage(config.LEVERAGE, symbol)
                await exchange.set_margin_mode('isolated', symbol)
            except Exception as e:
                logging.warning(f"⚠️ {symbol}: Param setup failed: {e}")

    async def _manage_positions(self, exchange):
        from core.enhanced_logging_system import enhanced_logger
        
        if not self.clean_modules_available:
            return
            
        enhanced_logger.display_table("🔄 Synchronizing positions with Bybit", "cyan")
        
        if not config.DEMO_MODE:
            try:
                newly_opened, newly_closed = await self.position_manager.sync_with_bybit(exchange)
                if newly_opened or newly_closed:
                    enhanced_logger.display_table(f"🔄 Position sync: +{len(newly_opened)} opened, +{len(newly_closed)} closed", "cyan")
            except Exception as e:
                logging.warning(f"Position sync error: {e}")
        
        # CRITICAL: Safety checks for all positions
        if POSITION_SAFETY_AVAILABLE and not config.DEMO_MODE:
            enhanced_logger.display_table("🛡️ Running safety checks on all positions", "cyan")
            try:
                # Check and close unsafe positions
                closed_unsafe = await global_position_safety_manager.check_and_close_unsafe_positions(
                    exchange, self.position_manager
                )
                
                # Enforce stop loss for all positions
                await global_position_safety_manager.enforce_stop_loss_for_all_positions(
                    exchange, self.position_manager, self.global_order_manager
                )
                
                if closed_unsafe > 0:
                    enhanced_logger.display_table(f"🛡️ Safety Manager: {closed_unsafe} unsafe positions closed", "yellow")
                else:
                    enhanced_logger.display_table("✅ All positions passed safety checks", "green")
                    
            except Exception as safety_error:
                logging.error(f"Position safety check error: {safety_error}")
        
        enhanced_logger.display_table("📈 Updating trailing stop systems", "cyan")
        try:
            closed_positions = await self.global_trading_orchestrator.update_trailing_positions(exchange)
            for pos in closed_positions:
                enhanced_logger.display_table(f"🎯 Trailing Exit: {pos.symbol} {pos.side.upper()} {pos.unrealized_pnl_pct:+.2f}%", "green")
        except Exception as e:
            logging.warning(f"Trailing system error: {e}")

    async def run_continuous_trading(self, exchange, xgb_models, xgb_scalers):
        while True:
            try:
                await self.run_trading_cycle(exchange, xgb_models, xgb_scalers)
                
                # 🕐 COUNTDOWN DINAMICO: Mostra timer nel terminale durante l'attesa
                await self._wait_with_countdown(config.TRADE_CYCLE_INTERVAL)
                
            except KeyboardInterrupt:
                logging.info("Shutting down…")
                break
            except Exception as e:
                logging.error(f"Error in trading cycle: {e}")
                await asyncio.sleep(60)
    
    async def _wait_with_countdown(self, total_seconds: int):
        """
        🕐 Attesa con countdown mono-riga nel terminale
        
        Args:
            total_seconds: Secondi totali da attendere (es. 300 per 5m)
            
        🚀 ENHANCED: Uses triple output logging system
        """
        # Import enhanced logging
        from core.enhanced_logging_system import enhanced_logger, countdown_logger
        
        # Log countdown start
        countdown_logger.log_countdown_start(total_seconds // 60)
        
        remaining = total_seconds
        
        while remaining > 0:
            # Calcola tempo rimanente
            minutes = remaining // 60
            seconds = remaining % 60
            
            # 🔧 TERMINAL: Usa print con \r per sovrascrivere (mantiene UX originale)
            countdown_text = f"⏰ Next cycle in: {minutes}m{seconds:02d}s"
            print(f"\r{colored(countdown_text, 'magenta')}", end='', flush=True)
            
            # 📝 FILE LOGGING: Log ogni tick significativo (ogni 30 secondi)
            if remaining % 30 == 0 or remaining <= 10:
                countdown_logger.log_countdown_tick(minutes, seconds)
            
            # Sleep per 1 secondo per aggiornamento fluido
            await asyncio.sleep(1)
            remaining -= 1
        
        # Fine countdown
        print()  # Nuova riga dopo il countdown
        enhanced_logger.display_table("🚀 Starting next cycle...", "cyan", attrs=['bold'])
