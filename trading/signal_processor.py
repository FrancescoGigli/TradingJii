"""
Signal Processor for the trading bot
Handles signal processing, RL filtering, and decision analysis
"""

import logging
import asyncio
from termcolor import colored

from utils.display_utils import calculate_ensemble_confidence, display_symbol_decision_analysis

# Import Decision Explainer for detailed analysis
try:
    from core.decision_explainer import global_decision_explainer
    DECISION_EXPLAINER_AVAILABLE = True
except ImportError:
    logging.warning("⚠️ Decision Explainer not available")
    DECISION_EXPLAINER_AVAILABLE = False
    global_decision_explainer = None


class SignalProcessor:
    """
    Processes ML predictions into trading signals and applies RL filtering
    """
    
    def __init__(self):
        self.position_manager_available = False
        
        # Import ThreadSafePositionManager
        try:
            from core.thread_safe_position_manager import global_thread_safe_position_manager
            self.position_manager = global_thread_safe_position_manager
            self.position_manager_available = True
            logging.debug("🔒 Signal Processor using ThreadSafePositionManager")
        except ImportError:
            logging.error("❌ ThreadSafePositionManager not available")
            self.position_manager_available = False
            raise ImportError("CRITICAL: ThreadSafePositionManager required for signal processing")

    async def process_prediction_results(self, prediction_results, all_symbol_data):
        """
        Process ML prediction results into trading signals
        
        FIX #3: Dynamic confidence threshold filtering
        
        Args:
            prediction_results: Results from ML predictions
            all_symbol_data: Market data for all symbols
            
        Returns:
            list: List of processed signals ready for execution
        """
        all_signals = []
        
        logging.info(colored("🔧 Processing prediction results for execution...", "yellow"))
        
        # FIX #3: Calculate dynamic confidence threshold
        confidence_threshold = self._calculate_dynamic_confidence_threshold()
        logging.info(colored(f"📊 Dynamic confidence threshold: {confidence_threshold:.1%}", "cyan"))
        
        for symbol, (ensemble_value, final_signal, tf_predictions) in prediction_results.items():
            try:
                symbol_short = symbol.replace('/USDT:USDT', '')
                logging.debug(f"🔍 Processing {symbol_short}: ensemble={ensemble_value}, signal={final_signal}")
                
                if ensemble_value is None or final_signal is None or final_signal == 2:
                    logging.debug(f"⏭️ Skipping {symbol_short}: ensemble={ensemble_value}, signal={final_signal}")
                    continue

                # Store signal with confidence details
                confidence_explanation = calculate_ensemble_confidence(tf_predictions, ensemble_value)
                
                # Get current price for ranking
                try:
                    # Use exchange to get current price - this would need to be passed in
                    # For now, use 0 as placeholder
                    current_price = 0
                except:
                    current_price = 0
                
                signal_data = {
                    'symbol': symbol,
                    'signal': final_signal,
                    'signal_name': 'BUY' if final_signal == 1 else 'SELL',
                    'confidence': ensemble_value,
                    'tf_predictions': tf_predictions,
                    'confidence_explanation': confidence_explanation,
                    'price': current_price,
                    'dataframes': all_symbol_data[symbol]  # Use pre-fetched data
                }
                
                # FIX #3: Dynamic confidence filter
                if ensemble_value < confidence_threshold:
                    logging.debug(
                        f"⏭️ {symbol_short}: Confidence {ensemble_value:.1%} < "
                        f"threshold {confidence_threshold:.1%}"
                    )
                    continue
                
                # Accept signal (RL removed - using XGBoost only)
                all_signals.append(signal_data)
                logging.info(f"✅ Added to execution queue: {symbol_short} {signal_data['signal_name']} (XGB:{ensemble_value:.1%})")
                
            except Exception as e:
                logging.error(f"Error processing signal for {symbol}: {e}")
                continue
        
        # Sort by ML confidence (highest first)
        all_signals.sort(key=lambda x: x.get('confidence', 0.0), reverse=True)
        
        logging.info(colored(f"🔢 Final signals ready for execution: {len(all_signals)}", "cyan"))
        for i, sig in enumerate(all_signals, 1):
            logging.debug(f"   {i}. {sig['symbol'].replace('/USDT:USDT', '')} {sig['signal_name']} - {sig['confidence']:.1%}")
        
        return all_signals


    async def display_complete_analysis(self, prediction_results, all_symbol_data):
        """
        Display complete analysis for all symbols showing decision pipeline
        
        Args:
            prediction_results: ML prediction results
            all_symbol_data: Market data for symbols
        """
        from core.enhanced_logging_system import enhanced_logger
        enhanced_logger.display_table(f"🔍 COMPLETE ANALYSIS FOR ALL SYMBOLS ({len(prediction_results)}/10)", "cyan", attrs=['bold'])
        enhanced_logger.display_table("=" * 80, "cyan")
        
        # Process ALL prediction results and show decision analysis
        prediction_items = list(prediction_results.items())
        for i, (symbol, (ensemble_value, final_signal, tf_predictions)) in enumerate(prediction_items, 1):
            try:
                # Create signal data for analysis display
                signal_name = 'BUY' if final_signal == 1 else 'SELL' if final_signal == 0 else 'NEUTRAL'
                signal_data = {
                    'symbol': symbol,
                    'signal': final_signal,
                    'signal_name': signal_name,
                    'confidence': ensemble_value if ensemble_value is not None else 0.0,
                    'tf_predictions': tf_predictions,
                    'price': 0
                }
                
                # Handle NEUTRAL signals
                if final_signal is None or final_signal == 2 or ensemble_value is None:
                    signal_data['signal_name'] = 'NEUTRAL'
                
                # Show decision analysis for this symbol
                if signal_data['signal_name'] in ['BUY', 'SELL']:
                    display_symbol_decision_analysis(
                        symbol, 
                        signal_data,
                        rl_available=False,
                        risk_manager_available=True
                    )
                
            except Exception as e:
                logging.error(f"Error in decision analysis for {symbol}: {e}")
                continue
        
        enhanced_logger.display_table("=" * 80, "cyan")

    async def get_current_price(self, exchange, symbol):
        """
        Get current price for a symbol
        
        Args:
            exchange: Exchange instance
            symbol: Symbol to get price for
            
        Returns:
            float: Current price or 0 if error
        """
        try:
            ticker = await exchange.fetch_ticker(symbol)
            return ticker.get('last', 0)
        except Exception as e:
            logging.warning(f"Could not get price for {symbol}: {e}")
            return 0

    def is_position_manager_available(self):
        """Check if position manager is available"""
        return self.position_manager_available
    
    def _calculate_dynamic_confidence_threshold(self):
        """
        Calculate dynamic confidence threshold based on market and performance
        
        FIX #3: Adapts threshold based on:
        - Market volatility (from market regime detector)
        - Recent performance (from session statistics)
        
        Returns:
            float: Dynamic confidence threshold (0.65-0.85)
        """
        import config
        
        # Start with base threshold
        threshold = getattr(config, 'MIN_CONFIDENCE_BASE', 0.65)
        
        # Adjust for market volatility
        try:
            from core.market_regime_detector import global_market_filter
            
            if hasattr(global_market_filter, 'last_volatility'):
                volatility = global_market_filter.last_volatility
                
                # High volatility = higher threshold required
                if volatility > 0.05:  # > 5% daily volatility
                    threshold = getattr(config, 'MIN_CONFIDENCE_VOLATILE', 0.75)
                    logging.debug(
                        f"📊 High volatility ({volatility:.1%}) - "
                        f"threshold increased to {threshold:.1%}"
                    )
        except Exception as e:
            logging.debug(f"Could not check market volatility: {e}")
        
        # Adjust based on recent performance
        if getattr(config, 'CONFIDENCE_ADAPTIVE_ENABLED', False):
            try:
                if self.position_manager_available:
                    # Get recent closed positions
                    session_summary = self.position_manager.get_session_summary()
                    
                    # Get win rate from recent trades
                    # Note: This is simplified - full implementation would track last N trades
                    total_trades = session_summary.get('closed_positions', 0)
                    
                    if total_trades >= 10:
                        # Calculate approximate recent win rate
                        winning_trades = session_summary.get('winning_trades', 0)
                        recent_wr = winning_trades / total_trades if total_trades > 0 else 0.5
                        
                        min_wr = getattr(config, 'CONFIDENCE_ADAPTIVE_MIN_WR', 0.55)
                        
                        if recent_wr < min_wr:
                            # Performance is poor, increase threshold
                            old_threshold = threshold
                            increase = getattr(config, 'CONFIDENCE_ADAPTIVE_INCREASE', 0.10)
                            threshold = min(0.85, threshold + increase)
                            
                            logging.warning(
                                f"⚠️ Recent win rate ({recent_wr:.1%}) < target ({min_wr:.1%}) - "
                                f"threshold increased: {old_threshold:.1%} → {threshold:.1%}"
                            )
            except Exception as e:
                logging.debug(f"Could not check recent performance: {e}")
        
        return threshold


# Global instance for easy access
global_signal_processor = SignalProcessor()
