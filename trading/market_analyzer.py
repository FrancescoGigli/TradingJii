"""
Market Analyzer for the trading bot
Handles data collection, ML predictions, and market analysis
"""

import time
import logging
import asyncio
from termcolor import colored

from fetcher import fetch_markets, get_top_symbols, fetch_min_amounts, fetch_and_save_data
# CRITICAL FIX: Use robust ML predictor instead of fragile one
try:
    from core.ml_predictor import predict_signal_ensemble
    logging.debug("✅ Using robust ML predictor - crash protection enabled")
except ImportError:
    from predictor import predict_signal_ensemble
    logging.warning("⚠️ Using legacy fragile predictor - crash risk exists")
import config
from utils.display_utils import display_data_download_summary


class MarketAnalyzer:
    """
    Handles market data collection and ML prediction analysis
    """
    
    def __init__(self):
        self.all_symbol_data = {}
        self.complete_symbols = []
        self.top_symbols_analysis = []
        self.min_amounts = {}
        self.symbol_volumes = {}  # Store volume data for display
    
    async def collect_market_data(self, exchange, enabled_timeframes, top_analysis_crypto, excluded_symbols):
        """
        Collect and organize market data for analysis
        
        Args:
            exchange: Exchange instance
            enabled_timeframes: List of timeframes to collect
            top_analysis_crypto: Number of top symbols to analyze
            excluded_symbols: List of symbols to exclude
            
        Returns:
            tuple: (all_symbol_data, complete_symbols, top_symbols_analysis)
        """
        logging.info(colored("🚀 PHASE 1: PARALLEL DATA COLLECTION", "cyan", attrs=['bold']))

        # Get markets and filter symbols
        markets = await fetch_markets(exchange)
        
        if excluded_symbols:
            all_symbols_analysis = [m['symbol'] for m in markets.values() if m.get('quote') == 'USDT'
                                    and m.get('active') and m.get('type') == 'swap'
                                    and not any(excl in m['symbol'] for excl in excluded_symbols)]
        else:
            all_symbols_analysis = [m['symbol'] for m in markets.values() if m.get('quote') == 'USDT'
                                    and m.get('active') and m.get('type') == 'swap']
        
        self.top_symbols_analysis = await get_top_symbols(exchange, all_symbols_analysis, top_n=top_analysis_crypto)
        logging.info(f"{colored('📊 Analyzing symbols:', 'cyan')} {len(self.top_symbols_analysis)} total")

        # Optimized data fetching with clean output
        from core.enhanced_logging_system import enhanced_logger
        enhanced_logger.display_table("📥 DATA DOWNLOAD - Optimized Display", "yellow", attrs=['bold'])
        
        data_fetch_start = time.time()
        self.all_symbol_data = {}
        successful_downloads = 0
        
        # 🚀 ORGANIZED THREAD DOWNLOAD - 5 Threads with Symbol Lists
        from core.symbol_exclusion_manager import global_symbol_exclusion_manager
        
        # Filter excluded symbols first
        valid_symbols = []
        excluded_count = 0
        
        for symbol in self.top_symbols_analysis:
            if global_symbol_exclusion_manager.is_excluded(symbol):
                excluded_count += 1
            else:
                valid_symbols.append(symbol)
        
        if excluded_count > 0:
            enhanced_logger.display_table(f"🚫 Pre-filtered {excluded_count} excluded symbols", "yellow")
        
        # Use threaded download with organized display
        self.all_symbol_data = await self._fetch_with_thread_lists(
            exchange, valid_symbols, enabled_timeframes
        )
        
        successful_downloads = len(self.all_symbol_data)

        data_fetch_time = time.time() - data_fetch_start
        
        # Display download summary
        display_data_download_summary(successful_downloads, len(self.top_symbols_analysis), data_fetch_time)

        # Filter symbols with complete data for all timeframes
        self.complete_symbols = list(self.all_symbol_data.keys())
        
        logging.info(f"📊 Symbols with complete data ready for analysis: {len(self.complete_symbols)}")
        
        return self.all_symbol_data, self.complete_symbols, data_fetch_time

    async def generate_ml_predictions(self, xgb_models, xgb_scalers, time_steps):
        """
        Generate ML predictions for all symbols with complete data
        """
        if not self.complete_symbols:
            logging.warning(colored("⚠️ No symbols with complete data this cycle", "yellow"))
            return {}, 0
        
        # Enhanced dynamic phase header with market insights
        total_symbols = len(self.complete_symbols)
        estimated_time = total_symbols * 3.5  # ~3.5 seconds per symbol
        
        logging.info(colored("🎯 PHASE 2: AI MARKET INTELLIGENCE ANALYSIS", "cyan", attrs=['bold']))
        logging.info(colored(f"📊 Scanning {total_symbols} crypto assets • Est. {estimated_time:.0f}s", "cyan"))
        logging.info(colored("🔍 Evaluating technical patterns, volume trends & market momentum", "cyan"))
        
        ml_start_time = time.time()
        prediction_results = {}
        
        # Dynamic wait messages for variety
        wait_messages = [
            "🔬 Processing market microstructure...",
            "📈 Evaluating price action signals...",
            "⚡ Computing momentum indicators...",
            "🎲 Analyzing risk/reward ratios...",
            "💡 Cross-referencing market patterns...",
            "🧮 Calculating probability distributions...",
            "🌊 Reading market sentiment waves...",
            "🔮 Forecasting trend continuations..."
        ]
        
        # Sequential predictions with enhanced logging
        for i, symbol in enumerate(self.complete_symbols, 1):
            symbol_short = symbol.replace('/USDT:USDT', '')
            
            # More expressive analysis header with context
            logging.info(colored(f"🎯 [{i:2d}/{total_symbols:2d}] {symbol_short:12s} • Deep Learning Analysis", "magenta", attrs=['bold']))
            
            # Get symbol data for context
            dataframes = self.all_symbol_data[symbol]
            
            # Perform prediction
            start_prediction = time.time()
            result = predict_signal_ensemble(dataframes, xgb_models, xgb_scalers, symbol, time_steps)
            prediction_time = time.time() - start_prediction
            
            prediction_results[symbol] = result
            
            # Enhanced result logging with insights
            if result and len(result) >= 3:
                confidence, signal, individual_preds = result
                if confidence is not None and signal is not None:
                    signal_names = {0: 'SELL 🔴', 1: 'BUY 🟢', 2: 'NEUTRAL 🟡'}
                    signal_name = signal_names.get(signal, 'UNKNOWN')
                    logging.info(colored(f"   💡 Prediction: {signal_name} • Confidence: {confidence:.1%} • {prediction_time:.2f}s", "white"))
                else:
                    logging.info(colored(f"   ⚠️  Analysis inconclusive • Market data insufficient", "yellow"))
            else:
                logging.info(colored(f"   ❌ Analysis failed • Technical error occurred", "red"))
            
            # Enhanced wait messaging (skip for last symbol)
            if i < total_symbols:
                message_idx = (i - 1) % len(wait_messages)
                wait_msg = wait_messages[message_idx]
                remaining = total_symbols - i
                eta_remaining = remaining * 3.5
                
                logging.info(colored(f"   {wait_msg} • {remaining} remaining • ~{eta_remaining:.0f}s ETA", "cyan"))
                await asyncio.sleep(3)

        ml_time = time.time() - ml_start_time
        
        # Final summary with market insights
        successful_predictions = sum(1 for result in prediction_results.values() 
                                   if result and len(result) >= 2 and result[0] is not None)
        
        logging.info(colored(f"🎯 AI Analysis Complete: {successful_predictions}/{total_symbols} successful • {ml_time:.1f}s total", "green", attrs=['bold']))
        
        return prediction_results, ml_time

    async def initialize_markets(self, exchange, top_analysis_crypto, excluded_symbols):
        """
        Initialize market data and get top symbols for analysis
        """
        try:
            markets = await fetch_markets(exchange)
            all_symbols = [m['symbol'] for m in markets.values() if m.get('quote') == 'USDT'
                           and m.get('active') and m.get('type') == 'swap']
            
            if excluded_symbols:
                all_symbols_analysis = [s for s in all_symbols if not any(excl in s for excl in excluded_symbols)]
            else:
                all_symbols_analysis = all_symbols

            # Get top symbols with volumes for display
            self.top_symbols_analysis, self.symbol_volumes = await self._get_top_symbols_with_volumes(
                exchange, all_symbols_analysis, top_n=top_analysis_crypto
            )
            
            # Get minimum amounts
            self.min_amounts = await fetch_min_amounts(exchange, self.top_symbols_analysis, markets)
            
            logging.debug(f"✅ Initialized {len(self.top_symbols_analysis)} symbols for analysis")
            
            return self.min_amounts
            
        except Exception as e:
            logging.error(f"Market initialization error: {e}")
            raise

    def get_symbol_data(self, symbol):
        """Get dataframes for a specific symbol"""
        return self.all_symbol_data.get(symbol, {})

    def get_complete_symbols(self):
        """Get list of symbols with complete data"""
        return self.complete_symbols.copy()

    def get_top_symbols(self):
        """Get list of top symbols for analysis"""
        return self.top_symbols_analysis.copy()

    def get_volumes_data(self):
        """Get volume data for display"""
        return self.symbol_volumes.copy()
    
    async def _get_top_symbols_with_volumes(self, exchange, all_symbols, top_n):
        """Get top symbols sorted by volume and store volume data"""
        try:
            # Use fetcher's get_top_symbols but collect volume data
            from fetcher import fetch_ticker_volume
            from asyncio import Semaphore
            
            # Parallel ticker volume fetching with rate limiting
            semaphore = Semaphore(20)  # Max 20 concurrent requests
            
            async def fetch_with_semaphore(symbol):
                async with semaphore:
                    return await fetch_ticker_volume(exchange, symbol)
            
            tasks = [fetch_with_semaphore(symbol) for symbol in all_symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and None values, store volumes
            symbol_volumes = []
            volumes_dict = {}
            
            for result in results:
                if isinstance(result, tuple) and result[1] is not None:
                    symbol, volume = result
                    symbol_volumes.append(result)
                    volumes_dict[symbol] = volume
            
            # Sort by volume and get top symbols
            symbol_volumes.sort(key=lambda x: x[1], reverse=True)
            top_symbols = [x[0] for x in symbol_volumes[:top_n]]
            
            logging.debug(f"🚀 Parallel ticker fetch: {len(symbol_volumes)} symbols processed concurrently")
            
            return top_symbols, volumes_dict
            
        except Exception as e:
            logging.error(f"Error getting top symbols with volumes: {e}")
            # Fallback to basic method
            top_symbols = await get_top_symbols(exchange, all_symbols, top_n)
            return top_symbols, {}

    async def _fetch_with_thread_lists(self, exchange, symbols, timeframes):
        """
        🚀 Organized download with thread bars
        Shows each thread's progress bar and symbol list
        """
        from core.enhanced_logging_system import enhanced_logger
        
        # Divide symbols into 5 thread groups
        thread_size = len(symbols) // 5
        remainder = len(symbols) % 5
        
        thread_groups = []
        start_idx = 0
        
        for i in range(5):
            current_size = thread_size + (1 if i < remainder else 0)
            end_idx = start_idx + current_size
            thread_symbols = symbols[start_idx:end_idx]
            
            thread_groups.append({
                'id': i + 1,
                'symbols': thread_symbols,
                'completed': 0,
                'current_symbol': None,
                'status': 'ready'
            })
            start_idx = end_idx
        
        # Display initial thread assignments
        enhanced_logger.display_table("📊 THREAD ASSIGNMENTS:", "cyan", attrs=['bold'])
        for group in thread_groups:
            symbol_names = [s.replace('/USDT:USDT', '') for s in group['symbols']]
            enhanced_logger.display_table(f"Thread {group['id']}: {', '.join(symbol_names)}", "white")
        enhanced_logger.display_table("")
        
        # Track progress
        all_data = {}
        total_completed = 0
        start_time = time.time()
        
        async def process_thread_group(group):
            """Process one thread group"""
            nonlocal total_completed
            
            thread_id = group['id']
            
            for symbol in group['symbols']:
                symbol_short = symbol.replace('/USDT:USDT', '')
                group['current_symbol'] = symbol_short
                group['status'] = 'processing'
                
                # Show thread progress bars
                self._display_thread_bars(thread_groups, total_completed, len(symbols))
                
                # Download timeframes
                symbol_data = {}
                success_count = 0
                
                for tf in timeframes:
                    try:
                        df = await fetch_and_save_data(exchange, symbol, tf)
                        if df is not None and len(df) > 100:
                            symbol_data[tf] = df
                            success_count += 1
                    except Exception as e:
                        logging.debug(f"[T{thread_id}] Error fetching {symbol}[{tf}]: {e}")
                
                # Mark completion
                if success_count == len(timeframes):
                    all_data[symbol] = symbol_data
                    group['completed'] += 1
                    total_completed += 1
                    
                    # Show updated bars after each completion
                    self._display_thread_bars(thread_groups, total_completed, len(symbols))
            
            group['status'] = 'done'
            group['current_symbol'] = None
            enhanced_logger.display_table(f"✅ Thread {thread_id} completed: {group['completed']}/{len(group['symbols'])} symbols", "green", attrs=['bold'])
        
        # Start with initial bars
        self._display_thread_bars(thread_groups, 0, len(symbols))
        
        # Execute all threads
        tasks = [process_thread_group(group) for group in thread_groups]
        await asyncio.gather(*tasks)
        
        return all_data

    def _display_thread_bars(self, thread_groups, total_completed, total_symbols):
        """Display progress bars for each thread with in-place updates"""
        from core.enhanced_logging_system import enhanced_logger
        
        # Rate limit (every 5 seconds or significant change)
        current_time = time.time()
        if not hasattr(self, '_last_bar_update'):
            self._last_bar_update = 0
            self._last_bar_completed = 0
            self._bars_displayed = False
        
        time_since_last = current_time - self._last_bar_update
        completion_change = total_completed - self._last_bar_completed
        
        # Show initial display or update every 5 seconds/5 completions
        if not self._bars_displayed or time_since_last >= 5.0 or completion_change >= 5:
            self._last_bar_update = current_time
            self._last_bar_completed = total_completed
            
            # Build the complete table as colored strings
            lines = []
            lines.append(colored("┌────────────────────────────────────────────────────────────────────┐", "cyan"))
            
            for group in thread_groups:
                thread_id = group['id']
                completed = group['completed']
                total_in_thread = len(group['symbols'])
                current_symbol = group['current_symbol']
                
                # Progress bar (10 chars)
                progress_pct = (completed / total_in_thread) if total_in_thread > 0 else 0
                filled = int(progress_pct * 10)
                bar = "█" * filled + "░" * (10 - filled)
                
                # Status display
                if group['status'] == 'done':
                    status_text = f"✅ Complete ({completed}/{total_in_thread})"
                elif current_symbol:
                    status_text = f"{current_symbol} 🔄"
                else:
                    status_text = "⏳ Waiting"
                
                # Thread line with fixed spacing and alignment
                thread_header = f"[Thread {thread_id}]"
                # Fixed width components for perfect alignment
                thread_part = f"│ {thread_header:<10} "  # Fixed width for thread header
                status_part = f"{status_text:<25} "        # Fixed width for status
                bar_part = f"{bar} "                       # Progress bar (10 chars + space)
                pct_part = f"{progress_pct*100:.0f}%"     # Percentage
                
                # Calculate remaining space to reach exactly 69 characters before final │
                content_length = len(thread_part) + len(status_part) + len(bar_part) + len(pct_part)
                padding = 69 - content_length
                
                thread_line = f"{thread_part}{status_part}{bar_part}{pct_part}{' ' * max(0, padding)}│"
                color = "green" if group['status'] == 'done' else "white"
                lines.append(colored(thread_line, color))
            
            lines.append(colored("└────────────────────────────────────────────────────────────────────┘", "cyan"))
            
            # Overall progress
            overall_pct = (total_completed / total_symbols) if total_symbols > 0 else 0
            overall_line = f"📊 Overall: {total_completed}/{total_symbols} ({overall_pct*100:.0f}%)"
            lines.append(colored(overall_line, "cyan"))
            
            # Display: First time shows normally, subsequent updates overwrite
            if not self._bars_displayed:
                # First display: show normally and log milestone
                for line in lines:
                    print(line)
                logging.info("📊 Thread progress monitoring started")
                self._bars_displayed = True
                self._table_lines = len(lines)
            else:
                # Overwrite previous table (move cursor up and rewrite)
                print(f"\033[{self._table_lines}A", end='')  # Move cursor up
                for line in lines:
                    print(f"\033[K{line}")  # Clear line and print new content
                
                # Log only major milestones (50%, 100%)
                milestones = [50, 100]
                current_milestone = int((overall_pct * 100) // 50) * 50
                if not hasattr(self, '_logged_milestone'):
                    self._logged_milestone = 0
                if current_milestone > self._logged_milestone and current_milestone in milestones:
                    logging.info(f"📊 Download progress: {current_milestone}% ({total_completed}/{total_symbols})")
                    self._logged_milestone = current_milestone

    def clear_data(self):
        """Clear stored market data to free memory"""
        self.all_symbol_data.clear()
        self.complete_symbols.clear()
        logging.debug("Market data cleared from memory")


# Global instance for easy access
global_market_analyzer = MarketAnalyzer()
