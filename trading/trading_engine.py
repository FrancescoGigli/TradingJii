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


class TradingEngine:
    """
    Main trading engine che orchestra l’intero processo di trading
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
        Execute one complete trading cycle
        """
        cycle_start_time = time.time()

        try:
            # Phase 1: Data collection
            all_symbol_data, complete_symbols, data_fetch_time = await self.market_analyzer.collect_market_data(
                exchange,
                self.config_manager.get_timeframes(),
                config.TOP_ANALYSIS_CRYPTO,
                config.EXCLUDED_SYMBOLS
            )
            if not complete_symbols:
                logging.warning("⚠️ No symbols with complete data this cycle")
                return

            # Phase 2: ML predictions
            prediction_results, ml_time = await self.market_analyzer.generate_ml_predictions(
                xgb_models, xgb_scalers, config.get_timesteps_for_timeframe(self.config_manager.get_default_timeframe())
            )

            # Phase 3: Signal processing
            self.signal_processor.display_complete_analysis(prediction_results, all_symbol_data)
            all_signals = await self.signal_processor.process_prediction_results(
                prediction_results, all_symbol_data
            )

            # Phase 4: Ranking
            logging.info(colored("📈 PHASE 2: RANKING AND SELECTING TOP SIGNALS", "green", attrs=['bold']))
            display_top_signals(all_signals, limit=10)

            # Phase 5: Execution
            await self._execute_signals(exchange, all_signals)

            # Phase 6: Manage positions
            await self._manage_positions(exchange)

            # Phase 7: Performance summary
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

            if self.first_cycle:
                self.first_cycle = False
                if self.database_system_loaded:
                    self.display_database_stats()

            # ── NEW: snapshot realtime_display (open + closed) ──
            # Inicializza il display se non esiste
            if not hasattr(self, 'realtime_display') or self.realtime_display is None:
                try:
                    trailing_monitor = getattr(self, 'trailing_monitor', None)
                    self.realtime_display = initialize_global_realtime_display(
                        self.position_manager if self.clean_modules_available else None,
                        trailing_monitor
                    )
                    logging.info(colored("📊 Realtime display initialized for cycle", "cyan"))
                except Exception as init_error:
                    logging.error(f"❌ Failed to initialize realtime display: {init_error}")
                    self.realtime_display = None
            
            if self.realtime_display:
                try:
                    logging.info(colored("📊 UPDATING POSITION DISPLAY...", "cyan"))
                    await self.realtime_display.update_snapshot(exchange)
                    self.realtime_display.show_snapshot()
                    logging.info(colored("📊 Position display updated", "cyan"))
                except Exception as e:
                    logging.error(f"❌ Snapshot display failed: {e}")
            else:
                logging.warning("⚠️ Realtime display not available")

            logging.info(colored("🔄 Cycle complete", "green"))

        except Exception as e:
            logging.error(f"Error in trading cycle: {e}")
            raise

    async def _execute_signals(self, exchange, all_signals):
        """
        Execute trading signals
        """
        if not all_signals:
            logging.info(colored("😐 No signals to execute this cycle", "yellow"))
            return

        usdt_balance = await get_real_balance(exchange)
        if usdt_balance is None:
            logging.warning("⚠️ Failed to get USDT balance")
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
            logging.info("⚠️ Maximum positions reached, no new signals")
            return

        logging.info(colored(f"🚀 PHASE 3: EXECUTING {len(signals_to_execute)} SIGNALS", "blue", attrs=['bold']))
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
            logging.info(colored(f"📊 EXECUTION SUMMARY: {executed_trades} signals executed", "green"))

    async def _setup_trading_parameters(self, exchange, signals_to_execute):
        logging.info("⚖️ Setting leverage + isolated margin")
        for signal in signals_to_execute:
            symbol = signal['symbol']
            try:
                await exchange.set_leverage(config.LEVERAGE, symbol)
                await exchange.set_margin_mode('isolated', symbol)
            except Exception as e:
                logging.warning(f"⚠️ {symbol}: Param setup failed: {e}")

    async def _manage_positions(self, exchange):
        if not self.clean_modules_available:
            return
        if not config.DEMO_MODE:
            try:
                newly_opened, newly_closed = await self.position_manager.sync_with_bybit(exchange)
                if newly_opened or newly_closed:
                    logging.info(f"🔄 Position sync: +{len(newly_opened)} opened, +{len(newly_closed)} closed")
            except Exception as e:
                logging.warning(f"Position sync error: {e}")
        try:
            closed_positions = await self.global_trading_orchestrator.update_trailing_positions(exchange)
            for pos in closed_positions:
                logging.info(colored(f"🎯 Trailing Exit: {pos.symbol} {pos.side.upper()} {pos.unrealized_pnl_pct:+.2f}%", "green"))
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
        """
        logging.info(colored(f"⏸️ WAITING {total_seconds//60}m until next cycle...", "magenta", attrs=['bold']))
        
        remaining = total_seconds
        
        while remaining > 0:
            # Calcola tempo rimanente
            minutes = remaining // 60
            seconds = remaining % 60
            
            # 🔧 MONO-RIGA: Usa print con \r per sovrascrivere
            countdown_text = f"⏰ Next cycle in: {minutes}m{seconds:02d}s"
            print(f"\r{colored(countdown_text, 'magenta')}", end='', flush=True)
            
            # Sleep per 1 secondo per aggiornamento fluido
            await asyncio.sleep(1)
            remaining -= 1
        
        # Nuova riga dopo il countdown
        print()  # Fine riga
        logging.info(colored("🚀 Starting next cycle...", "cyan", attrs=['bold']))
