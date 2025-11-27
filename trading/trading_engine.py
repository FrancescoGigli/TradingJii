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

# Import Dual-Engine System (XGBoost vs AI parallel analysis)
try:
    from core.ai_technical_analyst import AITechnicalAnalyst, global_ai_technical_analyst
    from core.decision_comparator import DecisionComparator, ExecutionStrategy, global_decision_comparator
    DUAL_ENGINE_AVAILABLE = True
    logging.debug("🔄 Dual-Engine System (XGBoost vs AI) available")
except ImportError as e:
    DUAL_ENGINE_AVAILABLE = False
    logging.warning(f"⚠️ Dual-Engine System not available: {e}")

# Import trade decision logger
try:
    from core.trade_decision_logger import global_trade_decision_logger
    TRADE_DECISION_LOGGER_AVAILABLE = True
except ImportError:
    TRADE_DECISION_LOGGER_AVAILABLE = False
    global_trade_decision_logger = None

# Adaptive Learning System REMOVED (too complex)
ADAPTIVE_LEARNING_AVAILABLE = False

# Removed: Online Learning / Post-mortem system (not functioning)
# Removed: Position Safety Manager (migrated to thread_safe_position_manager)

# Thread-safe position manager (mandatory)
try:
    from core.thread_safe_position_manager import global_thread_safe_position_manager
    THREAD_SAFE_POSITIONS_AVAILABLE = True
    logging.debug("🔒 ThreadSafePositionManager integration enabled")
except ImportError:
    THREAD_SAFE_POSITIONS_AVAILABLE = False
    global_thread_safe_position_manager = None
    logging.error("❌ CRITICAL: ThreadSafePositionManager not available — cannot proceed safely")
    raise ImportError("CRITICAL: ThreadSafePositionManager required for unified position management")

# Import new integrated systems
try:
    from core.session_statistics import global_session_statistics
    from core.integrated_trailing_monitor import run_integrated_trailing_monitor
    INTEGRATED_SYSTEMS_AVAILABLE = True
    logging.debug("📊 Integrated systems (stats, trailing) loaded")
except ImportError as e:
    INTEGRATED_SYSTEMS_AVAILABLE = False
    logging.warning(f"⚠️ Integrated systems not available: {e}")

# Trading Coordinators removed: position_opening_coordinator was unused (never called)
# Eliminated as part of code simplification - all position logic in thread_safe_position_manager


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
        
        # Initialize integrated systems (stats + trailing, NO dashboard)
        if INTEGRATED_SYSTEMS_AVAILABLE and self.clean_modules_available:
            self.session_stats = global_session_statistics
            logging.debug("📊 Integrated systems initialized (stats, trailing)")
        else:
            self.session_stats = None
            logging.warning("⚠️ Integrated systems not available - using basic mode")
        
        # Initialize hybrid AI system (Rizzo integration)
        if config.AI_VALIDATION_ENABLED or config.MARKET_INTELLIGENCE_ENABLED:
            self._init_hybrid_ai_system()
    
    def _init_hybrid_ai_system(self):
        """Initialize hybrid AI system components (Rizzo integration)"""
        import os
        
        self.market_intelligence_hub = None
        self.ai_validator = None
        
        if config.MARKET_INTELLIGENCE_ENABLED:
            # Market Intelligence Hub will be initialized later (needs exchange)
            logging.info("🤖 Market Intelligence Hub will be initialized with exchange")
        
        if config.AI_VALIDATION_ENABLED:
            try:
                from core.ai_decision_validator import AIDecisionValidator
                
                self.ai_validator = AIDecisionValidator(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model=config.OPENAI_MODEL
                )
                
                if self.ai_validator.is_available():
                    logging.info(f"✅ AI Decision Validator ready ({config.OPENAI_MODEL})")
                else:
                    logging.warning("⚠️ AI validation enabled but OpenAI API key not available")
                    if not config.AI_FALLBACK_TO_XGBOOST:
                        logging.error("❌ AI validation required but unavailable - set AI_FALLBACK_TO_XGBOOST=True")
            except Exception as e:
                logging.error(f"❌ Failed to initialize AI validator: {e}")
                self.ai_validator = None

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

            logging.debug("🔒 Clean trading modules loaded with ThreadSafePositionManager")
            return True
        except ImportError as e:
            logging.error(f"❌ Clean modules not available: {e}")
            return False
    

    async def initialize_session(self, exchange):
        """
        Initialize fresh session with position sync
        
        FIX #3: Balance Centralization - Single source of truth
        🆕 SESSION TRACKING: Reset only closed positions to track THIS session only
        """
        logging.info(colored("🧹 FRESH SESSION STARTUP", "cyan", attrs=['bold']))

        if self.clean_modules_available:
            # Reset session (clears all positions)
            self.position_manager.reset_session()
            
            # 🆕 Reset ONLY closed positions - will be populated by trades closed in THIS session
            self.position_manager.reset_session_closed_positions()

        # FIX #3: Centralized balance initialization
        real_balance = None
        if not config.DEMO_MODE:
            real_balance = await get_real_balance(exchange)
            
            # Update ONLY position manager (single source of truth)
            if real_balance and real_balance > 0 and self.clean_modules_available:
                self.position_manager.update_real_balance(real_balance)
                logging.info(colored(f"💰 Balance synced (centralized): ${real_balance:.2f}", "green"))
        else:
            # Demo mode - use demo balance
            if self.clean_modules_available:
                self.position_manager.update_real_balance(config.DEMO_BALANCE)
            logging.info(colored(f"🧪 DEMO MODE: Using ${config.DEMO_BALANCE:.2f}", "yellow"))

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
            await self.signal_processor.display_complete_analysis(prediction_results, all_symbol_data)
            all_signals = await self.signal_processor.process_prediction_results(prediction_results, all_symbol_data)

            # 🆕 PHASE 3.5: DUAL-ENGINE SYSTEM or LEGACY AI VALIDATION
            market_intel = None
            
            # Check if Dual-Engine mode is enabled
            use_dual_engine = (
                getattr(config, 'DUAL_ENGINE_ENABLED', False) and 
                DUAL_ENGINE_AVAILABLE and 
                getattr(config, 'AI_ANALYST_ENABLED', False)
            )
            
            if use_dual_engine:
                # ═══════════════════════════════════════════════════════════════
                # 🔄 DUAL-ENGINE MODE: XGBoost and AI analyze same indicators
                # ═══════════════════════════════════════════════════════════════
                try:
                    import os
                    enhanced_logger.display_table("🔄 DUAL-ENGINE ANALYSIS (XGBoost vs GPT-4o)", "cyan", attrs=['bold'])
                    
                    # Determine execution strategy
                    strategy_name = getattr(config, 'DUAL_ENGINE_STRATEGY', 'consensus')
                    strategy_map = {
                        'xgboost_only': ExecutionStrategy.XGBOOST_ONLY,
                        'ai_only': ExecutionStrategy.AI_ONLY,
                        'consensus': ExecutionStrategy.CONSENSUS,
                        'weighted': ExecutionStrategy.WEIGHTED,
                        'champion': ExecutionStrategy.CHAMPION
                    }
                    strategy = strategy_map.get(strategy_name, ExecutionStrategy.CONSENSUS)
                    global_decision_comparator.set_strategy(strategy)
                    
                    logging.info(colored(f"📊 Dual-Engine Strategy: {strategy_name.upper()}", "cyan"))
                    
                    # Initialize Market Intelligence Hub if needed
                    if config.MARKET_INTELLIGENCE_ENABLED and not self.market_intelligence_hub:
                        from core.market_intelligence import MarketIntelligenceHub
                        self.market_intelligence_hub = MarketIntelligenceHub(
                            exchange,
                            cmc_api_key=os.getenv("CMC_PRO_API_KEY"),
                            whale_api_key=os.getenv("WHALE_ALERT_API_KEY")
                        )
                        logging.info("🤖 Market Intelligence Hub initialized")
                    
                    # Collect market intelligence for AI context
                    if config.MARKET_INTELLIGENCE_ENABLED and self.market_intelligence_hub:
                        top_symbols = self.market_analyzer.get_top_symbols()[:10]
                        market_intel = await self.market_intelligence_hub.collect_intelligence(top_symbols)
                        if market_intel and market_intel.sentiment:
                            s = market_intel.sentiment
                            logging.info(f"😨 Sentiment: {s.get('value', 'N/A')}/100 ({s.get('classification', 'N/A')})")
                    
                    # Limit signals for AI analysis (cost control)
                    max_ai_symbols = getattr(config, 'AI_ANALYST_MAX_SYMBOLS', 10)
                    signals_to_analyze = all_signals[:max_ai_symbols]
                    
                    # AI Technical Analyst - Parallel independent analysis
                    logging.info(colored(f"🧠 AI Technical Analyst analyzing {len(signals_to_analyze)} signals...", "magenta"))
                    ai_signals = await global_ai_technical_analyst.analyze_batch(
                        signals_to_analyze, 
                        market_intel
                    )
                    
                    logging.info(colored(f"🧠 AI returned {len(ai_signals)} independent analyses", "magenta"))
                    
                    # Compare XGBoost vs AI for each signal
                    filtered_signals = []
                    
                    for signal in signals_to_analyze:
                        symbol = signal['symbol']
                        ai_signal = ai_signals.get(symbol)
                        
                        # Compare using Decision Comparator
                        comparison = global_decision_comparator.compare_signal(
                            xgb_signal=signal,
                            ai_signal=ai_signal,
                            strategy_override=None  # Use global strategy
                        )
                        
                        # Apply execution decision
                        if comparison.should_trade:
                            # Enrich signal with comparison data
                            signal['dual_engine_comparison'] = comparison.to_dict()
                            signal['ai_analysis'] = ai_signal.to_dict() if ai_signal else None
                            
                            # Use consensus confidence if available
                            if comparison.consensus_confidence > 0:
                                signal['original_confidence'] = signal['confidence']
                                signal['confidence'] = comparison.consensus_confidence / 100  # Convert to 0-1 scale
                            
                            filtered_signals.append(signal)
                    
                    # Log comparison summary
                    agreement_rate = global_decision_comparator.stats.get_agreement_rate()
                    logging.info(colored(
                        f"🔄 Dual-Engine Results: {len(filtered_signals)}/{len(signals_to_analyze)} approved | "
                        f"Agreement Rate: {agreement_rate:.1f}%",
                        "cyan"
                    ))
                    
                    # Update all_signals with filtered results
                    all_signals = filtered_signals
                    
                    # Show comparison dashboard if configured
                    if getattr(config, 'DUAL_ENGINE_SHOW_DASHBOARD', False):
                        global_decision_comparator.display_stats_dashboard()
                    
                except Exception as e:
                    logging.error(f"❌ Dual-Engine error: {e}")
                    if not config.AI_FALLBACK_TO_XGBOOST:
                        logging.warning("⚠️ Dual-Engine failed and fallback disabled - skipping cycle")
                        return
                    logging.info("⚠️ Falling back to XGBoost-only mode")
            
            elif config.MARKET_INTELLIGENCE_ENABLED or config.AI_VALIDATION_ENABLED:
                # ═══════════════════════════════════════════════════════════════
                # 🤖 LEGACY AI VALIDATION MODE (validator only, not parallel)
                # ═══════════════════════════════════════════════════════════════
                try:
                    import os
                    
                    # Initialize Market Intelligence Hub on first use (needs exchange)
                    if config.MARKET_INTELLIGENCE_ENABLED and not self.market_intelligence_hub:
                        from core.market_intelligence import MarketIntelligenceHub
                        self.market_intelligence_hub = MarketIntelligenceHub(
                            exchange,
                            cmc_api_key=os.getenv("CMC_PRO_API_KEY"),
                            whale_api_key=os.getenv("WHALE_ALERT_API_KEY")
                        )
                        logging.info("🤖 Market Intelligence Hub initialized")
                    
                    # Collect market intelligence
                    if config.MARKET_INTELLIGENCE_ENABLED and self.market_intelligence_hub:
                        enhanced_logger.display_table("📊 COLLECTING MARKET INTELLIGENCE", "magenta", attrs=['bold'])
                        
                        top_symbols = self.market_analyzer.get_top_symbols()[:10]  # Top 10 for intel
                        market_intel = await self.market_intelligence_hub.collect_intelligence(top_symbols)
                        
                        logging.info(f"📰 News: {len(market_intel.news[:100])}+ chars")
                        if market_intel.sentiment:
                            s = market_intel.sentiment
                            logging.info(f"😨 Sentiment: {s.get('value', 'N/A')}/100 ({s.get('classification', 'N/A')})")
                        if market_intel.forecasts and 'forecasts' in market_intel.forecasts:
                            logging.info(f"🔮 Forecasts: {len(market_intel.forecasts['forecasts'])} symbols")
                    
                    # AI Validation (Legacy mode)
                    if config.AI_VALIDATION_ENABLED and self.ai_validator and self.ai_validator.is_available():
                        if market_intel:
                            enhanced_logger.display_table("🤖 AI VALIDATION WITH GPT-4o (Legacy Mode)", "cyan", attrs=['bold'])
                            
                            # Get portfolio state
                            portfolio_state = {}
                            if self.clean_modules_available:
                                session_summary = self.position_manager.get_session_summary()
                                portfolio_state = {
                                    'balance': session_summary.get('balance', 0),
                                    'available_balance': session_summary.get('available_balance', 0),
                                    'active_positions': session_summary.get('active_positions', 0)
                                }
                            
                            # Validate signals with AI
                            validated_signals, ai_metadata = await self.ai_validator.validate_signals(
                                all_signals[:config.AI_MAX_SIGNALS_TO_VALIDATE],
                                market_intel,
                                portfolio_state,
                                max_signals=config.AI_MAX_SIGNALS_TO_VALIDATE
                            )
                            
                            # Filter to approved signals only
                            approved_signals = self.ai_validator.filter_approved_signals(validated_signals)
                            
                            # Log AI decision
                            logging.info(
                                f"🤖 AI Validation: {len(approved_signals)}/{len(all_signals[:config.AI_MAX_SIGNALS_TO_VALIDATE])} approved | "
                                f"Outlook: {ai_metadata.get('market_outlook', 'N/A')} | "
                                f"Risk: {ai_metadata.get('overall_risk_level', 'N/A')} | "
                                f"Cost: ${ai_metadata.get('cost_usd', 0):.4f}"
                            )
                            
                            # Replace signals with AI-approved ones
                            all_signals = approved_signals
                            
                            # Show approved signals with AI reasoning
                            if config.AI_VERBOSE_LOGGING and approved_signals:
                                for sig in approved_signals[:3]:  # Top 3
                                    if 'ai_reasoning' in sig:
                                        symbol_short = sig['symbol'].replace('/USDT:USDT', '')
                                        logging.info(f"   💡 {symbol_short}: {sig['ai_reasoning'][:80]}...")
                        else:
                            logging.warning("⚠️ AI validation enabled but no market intelligence available")
                    elif config.AI_VALIDATION_ENABLED and not config.AI_FALLBACK_TO_XGBOOST:
                        # AI required but not available - skip cycle
                        logging.warning("⚠️ AI validation required but not available - skipping cycle")
                        return
                        
                except Exception as e:
                    logging.error(f"❌ Market intelligence/AI error: {e}")
                    if config.AI_VALIDATION_ENABLED and not config.AI_FALLBACK_TO_XGBOOST:
                        logging.warning("⚠️ AI validation failed and fallback disabled - skipping cycle")
                        return

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

            # Phase 8: Realtime Display
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
        """Execute trading signals with enhanced logging and beautiful execution cards"""
        from utils.display_utils import display_phase5_header, display_execution_card, display_execution_summary
        
        if not all_signals:
            logging.info(colored("😐 No signals to execute this cycle", "yellow"))
            return

        # STEP 1: PRE-EXECUTION SYNC - Get accurate balance
        if self.clean_modules_available and not config.DEMO_MODE:
            logging.info(colored("🔄 PRE-EXECUTION SYNC: Checking existing positions...", "cyan"))
            try:
                newly_opened, newly_closed = await self.position_manager.thread_safe_sync_with_bybit(exchange)
                if newly_opened or newly_closed:
                    logging.info(colored(f"🔄 Sync found: {len(newly_opened)} new, {len(newly_closed)} closed", "cyan"))
            except Exception as sync_error:
                logging.warning(f"⚠️ Pre-execution sync failed: {sync_error}")

        # FIX #3: CENTRALIZED BALANCE - Use ONLY position manager (single source of truth)
        if not config.DEMO_MODE and self.clean_modules_available:
            # Sync balance from Bybit ONCE per cycle
            real_balance = await get_real_balance(exchange)
            if real_balance and real_balance > 0:
                self.position_manager.update_real_balance(real_balance)
                logging.debug(f"💰 Balance updated: ${real_balance:.2f}")

        # Get balance from centralized source
        if self.clean_modules_available:
            session_summary = self.position_manager.get_session_summary()
            usdt_balance = session_summary.get('balance', config.DEMO_BALANCE)
            used_margin = session_summary.get('used_margin', 0)
            available_balance = session_summary.get('available_balance', 0)
            open_positions_count = session_summary.get('active_positions', 0)
            
            # ✅ FIX PROBLEMA 4: BALANCE DOUBLE-COUNTING VALIDATION
            # Validate that available_balance calculation is correct
            calculated_available = usdt_balance - used_margin
            balance_diff = abs(available_balance - calculated_available)
            
            if balance_diff > 0.01:  # Tolerance: 1 cent
                logging.error(
                    f"❌ BALANCE MISMATCH DETECTED!\n"
                    f"   Reported available: ${available_balance:.2f}\n"
                    f"   Calculated (balance - used): ${calculated_available:.2f}\n"
                    f"   Difference: ${balance_diff:.2f}\n"
                    f"   Total balance: ${usdt_balance:.2f}\n"
                    f"   Used margin: ${used_margin:.2f}\n"
                    f"   Active positions: {open_positions_count}"
                )
                # Use calculated value as safe fallback
                available_balance = max(0, calculated_available)
                logging.warning(f"⚠️ Using calculated available balance: ${available_balance:.2f}")
            else:
                # Balance calculation is correct
                logging.debug(
                    f"✅ Balance validation passed: ${available_balance:.2f} available "
                    f"(${usdt_balance:.2f} total - ${used_margin:.2f} used)"
                )
        else:
            logging.warning("⚠️ Clean modules not available")
            return
        
        # STEP 4: BEAUTIFUL PHASE 5 HEADER
        display_phase5_header(usdt_balance, available_balance, used_margin, len(all_signals))

        if not all_signals:
            return

        # STEP 5: FILTER + SORT + LIMIT
        # Filter out symbols excluded from trading (BTC/ETH kept for training only)
        tradeable_signals = [s for s in all_signals if s["symbol"] not in config.EXCLUDED_FROM_TRADING]
        
        # Sort by confidence (highest first) - Priority-based execution
        tradeable_signals.sort(key=lambda x: x["confidence"], reverse=True)
        logging.info(colored(f"📊 Sorted {len(tradeable_signals)} signals by confidence (priority execution)", "cyan"))
        
        if len(all_signals) != len(tradeable_signals):
            excluded_count = len(all_signals) - len(tradeable_signals)
            logging.info(colored(f"🚫 Filtered {excluded_count} excluded symbols (training only)", "yellow"))
        
        # Apply position limits (max 5 based on new system)
        max_positions = max(0, config.MAX_CONCURRENT_POSITIONS - open_positions_count)
        signals_to_execute = tradeable_signals[: min(max_positions, len(tradeable_signals))]
        
        # Calculate margins using portfolio-based sizing
        if signals_to_execute and self.clean_modules_available:
            portfolio_margins = self.global_risk_calculator.calculate_portfolio_based_margins(
                signals_to_execute, available_balance, total_wallet=usdt_balance
            )
            logging.info(colored(f" Portfolio sizing: {len(portfolio_margins)} positions with weighted margins", "cyan"))
        else:
            portfolio_margins = []
        
        if not signals_to_execute:
            logging.info(colored("⚠️ No slots for new positions", "yellow"))
            return

        # Early balance check - test first signal to avoid useless loops
        if signals_to_execute and self.clean_modules_available:
            first_signal = signals_to_execute[0]
            df = first_signal["dataframes"][self.config_manager.get_default_timeframe()]
            if df is not None and len(df) > 0:
                latest_candle = df.iloc[-1]
                current_price = latest_candle.get("close", 0)
                atr = latest_candle.get("atr", current_price * 0.003)
                volatility = latest_candle.get("volatility", 0.0)
                
                market_data = self.MarketData(price=current_price, atr=atr, volatility=volatility)
                levels = self.global_risk_calculator.calculate_position_levels(
                    market_data, first_signal["signal_name"].lower(), first_signal["confidence"], usdt_balance
                )
                
                # Skip if position would be too small (e.g., high-price assets like XAUT)
                if levels is None:
                    enhanced_logger.display_table(
                        f"⚠️ FIRST SIGNAL SKIPPED: {first_signal['symbol']} requires too small IM (high-price asset)",
                        "yellow"
                    )
                    # Continue to other signals
                    return
                
                # Early exit if first signal requires more than available balance
                if levels.margin > usdt_balance:
                    enhanced_logger.display_table(f"⚠️ INSUFFICIENT BALANCE: Need ${levels.margin:.2f}+ per trade, have ${usdt_balance:.2f}", "yellow")
                    enhanced_logger.display_table("⏭️ SKIPPING EXECUTION → Moving to Position Management", "yellow")
                    return

        # Setup trading parameters (silent)
        await self._setup_trading_parameters_silent(exchange, signals_to_execute)

        # STEP 6: EXECUTE SIGNALS WITH BEAUTIFUL CARDS
        executed_trades = 0
        skipped_existing = 0
        failed_trades = 0
        total_margin_used = 0
        consecutive_insufficient_balance = 0  # FIX 3: Track consecutive balance failures
        MAX_CONSECUTIVE_BALANCE_FAILURES = 5  # FIX 3: Early exit threshold
        
        for i, signal in enumerate(signals_to_execute, 1):
            try:
                if not self.clean_modules_available:
                    display_execution_card(i, len(signals_to_execute), signal["symbol"], signal, None, "FAILED", "Clean modules not available")
                    break

                symbol = signal["symbol"]
                symbol_short = symbol.replace('/USDT:USDT', '')

                # 🛡️ BLACKLIST CHECK: Skip problematic symbols (XAUT, PAXG, etc.)
                if symbol in config.SYMBOL_BLACKLIST:
                    display_execution_card(
                        i, len(signals_to_execute), symbol, signal, None, "SKIPPED",
                        "Symbol in BLACKLIST (known issues)"
                    )
                    logging.warning(colored(f"⛔ {symbol_short}: In BLACKLIST - SKIP", "red"))
                    continue

                # Check if position already exists
                if self.position_manager.has_position_for_symbol(symbol):
                    skipped_existing += 1
                    display_execution_card(i, len(signals_to_execute), symbol, signal, None, "SKIPPED", "Position already exists")
                    continue

                # Get market data and calculate levels
                df = signal["dataframes"][self.config_manager.get_default_timeframe()]
                if df is None or len(df) == 0:
                    failed_trades += 1
                    display_execution_card(i, len(signals_to_execute), symbol, signal, None, "FAILED", "No market data available")
                    continue

                latest_candle = df.iloc[-1]
                current_price = latest_candle.get("close", 0)
                atr = latest_candle.get("atr", current_price * 0.003)
                volatility = latest_candle.get("volatility", 0.0)

                market_data = self.MarketData(price=current_price, atr=atr, volatility=volatility)
                
                # 🎯 PORTFOLIO SIZING ONLY - No fallback
                if not portfolio_margins or i-1 >= len(portfolio_margins):
                    failed_trades += 1
                    display_execution_card(
                        i, len(signals_to_execute), symbol, signal, None, "FAILED",
                        "Portfolio margins not available"
                    )
                    logging.error(f"❌ {symbol_short}: Portfolio sizing unavailable - SKIP")
                    continue
                
                # Use precalculated margin from portfolio sizing
                target_margin = portfolio_margins[i-1]
                logging.debug(f"💰 Portfolio margin for {symbol_short}: ${target_margin:.2f}")
                
                # Calculate position size with precalculated margin
                notional_value = target_margin * config.LEVERAGE
                position_size = notional_value / current_price
                
                # 🛡️ PRE-FLIGHT: Check minimum notional
                from core.position_management.position_safety import MIN_POSITION_USD
                expected_notional = position_size * current_price
                
                if expected_notional < MIN_POSITION_USD:
                    display_execution_card(
                        i, len(signals_to_execute), symbol, signal, None, "SKIPPED",
                        f"Notional too low: ${expected_notional:.2f} < ${MIN_POSITION_USD:.0f}\n" +
                        f"    Price ${current_price:.2f} too high for IM ${target_margin:.0f}"
                    )
                    logging.info(colored(
                        f"⏭️ {symbol_short}: Price (${current_price:.2f}) → "
                        f"notional ${expected_notional:.2f} < ${MIN_POSITION_USD:.0f} → SKIP",
                        "yellow"
                    ))
                    continue
                
                # Create PositionLevels with portfolio margin
                from core.risk_calculator import PositionLevels
                levels = PositionLevels(
                    margin=target_margin,
                    position_size=position_size,
                    stop_loss=0,  # Calculated later
                    take_profit=0,  # Not used
                    risk_pct=0,
                    reward_pct=0,
                    risk_reward_ratio=0
                )
                
                # Portfolio margin check with beautiful card display
                if levels.margin > available_balance:
                    display_execution_card(i, len(signals_to_execute), symbol, signal, levels, "SKIPPED", f"Insufficient margin: ${levels.margin:.2f} > ${available_balance:.2f}")
                    
                    # FIX 3: Track consecutive balance failures for early exit
                    consecutive_insufficient_balance += 1
                    
                    # FIX 3: Early exit if too many consecutive failures
                    if consecutive_insufficient_balance >= MAX_CONSECUTIVE_BALANCE_FAILURES:
                        from core.enhanced_logging_system import enhanced_logger
                        enhanced_logger.display_table(
                            f"⚠️ EARLY EXIT: {consecutive_insufficient_balance} consecutive insufficient balance failures",
                            "yellow"
                        )
                        enhanced_logger.display_table(
                            f"💡 Available balance (${available_balance:.2f}) too low for remaining signals (need ~${levels.margin:.2f}+)",
                            "yellow"
                        )
                        break  # Stop trying more signals
                    
                    logging.debug(f"⏭️ Skipping {symbol_short} → trying next position ({consecutive_insufficient_balance}/{MAX_CONSECUTIVE_BALANCE_FAILURES} consecutive fails)...")
                    continue  # FIX 2: Try next position instead of stopping all execution

                # Show executing card
                display_execution_card(i, len(signals_to_execute), symbol, signal, levels, "EXECUTING")
                
                # 🆕 Execute the trade with PORTFOLIO MARGIN
                # Pass precalculated margin from portfolio sizing
                margin_to_use = portfolio_margins[i-1] if (portfolio_margins and i-1 < len(portfolio_margins)) else None
                
                result = await self.global_trading_orchestrator.execute_new_trade(
                    exchange, signal, market_data, available_balance, 
                    margin_override=margin_to_use
                )
                
                if result.success:
                    # Success card
                    display_execution_card(i, len(signals_to_execute), symbol, signal, levels, "SUCCESS")
                    executed_trades += 1
                    total_margin_used += levels.margin
                    available_balance -= levels.margin
                    consecutive_insufficient_balance = 0  # FIX 3: Reset counter on success
                    
                    # 📊 LOG DECISION TO DATABASE
                    if TRADE_DECISION_LOGGER_AVAILABLE:
                        try:
                            # Prepare market context
                            market_context = {
                                'volatility': volatility,
                                'rsi_position': latest_candle.get('rsi_fast', 50.0),
                                'trend_strength': latest_candle.get('adx', 25.0),
                                'volume_surge': 1.0  # TODO: Calculate actual volume surge
                            }
                            
                            # Prepare position details
                            position_details = {
                                'entry_price': current_price,
                                'position_size': levels.position_size,
                                'margin': levels.margin,
                                'stop_loss': levels.stop_loss,
                                'leverage': config.LEVERAGE
                            }
                            
                            # Prepare portfolio state
                            portfolio_state = {
                                'available_balance': available_balance,
                                'active_positions': open_positions_count
                            }
                            
                            # Prepare market snapshots from dataframes
                            market_snapshots = {}
                            for tf in ['15m', '30m', '1h']:
                                if tf in signal.get('dataframes', {}) and signal['dataframes'][tf] is not None:
                                    df_tf = signal['dataframes'][tf]
                                    if len(df_tf) > 0:
                                        market_snapshots[tf] = df_tf.iloc[-1]
                            
                            # Log decision
                            decision_id = global_trade_decision_logger.log_opening_decision(
                                signal_data=signal,
                                market_context=market_context,
                                position_details=position_details,
                                portfolio_state=portfolio_state,
                                market_snapshots=market_snapshots if market_snapshots else None
                            )
                            
                            if decision_id:
                                logging.debug(f"📊 Trade decision logged with ID: {decision_id}")
                        except Exception as log_error:
                            logging.warning(f"⚠️ Failed to log decision: {log_error}")
                else:
                    # Failed card  
                    display_execution_card(i, len(signals_to_execute), symbol, signal, levels, "FAILED", result.error)
                    failed_trades += 1
                    
                    # If it's a margin error, try next position (might be smaller)
                    if "margin limit" in result.error.lower() or "insufficient" in result.error.lower():
                        logging.debug(f"⏭️ Margin error on {symbol_short} → trying next position...")
                        continue  # FIX: Try next position instead of stopping all execution
                        
            except Exception as e:
                failed_trades += 1
                display_execution_card(i, len(signals_to_execute), signal["symbol"], signal, None, "FAILED", str(e)[:50])
                logging.error(f"❌ Error executing {signal['symbol']}: {e}")
                continue

        # STEP 7: BEAUTIFUL EXECUTION SUMMARY
        remaining_balance = available_balance
        display_execution_summary(executed_trades, len(signals_to_execute), total_margin_used, remaining_balance)

    async def _setup_trading_parameters_silent(self, exchange, signals_to_execute):
        """Setup trading parameters without verbose logging"""
        for signal in signals_to_execute:
            symbol = signal["symbol"]
            try:
                await exchange.set_leverage(config.LEVERAGE, symbol)
                await exchange.set_margin_mode("isolated", symbol)
            except Exception as e:
                # Only log actual errors, not "leverage not modified" warnings
                if "leverage not modified" not in str(e).lower():
                    logging.debug(f"⚠️ {symbol}: Param setup failed: {e}")

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

        # CRITICAL FIX: FORCED POSITION SYNC - Get real-time data from Bybit
        enhanced_logger.display_table("🔄 FORCED SYNC: Fetching real-time positions from Bybit", "cyan")
        if not config.DEMO_MODE:
            try:
                # Force sync with Bybit to get latest position data
                newly_opened, newly_closed = await self.position_manager.thread_safe_sync_with_bybit(exchange)
                if newly_opened or newly_closed:
                    logging.info(colored(
                        f"🔄 Position sync: {len(newly_opened)} new, {len(newly_closed)} closed",
                        "green"
                    ))
                else:
                    logging.debug("✅ Position sync: All positions up to date")
            except Exception as e:
                logging.warning(f"Position sync error: {e}")

        # 🎪 TRAILING STOP MANAGEMENT (every 60s)
        if not config.DEMO_MODE and config.TRAILING_ENABLED:
            try:
                # Initialize timestamp tracker if not exists
                if not hasattr(self, '_last_trailing_update'):
                    self._last_trailing_update = 0
                
                current_time = time.time()
                time_since_last_update = current_time - self._last_trailing_update
                
                # Update trailing stops every 60s
                if time_since_last_update >= config.TRAILING_UPDATE_INTERVAL:
                    updates_count = await self.position_manager.update_trailing_stops(exchange)
                    self._last_trailing_update = current_time
                    
                    if updates_count > 0 and not config.TRAILING_SILENT_MODE:
                        enhanced_logger.display_table(
                            f"🎪 Trailing stops updated: {updates_count} positions", 
                            "cyan"
                        )
            except Exception as trailing_error:
                logging.error(f"Trailing stops update error: {trailing_error}")

        # 🔧 AUTO-FIX STOP LOSSES (every cycle)
        if not config.DEMO_MODE:
            try:
                fixed_sl_count = await self.position_manager.check_and_fix_stop_losses(exchange)
                if fixed_sl_count > 0:
                    enhanced_logger.display_table(f"🔧 {fixed_sl_count} stop losses auto-corrected", "green")
            except Exception as fix_error:
                logging.error(f"SL auto-fix error: {fix_error}")
        
        # Safety manager - MIGRATED to position_manager
        if not config.DEMO_MODE:
            try:
                closed_unsafe = await self.position_manager.check_and_close_unsafe_positions(exchange)
                if closed_unsafe > 0:
                    enhanced_logger.display_table(f"🛡️ {closed_unsafe} unsafe positions closed", "yellow")
            except Exception as safety_error:
                logging.error(f"Position safety check error: {safety_error}")

    async def _update_realtime_display(self, exchange):
        from core.enhanced_logging_system import enhanced_logger

        if not hasattr(self, "realtime_display") or self.realtime_display is None:
            try:
                self.realtime_display = initialize_global_realtime_display(
                    self.position_manager if self.clean_modules_available else None
                )
                enhanced_logger.display_table("📊 Realtime display initialized", "cyan")
            except Exception as init_error:
                logging.error(f"❌ Failed to initialize realtime display: {init_error}")
                self.realtime_display = None

        if self.realtime_display:
            try:
                await self.realtime_display.update_snapshot(exchange)
                # Show REAL Bybit data instead of cached session data
                self.realtime_display.show_snapshot()
            except Exception as e:
                logging.error(f"❌ Snapshot display failed: {e}")

    async def run_continuous_trading(self, exchange, xgb_models, xgb_scalers):
        """
        Run continuous trading with OPTIMIZED task management (FIX #6: Anti-Freeze)
        
        PERFORMANCE MODE (default):
        - Trading cycle (every 15 min)
        - Trailing monitor (optional, every 30s) 
        - Balance sync (optional, every 60s)
        - Dashboard DISABLED (too heavy)
        """
        
        # Initialize session balance for statistics
        if self.session_stats:
            if not config.DEMO_MODE:
                real_balance = await get_real_balance(exchange)
                if real_balance and real_balance > 0:
                    self.session_stats.initialize_balance(real_balance)
                    logging.info(f"📊 Session stats initialized with ${real_balance:.2f}")
            else:
                self.session_stats.initialize_balance(config.DEMO_BALANCE)
                logging.info(f"📊 Session stats initialized with ${config.DEMO_BALANCE:.2f} (DEMO)")
        
        # FIX #6: Selective task activation based on config
        tasks = []
        active_components = ["Trading Loop"]
        
        # Always include trading loop
        trading_task = asyncio.create_task(self._trading_loop(exchange, xgb_models, xgb_scalers))
        tasks.append(trading_task)
        
        # Optional: Trailing monitor (lightweight)
        if config.TRAILING_BACKGROUND_ENABLED and INTEGRATED_SYSTEMS_AVAILABLE and self.session_stats:
            trailing_task = asyncio.create_task(
                run_integrated_trailing_monitor(exchange, self.position_manager, self.session_stats)
            )
            tasks.append(trailing_task)
            active_components.append("Trailing Monitor")
        else:
            logging.info("📊 Trailing monitor: DISABLED (managed in-cycle)")
        
        # Dashboard removed - Terminal output only
        logging.info("🖥️ Output: Terminal only (no dashboard)")
        
        # Optional: Balance sync (lightweight)
        if config.BALANCE_SYNC_ENABLED and not config.DEMO_MODE:
            balance_sync_task = asyncio.create_task(self._balance_sync_loop(exchange))
            tasks.append(balance_sync_task)
            active_components.append("Balance Sync (60s)")
        else:
            logging.info("💰 Background balance sync: DISABLED (synced in-cycle)")
        
        logging.info(colored(
            f"🚀 PERFORMANCE MODE: {' + '.join(active_components)}",
            "green", attrs=['bold']
        ))
        
        try:
            # Run selected tasks in parallel
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logging.info("⛔ Trading stopped by user")
            # Cancel all tasks gracefully
            for task in tasks:
                task.cancel()
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except:
                pass
        except Exception as e:
            logging.error(f"❌ Error in trading system: {e}", exc_info=True)
    
    async def _balance_sync_loop(self, exchange):
        """
        Balance sync loop (every 60 seconds)
        
        Syncs real balance from Bybit every 60 seconds to keep it accurate.
        Runs as background task in parallel with trading loop.
        """
        if not self.clean_modules_available:
            logging.warning("⚠️ Balance sync disabled (position manager not available)")
            return
        
        if config.DEMO_MODE:
            logging.info("🧪 DEMO MODE: Balance sync disabled")
            return
        
        SYNC_INTERVAL = 60  # 60 seconds
        logging.info(f"💰 Balance sync started (interval: {SYNC_INTERVAL}s)")
        
        while True:
            try:
                await asyncio.sleep(SYNC_INTERVAL)
                
                # Fetch real balance from Bybit
                real_balance = await get_real_balance(exchange)
                
                if real_balance and real_balance > 0:
                    # Update position manager (single source of truth)
                    old_balance = self.position_manager.safe_get_session_summary().get('balance', 0.0)
                    self.position_manager.update_real_balance(real_balance)
                    
                    # Log only if there's a significant change (> $1)
                    balance_change = abs(real_balance - old_balance)
                    if balance_change > 1.0:
                        logging.info(colored(
                            f"💰 Balance synced: ${old_balance:.2f} → ${real_balance:.2f} "
                            f"({real_balance - old_balance:+.2f})",
                            "cyan"
                        ))
                    else:
                        logging.debug(f"💰 Balance synced: ${real_balance:.2f}")
                    
            except asyncio.CancelledError:
                # Task was cancelled (normal shutdown)
                logging.info("💰 Balance sync stopped")
                break
            except Exception as e:
                logging.error(f"❌ Balance sync error: {e}")
                # Continue loop despite error
                await asyncio.sleep(SYNC_INTERVAL)
    
    async def _trading_loop(self, exchange, xgb_models, xgb_scalers):
        """Internal trading loop (runs every 15 min)"""
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                
                # 🕐 TIMESTAMP SYNC every 5 cycles to prevent drift
                if cycle_count % 5 == 0:
                    from core.time_sync_manager import global_time_sync_manager
                    logging.info(colored(f"🕐 CYCLE {cycle_count}: Forcing timestamp sync...", "yellow"))
                    sync_success = await global_time_sync_manager.force_time_sync(exchange)
                    if sync_success:
                        logging.info(colored("✅ Timestamp sync successful", "green"))
                    else:
                        logging.warning(colored("⚠️ Timestamp sync failed - continuing anyway", "yellow"))
                
                await self.run_trading_cycle(exchange, xgb_models, xgb_scalers)
                await self._wait_with_countdown(config.TRADE_CYCLE_INTERVAL)
            except KeyboardInterrupt:
                logging.info("⛔ Trading loop stopped")
                break
            except Exception as e:
                logging.error(f"❌ Error in trading cycle: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _wait_with_countdown(self, total_seconds: int):
        """Clean countdown with minimal logging - shows every minute"""
        from core.enhanced_logging_system import enhanced_logger

        # Log only the start
        minutes_total = total_seconds // 60
        logging.info(f"ℹ️ ⏸️ WAITING {minutes_total}m until next cycle...")
        
        remaining = total_seconds
        last_logged_minute = -1
        last_displayed_minute = -1

        while remaining > 0:
            minutes, seconds = divmod(remaining, 60)
            
            # Display countdown every minute (or at significant milestones)
            should_display = (
                minutes != last_displayed_minute or  # New minute
                remaining <= 10 or  # Final 10 seconds
                remaining % 60 == 0  # Every minute boundary
            )
            
            if should_display:
                countdown_text = f"⏰ Next cycle in: {minutes}m{seconds:02d}s"
                print(f"\r{colored(countdown_text, 'magenta')}", end="", flush=True)
                last_displayed_minute = minutes

            # Log only significant milestones to avoid spam
            if minutes != last_logged_minute and minutes in [10, 5, 2, 1]:
                logging.info(f"ℹ️ ⏰ Next cycle in: {minutes}m{seconds:02d}s")
                last_logged_minute = minutes
            elif remaining == 10:
                logging.info("ℹ️ ⏰ Next cycle in: 0m10s")

            await asyncio.sleep(1)
            remaining -= 1

        # Clear the countdown line and log completion
        print("\r" + " " * 50 + "\r", end="", flush=True)
        logging.info("🚀 Starting next cycle...")
