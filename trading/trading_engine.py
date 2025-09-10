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
from utils.timing_utils import countdown_timer
from trade_manager import get_real_balance
import config


class TradingEngine:
    """
    Main trading engine that orchestrates the complete trading process
    """
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.first_cycle = True
        
        # Initialize components
        self.market_analyzer = global_market_analyzer
        self.signal_processor = global_signal_processor
        
        # Initialize optional components
        self.enhanced_display_available = self._init_enhanced_display()
        self.database_system_loaded = self._init_database_system()
        self.clean_modules_available = self._init_clean_modules()
        
    def _init_enhanced_display(self):
        """Initialize enhanced display system if available"""
        try:
            from core.terminal_display import (
                init_terminal_display, display_enhanced_signal, 
                display_analysis_progress, display_cycle_complete,
                display_model_status, display_portfolio_status, terminal_display,
                display_wallet_and_positions
            )
            self.terminal_display = terminal_display
            self.display_cycle_complete = display_cycle_complete
            return True
        except ImportError:
            logging.warning("⚠️ Enhanced Terminal Display not available")
            return False
    
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
        
        Args:
            exchange: Exchange instance
        """
        logging.info(colored("🧹 FRESH SESSION STARTUP", "cyan", attrs=['bold']))
        
        # Reset all internal position tracking
        logging.info(colored("🧹 Clearing internal position tracking...", "yellow"))
        if self.clean_modules_available:
            self.position_manager.reset_session()
        
        # Sync balance
        real_balance = await get_real_balance(exchange)
        if real_balance and real_balance > 0:
            if self.clean_modules_available:
                self.position_manager.update_real_balance(real_balance)
            logging.info(colored(f"💰 Position manager balance synced: ${real_balance:.2f}", "green"))
        else:
            logging.warning("⚠️ Could not sync real balance - using fallback")
        
        logging.info(colored("✅ Internal tracking reset - ready for fresh sync", "green"))
        
        # Handle existing positions
        if config.DEMO_MODE:
            logging.info(colored("🎮 Demo mode: Fresh session started", "magenta"))
        else:
            logging.info(colored("🔄 SYNCING WITH REAL BYBIT POSITIONS", "cyan"))
            if self.clean_modules_available:
                protection_results = await self.global_trading_orchestrator.protect_existing_positions(exchange)
                
                if protection_results:
                    successful = sum(1 for result in protection_results.values() if result.success)
                    total = len(protection_results)
                    logging.info(colored(f"🛡️ Live mode: {successful}/{total} existing positions protected", "cyan"))
                else:
                    logging.info(colored("🆕 Live mode: No existing positions - starting fresh", "green"))
        
        logging.info(colored("-" * 80, "cyan"))

    async def run_trading_cycle(self, exchange, xgb_models, xgb_scalers):
        """
        Execute one complete trading cycle
        
        Args:
            exchange: Exchange instance
            xgb_models: Dictionary of XGBoost models
            xgb_scalers: Dictionary of scalers
        """
        cycle_start_time = time.time()
        
        try:
            # Phase 1: Data Collection
            all_symbol_data, complete_symbols, data_fetch_time = await self.market_analyzer.collect_market_data(
                exchange, 
                self.config_manager.get_timeframes(),
                config.TOP_ANALYSIS_CRYPTO,
                config.EXCLUDED_SYMBOLS
            )
            
            if not complete_symbols:
                logging.warning(colored("⚠️ No symbols with complete data this cycle", "yellow"))
                return
            
            # Phase 2: ML Predictions
            prediction_results, ml_time = await self.market_analyzer.generate_ml_predictions(
                xgb_models, xgb_scalers, config.TIME_STEPS
            )
            
            # Phase 3: Signal Processing & Analysis Display
            self.signal_processor.display_complete_analysis(prediction_results, all_symbol_data)
            
            # Process signals for execution
            all_signals = await self.signal_processor.process_prediction_results(
                prediction_results, all_symbol_data
            )
            
            # Phase 4: Signal Ranking and Display
            logging.info(colored("📈 PHASE 2: RANKING AND SELECTING TOP SIGNALS", "green", attrs=['bold']))
            display_top_signals(all_signals, limit=10)
            
            # Phase 5: Signal Execution
            await self._execute_signals(exchange, all_signals)
            
            # Phase 6: Position Management
            await self._manage_positions(exchange)
            
            # Performance Summary
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
            
            # Display database stats on first cycle
            if self.first_cycle:
                self.first_cycle = False
                if self.database_system_loaded:
                    self.display_database_stats()
            
            # Show cycle complete
            if self.enhanced_display_available:
                self.display_cycle_complete()
            
            logging.info(colored("🔄 Cycle complete - waiting for next cycle", "green"))
            
        except Exception as e:
            logging.error(f"Error in trading cycle: {e}")
            raise

    async def _execute_signals(self, exchange, all_signals):
        """
        Execute trading signals with position limits and balance management
        
        Args:
            exchange: Exchange instance
            all_signals: List of signals to execute
        """
        if not all_signals:
            logging.info(colored("😐 No signals to execute this cycle", "yellow"))
            return
        
        # Get current balance and position count
        usdt_balance = await get_real_balance(exchange)
        if usdt_balance is None:
            logging.warning(colored("⚠️ Failed to get USDT balance", "yellow"))
            return
        
        # Get open positions count
        if self.clean_modules_available:
            open_positions_count = self.position_manager.get_position_count()
        else:
            try:
                positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
                open_positions_count = len([p for p in positions if float(p.get('contracts', 0)) > 0])
            except Exception as e:
                logging.warning(f"Could not get position count: {e}")
                open_positions_count = 0
        
        # Calculate maximum new positions
        max_positions = config.MAX_CONCURRENT_POSITIONS - open_positions_count
        signals_to_execute = all_signals[:min(max_positions, len(all_signals))]
        
        if not signals_to_execute:
            logging.info(colored("⚠️ Maximum positions reached, no new signals to execute", "yellow"))
            return
        
        logging.info(colored(f"🚀 PHASE 3: EXECUTING TOP {len(signals_to_execute)} SIGNALS", "blue", attrs=['bold']))
        
        # Set leverage and margin mode
        await self._setup_trading_parameters(exchange, signals_to_execute)
        
        # Execute signals
        executed_trades = 0
        
        for signal in signals_to_execute:
            try:
                if not self.clean_modules_available:
                    logging.warning("⚠️ Clean modules not available, skipping execution")
                    break
                
                symbol = signal['symbol']
                
                # Check if we can open new position
                can_open, reason = self.global_trading_orchestrator.can_open_new_position(symbol, usdt_balance)
                if not can_open:
                    logging.warning(colored(f"⚠️ {symbol}: {reason}", "yellow"))
                    continue
                
                # Get market data
                df = signal['dataframes'][self.config_manager.get_default_timeframe()]
                if df is None or len(df) == 0:
                    logging.warning(f"⚠️ {symbol}: No market data available")
                    continue
                
                latest_candle = df.iloc[-1]
                current_price = latest_candle.get('close', 0)
                atr = latest_candle.get('atr', current_price * 0.003)  # 0.3% fallback
                volatility = latest_candle.get('volatility', 0.0)
                
                market_data = self.MarketData(
                    price=current_price,
                    atr=atr,
                    volatility=volatility
                )
                
                # Calculate required margin
                levels = self.global_risk_calculator.calculate_position_levels(
                    market_data, signal['signal_name'].lower(), signal['confidence'], usdt_balance
                )
                
                # Check balance sufficiency
                if levels.margin > usdt_balance:
                    logging.warning(colored(f"⚠️ {symbol}: Insufficient balance ${usdt_balance:.2f} < ${levels.margin:.2f} margin required", "yellow"))
                    break
                
                # Execute trade
                result = await self.global_trading_orchestrator.execute_new_trade(
                    exchange, signal, market_data, usdt_balance
                )
                
                if result.success:
                    executed_trades += 1
                    usdt_balance -= levels.margin
                    logging.info(colored(f"✅ {symbol}: Trade successful - Position: {result.position_id}", "green"))
                    logging.info(colored(f"💰 Balance updated: ${usdt_balance:.2f} remaining (used ${levels.margin:.2f} margin)", "cyan"))
                else:
                    logging.warning(colored(f"❌ {symbol}: {result.error}", "yellow"))
                    
                    if "insufficient balance" in result.error.lower() or "ab not enough" in result.error.lower():
                        logging.warning(colored(f"💸 Balance exhausted after {executed_trades} trades - stopping execution", "yellow"))
                        break
                    elif "maximum" in result.error.lower():
                        break
                
            except Exception as e:
                logging.error(f"❌ Error executing {signal['symbol']}: {e}")
                continue
        
        # Log execution summary
        if executed_trades > 0:
            logging.info(colored(f"📊 EXECUTION SUMMARY: {executed_trades}/{len(signals_to_execute)} signals executed successfully", "green"))

    async def _setup_trading_parameters(self, exchange, signals_to_execute):
        """
        Set leverage and margin mode for trading symbols
        
        Args:
            exchange: Exchange instance
            signals_to_execute: List of signals to execute
        """
        logging.info(colored("⚖️ SETTING 10x LEVERAGE + ISOLATED MARGIN for all trading symbols...", "yellow"))
        
        for signal in signals_to_execute:
            symbol = signal['symbol']
            try:
                # Set leverage
                await exchange.set_leverage(config.LEVERAGE, symbol)
                logging.info(colored(f"✅ {symbol}: Leverage set to {config.LEVERAGE}x", "green"))
                
                # Set margin mode to ISOLATED
                try:
                    await exchange.set_margin_mode('isolated', symbol)
                    logging.info(colored(f"🔒 {symbol}: Margin mode set to ISOLATED", "green"))
                except Exception as margin_error:
                    logging.warning(colored(f"⚠️ {symbol}: Could not set isolated margin: {margin_error}", "yellow"))
                    
            except Exception as lev_error:
                logging.warning(colored(f"⚠️ {symbol}: Could not set leverage to {config.LEVERAGE}x: {lev_error}", "yellow"))

    async def _manage_positions(self, exchange):
        """
        Manage existing positions - sync and trailing stops
        
        Args:
            exchange: Exchange instance
        """
        if not self.clean_modules_available:
            return
        
        # Position sync with Bybit
        if not config.DEMO_MODE:
            try:
                newly_opened, newly_closed = await self.position_manager.sync_with_bybit(exchange)
                
                if newly_opened or newly_closed:
                    logging.info(colored(f"🔄 Position sync: +{len(newly_opened)} opened, +{len(newly_closed)} closed", "cyan"))
                
            except Exception as sync_error:
                logging.warning(f"Position sync error: {sync_error}")
        
        # Update trailing stop system
        try:
            closed_positions = await self.global_trading_orchestrator.update_trailing_positions(exchange)
            
            # Log trailing exits
            for position in closed_positions:
                logging.info(colored(f"🎯 Trailing Exit: {position.symbol} {position.side.upper()} @ ${position.current_price:.6f}", "green"))
                logging.info(colored(f"   💰 Final PnL: {position.unrealized_pnl_pct:+.2f}% (${position.unrealized_pnl_usd:+.2f})", 
                                   "green" if position.unrealized_pnl_pct > 0 else "red"))
                
        except Exception as trailing_error:
            logging.warning(f"Trailing system error: {trailing_error}")

    async def run_continuous_trading(self, exchange, xgb_models, xgb_scalers):
        """
        Run continuous trading cycles
        
        Args:
            exchange: Exchange instance
            xgb_models: Dictionary of XGBoost models
            xgb_scalers: Dictionary of scalers
        """
        while True:
            try:
                await self.run_trading_cycle(exchange, xgb_models, xgb_scalers)
                await countdown_timer(config.TRADE_CYCLE_INTERVAL)
                
            except KeyboardInterrupt:
                logging.info(colored("Interrupt signal received. Shutting down...", "red"))
                break
            except Exception as e:
                logging.error(f"Error in trading cycle: {e}")
                await asyncio.sleep(60)  # Wait before retry
