"""
Market Analyzer for the trading bot
Handles data collection, ML predictions, and market analysis
"""

import time
import logging
import asyncio
from termcolor import colored

from fetcher import fetch_markets, get_top_symbols, fetch_min_amounts, fetch_and_save_data
from predictor import predict_signal_ensemble
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
        
        # Clean symbol-by-symbol download with organized output
        for index, symbol in enumerate(self.top_symbols_analysis, 1):
            symbol_short = symbol.replace('/USDT:USDT', '')
            
            # 🚫 EARLY CHECK: Salta simbolo se già escluso da cicli precedenti
            from core.symbol_exclusion_manager import global_symbol_exclusion_manager
            if global_symbol_exclusion_manager.is_excluded(symbol):
                enhanced_logger.display_table(f"[{index}/{len(self.top_symbols_analysis)}] {symbol_short} - 🚫 SKIPPED (excluded)", "yellow")
                continue
                
            symbol_start_time = time.time()
            
            # Clean symbol header
            enhanced_logger.display_table(f"[{index}/{len(self.top_symbols_analysis)}] {symbol_short}", "cyan", attrs=['bold'])
            
            dataframes = {}
            symbol_success = True
            timeframe_results = []
            
            # Download all timeframes for this symbol
            for tf in enabled_timeframes:
                # 🚫 CHECK: Verifica se il simbolo è stato escluso nel frattempo
                if global_symbol_exclusion_manager.is_excluded(symbol):
                    enhanced_logger.display_table(f"  🚫 STOP: {symbol_short} excluded during processing", 'yellow')
                    symbol_success = False
                    break
                
                try:
                    tf_start = time.time()
                    df = await fetch_and_save_data(exchange, symbol, tf)
                    tf_time = time.time() - tf_start
                    
                    if df is not None and len(df) > 100:
                        dataframes[tf] = df
                        timeframe_results.append(f"  📥 {tf:>3}: {len(df):,} candles ✅ ({tf_time:.1f}s)")
                    else:
                        timeframe_results.append(f"  ❌ {tf:>3}: No data")
                        symbol_success = False
                        
                        # 🔧 IMMEDIATE EXCLUSION: Se un timeframe fallisce subito, escludi il simbolo
                        if len(dataframes) == 0:  # Nessun timeframe riuscito
                            enhanced_logger.display_table(f"  🚫 EXCLUDING: {symbol_short} - No data for first timeframe", 'yellow')
                            global_symbol_exclusion_manager.exclude_symbol_insufficient_data(
                                symbol, missing_timeframes=[tf]
                            )
                            symbol_success = False
                            break  # Esce dal loop timeframes
                        
                except Exception as e:
                    error_detail = str(e)
                    timeframe_results.append(f"  ❌ {tf:>3}: Error - {str(e)[:30]}...")
                    symbol_success = False
                    
                    # 🔧 IMMEDIATE EXCLUSION per dataset errors
                    if "too small" in error_detail.lower() or "insufficient" in error_detail.lower():
                        enhanced_logger.display_table(f"  🚫 EXCLUDING: {symbol_short} - Insufficient data", 'yellow')
                        global_symbol_exclusion_manager.exclude_symbol_insufficient_data(
                            symbol, missing_timeframes=[tf]
                        )
                        symbol_success = False
                        break  # Esce dal loop timeframes
            
            # Display results for this symbol
            for result in timeframe_results:
                enhanced_logger.display_table(result, 'green' if '✅' in result else 'red')
            
            # Symbol summary
            symbol_time = time.time() - symbol_start_time
            if symbol_success and len(dataframes) == len(enabled_timeframes):
                self.all_symbol_data[symbol] = dataframes
                successful_downloads += 1
                enhanced_logger.display_table(f"  ✅ Complete: {len(enabled_timeframes)}/{len(enabled_timeframes)} timeframes ({symbol_time:.1f}s total)", 'green')
            else:
                missing_tf = len(enabled_timeframes) - len(dataframes)
                missing_timeframes = [tf for tf in enabled_timeframes if tf not in dataframes]
                enhanced_logger.display_table(f"  ❌ Failed: Missing {missing_tf} timeframes", 'red')
                
                # 🚫 AUTO-EXCLUDE simbolo con timeframes insufficienti
                from core.symbol_exclusion_manager import global_symbol_exclusion_manager
                global_symbol_exclusion_manager.exclude_symbol_insufficient_data(
                    symbol, 
                    missing_timeframes=missing_timeframes
                )

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
        
        Args:
            xgb_models: Dictionary of XGBoost models by timeframe
            xgb_scalers: Dictionary of scalers by timeframe
            time_steps: Time steps for prediction
            
        Returns:
            tuple: (prediction_results, ml_time)
        """
        if not self.complete_symbols:
            logging.warning(colored("⚠️ No symbols with complete data this cycle", "yellow"))
            return {}, 0
        
        logging.info(colored("🧠 PHASE 2: PARALLEL ML PREDICTIONS", "cyan", attrs=['bold']))
        
        # Check if parallel predictor is available
        try:
            from core.parallel_predictor import predict_all_parallel
            parallel_available = True
        except ImportError:
            parallel_available = False
            logging.warning("⚠️ Parallel predictor not available, using sequential predictions")
        
        ml_start_time = time.time()
        prediction_results = {}
        
        if parallel_available:
            # Use parallel predictor for better performance
            prediction_results = await predict_all_parallel(
                self.all_symbol_data, xgb_models, xgb_scalers, time_steps
            )
        else:
            # Fallback to sequential predictions
            for symbol in self.complete_symbols:
                dataframes = self.all_symbol_data[symbol]
                result = predict_signal_ensemble(dataframes, xgb_models, xgb_scalers, symbol, time_steps)
                prediction_results[symbol] = result

        ml_time = time.time() - ml_start_time
        logging.info(colored(f"✅ ML predictions completed in {ml_time:.1f}s", "green"))
        
        return prediction_results, ml_time

    async def initialize_markets(self, exchange, top_analysis_crypto, excluded_symbols):
        """
        Initialize market data and get top symbols for analysis
        
        Args:
            exchange: Exchange instance
            top_analysis_crypto: Number of top symbols to get
            excluded_symbols: Symbols to exclude from analysis
            
        Returns:
            dict: Min amounts for symbols
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
            
            logging.info(f"✅ Initialized {len(self.top_symbols_analysis)} symbols for analysis")
            
            return self.min_amounts
            
        except Exception as e:
            logging.error(f"Market initialization error: {e}")
            raise

    def get_symbol_data(self, symbol):
        """
        Get dataframes for a specific symbol
        
        Args:
            symbol: Symbol to get data for
            
        Returns:
            dict: Dataframes by timeframe for the symbol
        """
        return self.all_symbol_data.get(symbol, {})

    def get_complete_symbols(self):
        """
        Get list of symbols with complete data
        
        Returns:
            list: Symbols with complete timeframe data
        """
        return self.complete_symbols.copy()

    def get_top_symbols(self):
        """
        Get list of top symbols for analysis
        
        Returns:
            list: Top symbols selected for analysis
        """
        return self.top_symbols_analysis.copy()

    def get_volumes_data(self):
        """
        Get volume data for display
        
        Returns:
            dict: Symbol volumes for display formatting
        """
        return self.symbol_volumes.copy()
    
    async def _get_top_symbols_with_volumes(self, exchange, all_symbols, top_n):
        """
        Get top symbols sorted by volume and store volume data
        
        Args:
            exchange: Exchange instance
            all_symbols: List of all available symbols
            top_n: Number of top symbols to return
            
        Returns:
            tuple: (top_symbols_list, volumes_dict)
        """
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
            
            logging.info(f"🚀 Parallel ticker fetch: {len(symbol_volumes)} symbols processed concurrently")
            
            return top_symbols, volumes_dict
            
        except Exception as e:
            logging.error(f"Error getting top symbols with volumes: {e}")
            # Fallback to basic method
            top_symbols = await get_top_symbols(exchange, all_symbols, top_n)
            return top_symbols, {}

    def clear_data(self):
        """
        Clear stored market data to free memory
        """
        self.all_symbol_data.clear()
        self.complete_symbols.clear()
        logging.debug("Market data cleared from memory")


# Global instance for easy access
global_market_analyzer = MarketAnalyzer()
